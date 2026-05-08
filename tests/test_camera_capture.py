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

    def write_config(self, path: Path, script: Path | None = None, cameras: dict[str, dict] | None = None) -> None:
        data: dict[str, object] = {"timers": []}
        if script is not None:
            data["camera"] = {"capture_script": str(script)}
        if cameras is not None:
            data["cameras"] = cameras
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def write_image(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpg")

    def test_successful_capture_writes_image_in_camera_capture_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            script = self.make_script(
                root,
                "#!/usr/bin/env bash\n"
                "printf 'jpg' > \"$1\"\n"
                "echo camera_id=$PLAMP_CAMERA_ID\n",
            )
            self.write_config(
                config_file,
                script,
                cameras={
                    "rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"},
                },
            )

            metadata = capture_camera_image(
                repo_root=root,
                data_dir=root / "data",
                config_file=config_file,
                grow_config_file=root / "grow" / "missing" / "grow.json",
                camera_id="rpicam_cam0",
            )

            image_path = root / metadata["image_path"]
            self.assertTrue(image_path.exists())
            self.assertEqual(image_path.read_bytes(), b"jpg")
            self.assertEqual(image_path.parent.parent, root / "grow" / "grows" / "grow-basil" / "captures")
            self.assertTrue(metadata["capture_id"].startswith("manual-rpicam_cam0-"))
            self.assertEqual(metadata["capture_kind"], "manual")
            self.assertEqual(metadata["camera_id"], "rpicam_cam0")
            self.assertEqual(metadata["camera_summary"]["camera_id"], "rpicam_cam0")
            self.assertEqual(metadata["camera_command"], [str(script), str(image_path)])
            self.assertEqual(metadata["image_url"], f"/api/camera/captures/{metadata['capture_id']}/image")

            resolved = find_capture_image(
                metadata["capture_id"],
                repo_root=root,
                data_dir=root / "data",
                grows_dir=root / "grow" / "grows",
                config_file=config_file,
            )
            self.assertEqual(resolved, image_path)

    def test_capture_with_unknown_camera_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            script = self.make_script(root, "#!/usr/bin/env bash\nprintf 'jpg' > \"$1\"\n")
            self.write_config(config_file, script, cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}})

            with self.assertRaisesRegex(CameraCaptureError, "unknown camera_id"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    camera_id="rpicam_cam9",
                )

    def test_capture_rejects_absolute_capture_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            script = self.make_script(root, "#!/usr/bin/env bash\nprintf 'jpg' > \"$1\"\n")
            self.write_config(config_file, script, cameras={"rpicam_cam0": {"capture_dir": "/tmp/captures"}})

            with self.assertRaisesRegex(CameraCaptureError, "repo-relative"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    camera_id="rpicam_cam0",
                )

    def test_list_camera_captures_scans_jpeg_files_without_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            self.write_config(
                config_file,
                script=None,
                cameras={
                    "rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"},
                    "rpicam_cam1": {"capture_dir": "data/camera/captures"},
                },
            )
            grow_dir = root / "grow" / "grows" / "grow-basil"
            grow_dir.mkdir(parents=True, exist_ok=True)
            grow_dir.joinpath("grow.json").write_text(
                json.dumps({"grow_id": "grow-basil", "crop": {"common_name": "Basil", "cultivar": "Siam Queen"}}),
                encoding="utf-8",
            )

            grow_image = grow_dir / "captures" / "2026-05-07" / "auto-rpicam_cam0-2026-05-07T18-12-44Z-a1b2c3.jpg"
            roll_image = root / "data" / "camera" / "captures" / "2026-05-07" / "manual-rpicam_cam1-2026-05-07T18-12-40Z-d4e5f6.jpg"
            self.write_image(grow_image)
            self.write_image(roll_image)

            captures = list_camera_captures(
                repo_root=root,
                data_dir=root / "data",
                grows_dir=root / "grow" / "grows",
                config_file=config_file,
            )

            self.assertEqual([item["capture_id"] for item in captures], [grow_image.stem, roll_image.stem])
            self.assertEqual(captures[0]["source"], "grow")
            self.assertEqual(captures[0]["grow_id"], "grow-basil")
            self.assertEqual(captures[0]["grow_name"], "Basil Siam Queen")
            self.assertEqual(captures[0]["capture_kind"], "auto")
            self.assertEqual(captures[0]["camera_id"], "rpicam_cam0")
            self.assertEqual(captures[1]["source"], "camera_roll")
            self.assertEqual(captures[1]["capture_kind"], "manual")
            self.assertEqual(captures[1]["camera_id"], "rpicam_cam1")
            self.assertTrue(captures[0]["image_url"].startswith("/api/camera/images/"))
            self.assertEqual(resolve_capture_image_key(captures[0]["image_key"], repo_root=root), grow_image)

    def test_list_camera_captures_filters_by_source_grow_and_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "data" / "config.json"
            self.write_config(
                config_file,
                script=None,
                cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}},
            )

            grow_dir = root / "grow" / "grows" / "grow-basil"
            grow_dir.mkdir(parents=True, exist_ok=True)
            grow_dir.joinpath("grow.json").write_text(json.dumps({"grow_id": "grow-basil"}), encoding="utf-8")
            self.write_image(grow_dir / "captures" / "2026-05-07" / "manual-rpicam_cam0-2026-05-07T18-12-44Z-a1b2c3.jpg")
            self.write_image(grow_dir / "captures" / "2026-05-07" / "manual-rpicam_cam0-2026-05-07T18-12-45Z-a1b2c4.jpg")
            self.write_image(root / "data" / "camera" / "captures" / "2026-05-07" / "manual-rpicam_cam9-2026-05-07T18-12-46Z-a1b2c5.jpg")

            grow_only = list_camera_captures(
                repo_root=root,
                data_dir=root / "data",
                grows_dir=root / "grow" / "grows",
                config_file=config_file,
                source="grow",
                grow_id="grow-basil",
            )
            roll_only = list_camera_captures(
                repo_root=root,
                data_dir=root / "data",
                grows_dir=root / "grow" / "grows",
                config_file=config_file,
                source="camera_roll",
                limit=1,
                offset=0,
            )

            self.assertEqual([item["source"] for item in grow_only], ["grow", "grow"])
            self.assertEqual([item["grow_id"] for item in grow_only], ["grow-basil", "grow-basil"])
            self.assertEqual(len(roll_only), 1)
            self.assertEqual(roll_only[0]["source"], "camera_roll")

    def test_list_camera_captures_falls_back_to_shared_grows_dir_from_data_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared_root = root / "shared-root"
            run_root = root / "run-root"
            shared_root.mkdir()
            run_root.mkdir()

            data_dir = shared_root / "data"
            data_dir.mkdir()
            linked_data_dir = run_root / "data"
            linked_data_dir.symlink_to(data_dir, target_is_directory=True)

            grows_dir = run_root / "grow" / "grows"
            grow_dir = grows_dir / "grow-basil"
            grow_dir.mkdir(parents=True, exist_ok=True)
            grow_dir.joinpath("grow.json").write_text(
                json.dumps({"grow_id": "grow-basil", "crop": {"common_name": "Basil", "cultivar": "Siam Queen"}}),
                encoding="utf-8",
            )

            config_file = linked_data_dir / "config.json"
            self.write_config(config_file, script=None, cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}})

            shared_grow_image = shared_root / "grow" / "grows" / "grow-basil" / "captures" / "2026-04-12" / "manual-rpicam_cam0-2026-04-12T10-00-01Z-deadbe.jpg"
            self.write_image(shared_grow_image)

            captures = list_camera_captures(
                repo_root=run_root,
                data_dir=linked_data_dir,
                grows_dir=grows_dir,
                config_file=config_file,
            )

            self.assertEqual([item["capture_id"] for item in captures], [shared_grow_image.stem])
            self.assertEqual(captures[0]["source"], "grow")
            self.assertEqual(captures[0]["grow_id"], "grow-basil")

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
            self.write_config(config_file, missing, cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}})

            with self.assertRaisesRegex(CameraCaptureError, "capture script not found"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    camera_id="rpicam_cam0",
                )

    def test_successful_script_without_image_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root, "#!/usr/bin/env bash\nexit 0\n")
            config_file = root / "data" / "config.json"
            self.write_config(config_file, script, cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}})

            with self.assertRaisesRegex(CameraCaptureError, "image file is missing"):
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    camera_id="rpicam_cam0",
                )

    def test_nonzero_script_raises_bad_gateway_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.make_script(root, "#!/usr/bin/env bash\necho 'camera failed' >&2\nexit 7\n")
            config_file = root / "data" / "config.json"
            self.write_config(config_file, script, cameras={"rpicam_cam0": {"capture_dir": "grow/grows/grow-basil/captures"}})

            with self.assertRaisesRegex(CameraCaptureError, "camera command failed") as cm:
                capture_camera_image(
                    repo_root=root,
                    data_dir=root / "data",
                    config_file=config_file,
                    grow_config_file=root / "grow" / "missing" / "grow.json",
                    camera_id="rpicam_cam0",
                )
            self.assertEqual(cm.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
