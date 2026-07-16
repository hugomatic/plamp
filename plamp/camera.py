from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from plamp.locks import exclusive_lock


class CameraError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


def _default_capture(**kwargs: Any) -> dict[str, Any]:
    # Capture mechanics remain a lower detail layer while callers converge on
    # this stable, process-safe library boundary.
    from plamp_web.camera_capture import capture_camera_image

    return capture_camera_image(**kwargs)


def capture_camera(
    camera_id: str,
    *,
    lock_dir: Path,
    timeout: float = 60.0,
    capture_kind: str = "manual",
    capture_func: Callable[..., dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if not camera_id or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in camera_id):
        raise ValueError("camera_id must contain only letters, digits, underscore, or hyphen")
    operation = capture_func or _default_capture
    with exclusive_lock(lock_dir / f"camera-{camera_id}.lock", timeout=timeout):
        try:
            return operation(camera_id=camera_id, capture_kind=capture_kind, **kwargs)
        except Exception as exc:
            if isinstance(exc, CameraError):
                raise
            raise CameraError(str(exc), status_code=int(getattr(exc, "status_code", 500))) from exc
