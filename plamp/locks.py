from __future__ import annotations

import errno
import fcntl
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockTimeout(TimeoutError):
    pass


@contextmanager
def exclusive_lock(path: Path, *, timeout: float, poll_interval: float = 0.01) -> Iterator[None]:
    """Acquire an interprocess lock within a finite, non-negative time budget.

    The budget governs lock polling; it cannot preempt synchronous filesystem OS calls.
    """
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("timeout must be finite and non-negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o664)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timed out waiting for {path.name}") from exc
                time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0.0)))
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
