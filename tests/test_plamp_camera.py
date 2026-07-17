import tempfile
import unittest
from pathlib import Path

from plamp.camera import capture_camera
from plamp.locks import LockTimeout, exclusive_lock


class CameraLibraryTests(unittest.TestCase):
    def test_capture_uses_camera_specific_process_lock(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp)
            lock_path = lock_dir / "camera-cam0.lock"
            with exclusive_lock(lock_path, timeout=0.1):
                with self.assertRaises(LockTimeout):
                    capture_camera(
                        "cam0",
                        lock_dir=lock_dir,
                        timeout=0.0,
                        capture_func=lambda **kwargs: calls.append(kwargs),
                    )

        self.assertEqual(calls, [])

    def test_capture_returns_detail_layer_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = capture_camera(
                "cam0",
                lock_dir=Path(tmp),
                timeout=0.1,
                capture_kind="manual",
                capture_func=lambda **kwargs: {"camera_id": kwargs["camera_id"], "capture_kind": kwargs["capture_kind"]},
            )

        self.assertEqual(result, {"camera_id": "cam0", "capture_kind": "manual"})
