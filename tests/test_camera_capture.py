import json
import stat
import tempfile
import unittest
from pathlib import Path

from plamp_web.camera_capture import (
    CameraCaptureError,
    capture_camera_image,
    capture_image_key,
    find_capture_image,
    list_camera_captures,
    resolve_capture_image_key,
)


class CameraCaptureTests(unittest.TestCase):
    def make_script(self, directory: Path, body: str) -> Path:
        script = directory / "fake-camera.sh"
        script.write_text(body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def write_config(self, path: Path, script: Path | None = None) -> None:
        data = {"timers": []}
        if script is not None:
            data["camera"] = {"capture_script": str(script)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_successful_capture_writes_image_and_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            script = self.make_script(
                root,
                "#!/usr/bin/env bash\n"
                "printf 'jpg' > \"$1\"\n"
                "echo 'timestamp=2026-04-12_12-10-00'\n"
                "echo \"image=$1\"\n"
                "echo 'command=rpicam-still --output example.jpg'\n"
                "echo 'exit_code=0'\n"
                "echo 'log=/tmp/camera.log'\n"
                "echo 'warning text' >&2\n",
            )
            self.write_config(config_file, script)

            metadata = capture_camera_image(
                repo_root=root,
                data_dir=root / "data",
                config_file=config_file,
                grow_config_file=root / "grow" / "missing" / "grow.json",
                capture_id="cap-test123",
            )

            image_path = root / metadata["image_path"]
            sidecar_path = root / metadata["sidecar_path"]
            self.assertEqual(metadata["capture_id"], "cap-test123")
            self.assertEqual(metadata["image_url"], "/api/camera/captures/cap-test123/image")
            self.assertEqual(metadata["camera_script"], str(script))
            self.assertEqual(metadata["camera_command"], [str(script), str(image_path)])
            self.assertEqual(metadata["camera_stderr"], "warning text")
            self.assertEqual(metadata["camera_summary"]["exit_code"], "0")
            self.assertEqual(image_path.read_bytes(), b"jpg")
            self.assertEqual(json.loads(sidecar_path.read_text(encoding="utf-8")), metadata)
            self.assertEqual(find_capture_image("cap-test123", data_dir=root / "data"), image_path)

    def test_successful_capture_stores_selected_camera_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            script = self.make_script(
                root,
                "#!/usr/bin/env bash\n"
                "printf 'jpg' > \"$1\"\n"
                "echo camera_id=$PLAMP_CAMERA_ID\n",
            )
            self.write_config(config_file, script)

            metadata = capture_camera_image(
                repo_root=root,
                data_dir=root / "data",
                config_file=config_file,
                grow_config_file=root / "grow" / "missing" / "grow.json",
                capture_id="cap-cam0",
                camera_id="rpicam_cam0",
            )

            sidecar = root / metadata["sidecar_path"]
            self.assertEqual(metadata["camera_id"], "rpicam_cam0")
            self.assertEqual(metadata["camera_summary"]["camera_id"], "rpicam_cam0")
            self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8"))["camera_id"], "rpicam_cam0")

    def test_grow_config_is_transitional_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root, "#!/usr/bin/env bash\nprintf 'jpg' > \"$1\"\n")
            config_file = root / "data" / "config.json"
            self.write_config(config_file)
            grow_config_file = root / "grow" / "grows" / "grow-thai-basil-siam-queen-2026-03-27" / "grow.json"
            grow_config_file.parent.mkdir(parents=True, exist_ok=True)
            grow_config_file.write_text(json.dumps({"camera": {"capture_script": str(script)}}), encoding="utf-8")

            metadata = capture_camera_image(
                repo_root=root,
                data_dir=root / "data",
                config_file=config_file,
                grow_config_file=grow_config_file,
                capture_id="cap-fallback",
            )

            self.assertEqual(metadata["camera_script"], str(script))


    def write_sidecar(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        path.with_suffix(".jpg").write_bytes(b"jpg")

    def test_list_camera_captures_combines_camera_roll_and_grow_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roll_image = root / "data" / "camera" / "captures" / "2026-04-13" / "cap-roll.jpg"
            grow_image = root / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-12" / "cap-grow.jpg"
            grow_config = root / "grow" / "grows" / "grow-basil" / "grow.json"
            grow_config.parent.mkdir(parents=True, exist_ok=True)
            grow_config.write_text(json.dumps({"grow_id": "grow-basil", "crop": {"common_name": "Basil", "cultivar": "Siam Queen"}}), encoding="utf-8")
            self.write_sidecar(
                roll_image.with_suffix(".json"),
                {
                    "capture_id": "cap-roll",
                    "timestamp": "2026-04-13T07:05:41+00:00",
                    "image_path": str(roll_image.relative_to(root)),
                    "sidecar_path": str(roll_image.with_suffix(".json").relative_to(root)),
                    "brightness_mean": 100.0,
                },
            )
            self.write_sidecar(
                grow_image.with_suffix(".json"),
                {
                    "timestamp": "2026-04-12T10:00:01+00:00",
                    "grow_id": "grow-basil",
                    "image_path": str(grow_image.relative_to(root)),
                    "sidecar_path": str(grow_image.with_suffix(".json").relative_to(root)),
                    "brightness_mean": 73.613,
                },
            )

            captures = list_camera_captures(repo_root=root, data_dir=root / "data", grows_dir=root / "grow" / "grows")

            self.assertEqual([item["capture_id"] for item in captures], ["cap-roll", "cap-grow"])
            self.assertEqual(captures[0]["source"], "camera_roll")
            self.assertIsNone(captures[0]["grow_id"])
            self.assertEqual(captures[1]["source"], "grow")
            self.assertEqual(captures[1]["grow_id"], "grow-basil")
            self.assertEqual(captures[1]["grow_name"], "Basil Siam Queen")
            self.assertTrue(captures[1]["image_url"].startswith("/api/camera/images/"))
            self.assertEqual(resolve_capture_image_key(captures[1]["image_key"], repo_root=root), grow_image)

    def test_list_camera_captures_filters_by_source_and_grow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roll_image = root / "data" / "camera" / "captures" / "2026-04-13" / "cap-roll.jpg"
            grow_image = root / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-12" / "cap-grow.jpg"
            self.write_sidecar(
                roll_image.with_suffix(".json"),
                {"timestamp": "2026-04-13T00:00:00+00:00", "image_path": str(roll_image.relative_to(root)), "sidecar_path": str(roll_image.with_suffix(".json").relative_to(root))},
            )
            self.write_sidecar(
                grow_image.with_suffix(".json"),
                {"timestamp": "2026-04-12T00:00:00+00:00", "grow_id": "grow-basil", "image_path": str(grow_image.relative_to(root)), "sidecar_path": str(grow_image.with_suffix(".json").relative_to(root))},
            )

            roll_only = list_camera_captures(repo_root=root, data_dir=root / "data", grows_dir=root / "grow" / "grows", source="camera_roll")
            grow_only = list_camera_captures(repo_root=root, data_dir=root / "data", grows_dir=root / "grow" / "grows", grow_id="grow-basil")

            self.assertEqual([item["source"] for item in roll_only], ["camera_roll"])
            self.assertEqual([item["grow_id"] for item in grow_only], ["grow-basil"])


    def test_list_camera_captures_supports_offset_paging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(3):
                image = root / "data" / "camera" / "captures" / "2026-04-13" / f"cap-{index}.jpg"
                self.write_sidecar(
                    image.with_suffix(".json"),
                    {
                        "capture_id": f"cap-{index}",
                        "timestamp": f"2026-04-13T00:00:0{index}+00:00",
                        "image_path": str(image.relative_to(root)),
                        "sidecar_path": str(image.with_suffix(".json").relative_to(root)),
                    },
                )

            captures = list_camera_captures(
                repo_root=root,
                data_dir=root / "data",
                grows_dir=root / "grow" / "grows",
                limit=1,
                offset=1,
            )

            self.assertEqual([item["capture_id"] for item in captures], ["cap-1"])

    def test_capture_image_key_rejects_paths_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = capture_image_key(Path("/tmp/outside.jpg"), repo_root=root)

            self.assertIsNone(resolve_capture_image_key(key, repo_root=root))

    def test_missing_script_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing-camera.sh"
            config_file = root / "data" / "config.json"
            self.write_config(config_file, missing)

            with self.assertRaisesRegex(CameraCaptureError, "capture script not found"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    capture_id="cap-missing",
                )

    def test_successful_script_without_image_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root, "#!/usr/bin/env bash\nexit 0\n")
            config_file = root / "data" / "config.json"
            self.write_config(config_file, script)

            with self.assertRaisesRegex(CameraCaptureError, "image file is missing"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    capture_id="cap-noimage",
                )

    def test_nonzero_script_raises_bad_gateway_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root, "#!/usr/bin/env bash\necho 'camera failed' >&2\nexit 7\n")
            config_file = root / "data" / "config.json"
            self.write_config(config_file, script)

            with self.assertRaisesRegex(CameraCaptureError, "camera command failed") as cm:
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    capture_id="cap-fail",
                )
            self.assertEqual(cm.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
