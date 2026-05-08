import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import plamp_web.server as server


class CameraApiTests(unittest.TestCase):
    def setUp(self) -> None:
        server.stop_camera_worker()

    def tearDown(self) -> None:
        server.stop_camera_worker()

    class FakePicamera2:
        def create_still_configuration(self) -> dict[str, str]:
            return {"mode": "still"}

        def configure(self, config: dict[str, str]) -> None:
            pass

        def set_controls(self, controls: dict[str, object]) -> None:
            pass

        def start(self) -> None:
            pass

        def capture_file(self, path: str) -> None:
            Path(path).write_bytes(b"jpg")

        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    def test_post_camera_capture_returns_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(
                json.dumps(
                    {
                        "timers": [],
                        "cameras": {
                            "rpicam_cam0": {
                                "capture_dir": "data/grow/grows/grow-basil/captures",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
                patch("plamp_web.camera_capture.load_picamera2_class", return_value=self.FakePicamera2),
                patch.object(server, "load_config", return_value=json.loads(config_file.read_text(encoding="utf-8"))),
            ):
                data = server.post_camera_capture(camera_id="rpicam_cam0")

            self.assertTrue(data["capture_id"].startswith("manual-rpicam_cam0-"))
            self.assertEqual(data["image_url"], f"/api/camera/captures/{data['capture_id']}/image")
            self.assertTrue((root / data["image_path"]).exists())
            self.assertNotIn("sidecar_path", data)
            self.assertEqual(data["camera_id"], "rpicam_cam0")
            self.assertEqual(data["camera_summary"]["backend"], "picamera2")
            self.assertNotIn("camera_script", data)



    def test_post_camera_capture_accepts_camera_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(
                json.dumps(
                    {
                        "cameras": {
                            "rpicam_cam0": {
                                "capture_dir": "data/grow/grows/grow-basil/captures",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
                patch("plamp_web.camera_capture.load_picamera2_class", return_value=self.FakePicamera2),
                patch.object(server, "load_config", return_value=json.loads(config_file.read_text(encoding="utf-8"))),
            ):
                data = server.post_camera_capture(camera_id="rpicam_cam0")

            self.assertEqual(data["camera_id"], "rpicam_cam0")

    def test_post_camera_capture_routes_through_camera_worker(self):
        class FakeWorker:
            def __init__(self) -> None:
                self.calls: list[tuple[str | None, str]] = []

            def capture(self, *, camera_id: str | None, capture_kind: str) -> dict[str, object]:
                self.calls.append((camera_id, capture_kind))
                return {"camera_id": camera_id, "capture_kind": capture_kind, "camera_summary": {"backend": "picamera2"}}

        worker = FakeWorker()
        with patch.object(server, "get_or_start_camera_worker", return_value=worker):
            data = server.post_camera_capture(camera_id="rpicam_cam0")

        self.assertEqual(worker.calls, [("rpicam_cam0", "manual")])
        self.assertEqual(data["camera_id"], "rpicam_cam0")
        self.assertEqual(data["capture_kind"], "manual")

    def test_get_runtime_includes_camera_worker_summary(self):
        with patch.object(server, "camera_worker_summary", return_value={"state": "idle", "queue_depth": 0}):
            data = server.get_runtime()

        self.assertEqual(data["camera_worker"]["state"], "idle")
        self.assertEqual(data["camera_worker"]["queue_depth"], 0)

    def test_camera_worker_collects_due_scheduled_cameras(self):
        worker = server.CameraWorker(capture_func=lambda **_: {"ok": True})
        worker.refresh_schedule(
            {
                "cam_b": {"capture_every_seconds": 0},
                "cam_a": {"capture_every_seconds": 5},
                "cam_c": {"capture_every_seconds": 10},
            },
            now=100.0,
        )

        self.assertEqual(worker.collect_due_camera_ids(now=100.0), ["cam_a", "cam_c"])
        worker.mark_capture_complete(camera_id="cam_a", capture_kind="auto", now=100.0)
        self.assertEqual(worker.collect_due_camera_ids(now=104.0), ["cam_c"])
        self.assertEqual(worker.collect_due_camera_ids(now=105.0), ["cam_a", "cam_c"])

    def test_get_camera_captures_returns_normalized_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            grows_dir = root / "data" / "grow" / "grows"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(
                json.dumps({"cameras": {"rpicam_cam0": {"capture_dir": "data/grow/grows/grow-basil/captures"}}}),
                encoding="utf-8",
            )
            image = root / "data" / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-13" / "manual-rpicam_cam0-2026-04-13T00-00-00Z-a1.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"jpg")

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "GROWS_DIR", grows_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
            ):
                data = server.get_camera_captures()

            self.assertEqual(len(data["captures"]), 1)
            self.assertEqual(data["captures"][0]["source"], "grow")
            self.assertEqual(data["captures"][0]["camera_id"], "rpicam_cam0")
            self.assertEqual(data["captures"][0]["capture_kind"], "manual")
            self.assertTrue(data["captures"][0]["image_url"].startswith("/api/camera/images/"))


    def test_get_camera_captures_supports_offset_paging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            grows_dir = root / "data" / "grow" / "grows"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(
                json.dumps({"cameras": {"rpicam_cam0": {"capture_dir": "data/grow/grows/grow-basil/captures"}}}),
                encoding="utf-8",
            )
            for index in range(3):
                image = root / "data" / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-13" / f"manual-rpicam_cam0-2026-04-13T00-00-0{index}Z-a{index}.jpg"
                image.parent.mkdir(parents=True, exist_ok=True)
                image.write_bytes(b"jpg")

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "GROWS_DIR", grows_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
            ):
                data = server.get_camera_captures(limit=1, offset=1)

            self.assertEqual(len(data["captures"]), 1)
            self.assertEqual(data["limit"], 1)
            self.assertEqual(data["offset"], 1)
            self.assertTrue(data["has_more"])
            self.assertEqual(data["total"], 3)

    def test_get_camera_image_by_key_returns_file_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "data" / "camera" / "captures" / "2026-04-13" / "cap-roll.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"jpg")
            key = server.camera_capture.capture_image_key(image, repo_root=root)

            with patch.object(server.camera_capture, "REPO_ROOT", root):
                response = server.get_camera_image_by_key(key)

            self.assertEqual(Path(response.path), image)
            self.assertEqual(response.media_type, "image/jpeg")

    def test_get_camera_capture_image_returns_jpeg_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = Path(tmp) / "data"
            grows_dir = root / "data" / "grow" / "grows"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(
                json.dumps({"cameras": {"rpicam_cam0": {"capture_dir": "data/grow/grows/grow-basil/captures"}}}),
                encoding="utf-8",
            )
            image_dir = root / "data" / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-12"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "manual-rpicam_cam0-2026-04-12T00-00-00Z-a1.jpg"
            image_path.write_bytes(b"jpg")

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "GROWS_DIR", grows_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
            ):
                response = server.get_camera_capture_image("manual-rpicam_cam0-2026-04-12T00-00-00Z-a1")

            self.assertEqual(Path(response.path), image_path)
            self.assertEqual(response.media_type, "image/jpeg")

    def test_get_camera_capture_image_404s_for_unknown_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(server.camera_capture, "DATA_DIR", Path(tmp) / "data"):
                with self.assertRaises(HTTPException) as cm:
                    server.get_camera_capture_image("cap-missing")

            self.assertEqual(cm.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
