import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plamp.locks import LockTimeout, exclusive_lock


class LockTests(unittest.TestCase):
    def test_lock_creates_parent_and_releases_for_next_caller(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "pico-abc.lock"
            with exclusive_lock(path, timeout=0.1):
                self.assertTrue(path.exists())
            with exclusive_lock(path, timeout=0.1):
                pass

    def test_lock_times_out_while_same_file_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pico-abc.lock"
            with exclusive_lock(path, timeout=0.1):
                with patch("plamp.locks.time.sleep"):
                    with self.assertRaisesRegex(LockTimeout, "pico-abc.lock"):
                        with exclusive_lock(path, timeout=0.0):
                            pass
