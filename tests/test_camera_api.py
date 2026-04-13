import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import plamp_web.server as server


class CameraApiTests(unittest.TestCase):
    def make_script(self, directory: Path) -> Path:
        script = directory / "fake-camera.sh"
        script.write_text("#!/usr/bin/env bash\nprintf 'jpg' > \"$1\"\necho 'exit_code=0'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def test_post_camera_capture_returns_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root)
            data_dir = root / "data"
            config_file = data_dir / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(json.dumps({"timers": [], "camera": {"capture_script": str(script)}}), encoding="utf-8")

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "CONFIG_FILE", config_file),
                patch.object(server.camera_capture, "TRANSITIONAL_GROW_CONFIG_FILE", root / "grow.json"),
            ):
                data = server.post_camera_capture()

            self.assertTrue(data["capture_id"].startswith("cap-"))
            self.assertEqual(data["image_url"], f"/api/camera/captures/{data['capture_id']}/image")
            self.assertTrue((root / data["image_path"]).exists())
            self.assertTrue((root / data["sidecar_path"]).exists())


    def test_get_camera_captures_returns_normalized_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            grows_dir = root / "grow" / "grows"
            image = data_dir / "camera" / "captures" / "2026-04-13" / "cap-roll.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"jpg")
            image.with_suffix(".json").write_text(
                json.dumps({"timestamp": "2026-04-13T00:00:00+00:00", "image_path": str(image.relative_to(root)), "sidecar_path": str(image.with_suffix(".json").relative_to(root))}),
                encoding="utf-8",
            )

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "GROWS_DIR", grows_dir),
            ):
                data = server.get_camera_captures()

            self.assertEqual(len(data["captures"]), 1)
            self.assertEqual(data["captures"][0]["source"], "camera_roll")
            self.assertTrue(data["captures"][0]["image_url"].startswith("/api/camera/images/"))


    def test_get_camera_captures_supports_offset_paging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            grows_dir = root / "grow" / "grows"
            for index in range(3):
                image = data_dir / "camera" / "captures" / "2026-04-13" / f"cap-{index}.jpg"
                image.parent.mkdir(parents=True, exist_ok=True)
                image.write_bytes(b"jpg")
                image.with_suffix(".json").write_text(
                    json.dumps({
                        "capture_id": f"cap-{index}",
                        "timestamp": f"2026-04-13T00:00:0{index}+00:00",
                        "image_path": str(image.relative_to(root)),
                        "sidecar_path": str(image.with_suffix(".json").relative_to(root)),
                    }),
                    encoding="utf-8",
                )

            with (
                patch.object(server.camera_capture, "REPO_ROOT", root),
                patch.object(server.camera_capture, "DATA_DIR", data_dir),
                patch.object(server.camera_capture, "GROWS_DIR", grows_dir),
            ):
                data = server.get_camera_captures(limit=1, offset=1)

            self.assertEqual([item["capture_id"] for item in data["captures"]], ["cap-1"])
            self.assertEqual(data["limit"], 1)
            self.assertEqual(data["offset"], 1)
            self.assertTrue(data["has_more"])

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
            data_dir = Path(tmp) / "data"
            image_dir = data_dir / "camera" / "captures" / "2026-04-12"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "cap-test.jpg"
            image_path.write_bytes(b"jpg")

            with patch.object(server.camera_capture, "DATA_DIR", data_dir):
                response = server.get_camera_capture_image("cap-test")

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
