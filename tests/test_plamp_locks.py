import math
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plamp.locks import LockTimeout, exclusive_lock


def _hold_lock_until_released(path, ready, release):
    with exclusive_lock(Path(path), timeout=1.0):
        ready.set()
        release.wait(5.0)
        os._exit(0)


class LockTests(unittest.TestCase):
    def test_rejects_invalid_timeouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pico-abc.lock"
            for timeout in (-0.01, math.nan, math.inf, -math.inf):
                with self.subTest(timeout=timeout):
                    with self.assertRaisesRegex(ValueError, "timeout"):
                        with exclusive_lock(path, timeout=timeout):
                            pass

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

    def test_lock_contends_across_processes_and_releases_on_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pico-process.lock"
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            release = context.Event()
            process = context.Process(target=_hold_lock_until_released, args=(str(path), ready, release))
            process.start()
            self.assertTrue(ready.wait(5.0))
            try:
                with self.assertRaises(LockTimeout):
                    with exclusive_lock(path, timeout=0.0):
                        pass
            finally:
                release.set()
                process.join(5.0)
                if process.is_alive():
                    process.terminate()
                    process.join(5.0)
            self.assertEqual(process.exitcode, 0)
            with exclusive_lock(path, timeout=0.1):
                pass
