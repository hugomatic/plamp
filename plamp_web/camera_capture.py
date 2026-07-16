from __future__ import annotations

import base64
import binascii
import importlib
import json
import os
import re
import secrets
import site
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plamp.context import resolve_context


RUNTIME_CONTEXT = resolve_context()
REPO_ROOT = RUNTIME_CONTEXT.root
DATA_DIR = RUNTIME_CONTEXT.data_dir
CONFIG_FILE = RUNTIME_CONTEXT.config_file
GROWS_DIR = DATA_DIR / "grow" / "grows"


@dataclass
class CameraCaptureError(Exception):
    message: str
    status_code: int = 500

    def __str__(self) -> str:
        return self.message


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise CameraCaptureError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CameraCaptureError(f"{path} must contain a JSON object")
    return data


def load_picamera2_class() -> type[Any]:
    try:
        module = importlib.import_module("picamera2")
    except ModuleNotFoundError:
        for path in ("/usr/lib/python3/dist-packages", "/usr/lib/python3.11/dist-packages"):
            if path not in sys.path and Path(path).exists():
                site.addsitedir(path)
        try:
            module = importlib.import_module("picamera2")
        except ModuleNotFoundError as exc:
            raise CameraCaptureError("Picamera2 is not available in the plamp-web Python environment") from exc
    camera_class = getattr(module, "Picamera2", None)
    if camera_class is None:
        raise CameraCaptureError("Picamera2 import succeeded but Picamera2 class is missing")
    return camera_class


def load_libcamera_controls_module() -> Any | None:
    try:
        return importlib.import_module("libcamera").controls
    except ModuleNotFoundError:
        for path in ("/usr/lib/python3/dist-packages", "/usr/lib/python3.11/dist-packages"):
            if path not in sys.path and Path(path).exists():
                site.addsitedir(path)
        try:
            return importlib.import_module("libcamera").controls
        except ModuleNotFoundError:
            return None


def configured_camera_settings(
    *,
    config_file: Path = CONFIG_FILE,
    camera_id: str,
) -> dict[str, Any]:
    config = load_json_object(config_file)
    cameras = config.get("cameras")
    if not isinstance(cameras, dict):
        return {}
    item = cameras.get(camera_id)
    if not isinstance(item, dict):
        return {}
    return item


def parse_camera_output(stdout: str) -> dict[str, str]:
    summary: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"timestamp", "image", "command", "exit_code", "log", "camera_id"}:
            summary[key] = value
    return summary


def build_picamera2_controls(camera_settings: dict[str, Any]) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    autofocus_mode = camera_settings.get("autofocus_mode")
    libcamera_controls = load_libcamera_controls_module()
    af_modes = getattr(libcamera_controls, "AfModeEnum", None) if libcamera_controls is not None else None
    if isinstance(autofocus_mode, str) and autofocus_mode and af_modes is not None:
        mode_map = {
            "auto": getattr(af_modes, "Auto", None),
            "continuous": getattr(af_modes, "Continuous", None),
            "manual": getattr(af_modes, "Manual", None),
        }
        af_mode = mode_map.get(autofocus_mode)
        if af_mode is not None:
            controls["AfMode"] = af_mode
    return controls


def capture_with_picamera2(
    *,
    output_path: Path,
    camera_id: str,
    camera_settings: dict[str, Any],
    captured_at: str,
) -> dict[str, Any]:
    camera_class = load_picamera2_class()
    try:
        picamera = camera_class()
    except Exception as exc:
        raise CameraCaptureError(f"camera capture failed: {exc}", status_code=502) from exc
    temp_file = tempfile.NamedTemporaryFile(
        prefix=f"{sanitize_capture_fragment(camera_id)}-",
        suffix=".jpg",
        dir="/tmp",
        delete=False,
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    controls = build_picamera2_controls(camera_settings)
    controls_summary: dict[str, Any] = {}
    autofocus_mode = camera_settings.get("autofocus_mode")
    autofocus_delay_ms = camera_settings.get("autofocus_delay_ms")
    if isinstance(autofocus_mode, str) and autofocus_mode:
        controls_summary["autofocus_mode"] = autofocus_mode
    try:
        configuration = picamera.create_still_configuration()
        picamera.configure(configuration)
        if controls and hasattr(picamera, "set_controls"):
            picamera.set_controls(controls)
        if hasattr(picamera, "start"):
            picamera.start()
        if (
            isinstance(autofocus_mode, str)
            and autofocus_mode in {"auto", "continuous", "manual"}
            and isinstance(autofocus_delay_ms, int)
            and autofocus_delay_ms > 0
        ):
            time.sleep(autofocus_delay_ms / 1000.0)
        picamera.capture_file(str(temp_path))
        if hasattr(picamera, "stop"):
            picamera.stop()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.replace(output_path)
    except CameraCaptureError:
        raise
    except Exception as exc:
        raise CameraCaptureError(f"camera capture failed: {exc}", status_code=502) from exc
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        close = getattr(picamera, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
    return {
        "backend": "picamera2",
        "camera_id": camera_id,
        "captured_at": captured_at,
        "controls": controls_summary,
    }


def wait_for_file(path: Path, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.1)
    raise CameraCaptureError(f"capture completed but image file is missing: {path}", status_code=502)


def image_mean_brightness(image_path: Path) -> float | None:
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return None
    try:
        with Image.open(image_path) as image:
            gray = image.convert("L")
            return round(ImageStat.Stat(gray).mean[0], 3)
    except Exception:
        return None


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


CAPTURE_FILE_RE = re.compile(
    r"^(?P<kind>manual|auto)-(?P<camera_id>.+)-(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)-(?P<token>[A-Za-z0-9]+)$"
)


def sanitize_capture_fragment(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return sanitized or "camera"


def parse_capture_filename(stem: str) -> tuple[str | None, str | None, str | None]:
    match = CAPTURE_FILE_RE.match(stem)
    if not match:
        return None, None, None
    timestamp_raw = match.group("timestamp")
    try:
        parsed = datetime.strptime(timestamp_raw, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None, None, None
    return match.group("kind"), match.group("camera_id"), parsed.isoformat()


def configured_camera_capture_dirs(
    *,
    repo_root: Path,
    config_file: Path,
    strict: bool,
) -> dict[str, Path]:
    config = load_json_object(config_file)
    cameras = config.get("cameras")
    if not isinstance(cameras, dict):
        return {}
    dirs: dict[str, Path] = {}
    resolved_root = repo_root.resolve()
    for camera_id, item in cameras.items():
        if not isinstance(camera_id, str) or not isinstance(item, dict):
            continue
        capture_dir = item.get("capture_dir")
        if not isinstance(capture_dir, str) or not capture_dir.strip():
            continue
        path = Path(capture_dir.strip()).expanduser()
        if path.is_absolute():
            if strict:
                raise CameraCaptureError(f"camera {camera_id} capture_dir must be repo-relative, got absolute path: {capture_dir}")
            continue
        resolved_path = (repo_root / path).resolve()
        if not resolved_path.is_relative_to(resolved_root):
            if strict:
                raise CameraCaptureError(f"camera {camera_id} capture_dir escapes repo root: {capture_dir}")
            continue
        dirs[camera_id] = resolved_path
    return dirs


def select_capture_target(
    *,
    repo_root: Path,
    data_dir: Path,
    config_file: Path,
    camera_id: str | None,
) -> tuple[str, Path]:
    configured_dirs = configured_camera_capture_dirs(repo_root=repo_root, config_file=config_file, strict=True)
    requested_camera_id = str(camera_id or "").strip()
    if requested_camera_id:
        if requested_camera_id not in configured_dirs:
            raise CameraCaptureError(f"unknown camera_id or missing capture_dir: {requested_camera_id}", status_code=404)
        return requested_camera_id, configured_dirs[requested_camera_id]
    if configured_dirs:
        selected = next(iter(configured_dirs))
        return selected, configured_dirs[selected]
    return "camera", (data_dir / "camera" / "captures").resolve()


def capture_camera_image(
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    config_file: Path = CONFIG_FILE,
    capture_id: str | None = None,
    camera_id: str | None = None,
    capture_kind: str = "manual",
) -> dict[str, Any]:
    now = utc_now_dt()
    final_capture_kind = capture_kind if capture_kind in {"manual", "auto"} else "manual"
    selected_camera_id, capture_root = select_capture_target(
        repo_root=repo_root,
        data_dir=data_dir,
        config_file=config_file,
        camera_id=camera_id,
    )
    timestamp_tag = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    default_capture_id = f"{final_capture_kind}-{sanitize_capture_fragment(selected_camera_id)}-{timestamp_tag}-{secrets.token_hex(3)}"
    final_capture_id = str(capture_id or default_capture_id).strip()
    if not final_capture_id or "/" in final_capture_id or "\\" in final_capture_id:
        raise CameraCaptureError(f"invalid capture_id: {final_capture_id}", status_code=422)
    day_dir = capture_root / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    image_path = day_dir / f"{final_capture_id}.jpg"
    camera_settings = configured_camera_settings(config_file=config_file, camera_id=selected_camera_id)
    summary = capture_with_picamera2(
        output_path=image_path,
        camera_id=selected_camera_id,
        camera_settings=camera_settings,
        captured_at=now.isoformat(),
    )
    wait_for_file(image_path)
    brightness = image_mean_brightness(image_path)

    metadata: dict[str, Any] = {
        "capture_id": final_capture_id,
        "timestamp": now.isoformat(),
        "capture_kind": final_capture_kind,
        "image_url": f"/api/camera/captures/{final_capture_id}/image",
        "image_path": repo_relative(image_path, repo_root),
        "camera_summary": summary,
        "camera_id": selected_camera_id,
    }
    if brightness is not None:
        metadata["brightness_mean"] = brightness

    return metadata


def candidate_grows_dirs(*, repo_root: Path, data_dir: Path, grows_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    for candidate in [grows_dir, repo_root / "grow" / "grows", data_dir.resolve().parent / "grow" / "grows"]:
        resolved = candidate.resolve()
        if any(existing.resolve() == resolved for existing in dirs):
            continue
        dirs.append(candidate)
    return dirs


def scan_capture_dirs(
    *,
    repo_root: Path,
    data_dir: Path,
    grows_dir: Path,
    config_file: Path,
) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        dirs.append(path)

    add(data_dir / "camera" / "captures")
    for candidate in candidate_grows_dirs(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir):
        for capture_root in candidate.glob("*/captures"):
            add(capture_root)
    try:
        for capture_dir in configured_camera_capture_dirs(repo_root=repo_root, config_file=config_file, strict=False).values():
            add(capture_dir)
    except CameraCaptureError:
        pass
    return dirs


def iter_capture_images(scan_dirs: list[Path]) -> list[Path]:
    images: list[Path] = []
    for capture_dir in scan_dirs:
        if not capture_dir.exists() or not capture_dir.is_dir():
            continue
        for image_path in capture_dir.rglob("*"):
            if not image_path.is_file():
                continue
            if image_path.suffix.lower() in {".jpg", ".jpeg"}:
                images.append(image_path)
    images.sort()
    return images


def find_capture_image(
    capture_id: str,
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    grows_dir: Path = GROWS_DIR,
    config_file: Path = CONFIG_FILE,
) -> Path | None:
    if not capture_id or "/" in capture_id or "\\" in capture_id:
        return None
    for image_path in iter_capture_images(scan_capture_dirs(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir, config_file=config_file)):
        if image_path.stem == capture_id:
            return image_path
    return None



def candidate_storage_roots(*, repo_root: Path, data_dir: Path, grows_dir: Path) -> list[Path]:
    roots: list[Path] = []
    for candidate in [repo_root, data_dir.resolve().parent, grows_dir.resolve().parents[1]]:
        resolved = candidate.resolve()
        if any(existing.resolve() == resolved for existing in roots):
            continue
        roots.append(candidate)
    return roots


def capture_image_key(image_path: Path, *, repo_root: Path = REPO_ROOT) -> str:
    resolved_root = repo_root.resolve()
    resolved_path = image_path.resolve()
    try:
        value = resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        value = resolved_path.as_posix()
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")

def resolve_capture_image_key(
    image_key: str,
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    grows_dir: Path = GROWS_DIR,
) -> Path | None:
    try:
        padded = image_key + "=" * (-len(image_key) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if not raw:
        return None
    decoded = Path(raw)
    candidate = decoded if decoded.is_absolute() else repo_root / decoded
    try:
        resolved = candidate.resolve()
        if not any(resolved.is_relative_to(root.resolve()) for root in candidate_storage_roots(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir)):
            return None
    except ValueError:
        return None
    if resolved.suffix.lower() not in {".jpg", ".jpeg"}:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


def grow_display_names(grows_dir: Path = GROWS_DIR) -> dict[str, str]:
    names: dict[str, str] = {}
    for grow_file in sorted(grows_dir.glob("*/grow.json")):
        grow = load_json_object(grow_file)
        grow_id = str(grow.get("grow_id") or grow_file.parent.name)
        crop = grow.get("crop")
        parts: list[str] = []
        if isinstance(crop, dict):
            for key in ["common_name", "cultivar"]:
                value = crop.get(key)
                if isinstance(value, str) and value:
                    parts.append(value)
        names[grow_id] = " ".join(parts) if parts else grow_id
    return names


def classify_capture_source(image_path: Path, *, data_dir: Path, grows_dirs: list[Path]) -> tuple[str, str | None]:
    resolved = image_path.resolve()
    for grows_root in grows_dirs:
        root_resolved = grows_root.resolve()
        if not resolved.is_relative_to(root_resolved):
            continue
        relative = resolved.relative_to(root_resolved)
        if len(relative.parts) >= 3 and relative.parts[1] == "captures":
            return "grow", relative.parts[0]
    if resolved.is_relative_to((data_dir / "camera" / "captures").resolve()):
        return "camera_roll", None
    return "camera_roll", None


def capture_timestamp(image_path: Path, timestamp_from_name: str | None) -> str:
    if timestamp_from_name:
        return timestamp_from_name
    fallback = datetime.fromtimestamp(image_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    return fallback.isoformat()


def normalized_capture_from_image(
    image_path: Path,
    *,
    repo_root: Path,
    data_dir: Path,
    grows_dirs: list[Path],
    grow_names: dict[str, str],
) -> dict[str, Any]:
    kind, camera_id, name_timestamp = parse_capture_filename(image_path.stem)
    source, detected_grow_id = classify_capture_source(image_path, data_dir=data_dir, grows_dirs=grows_dirs)
    key = capture_image_key(image_path, repo_root=repo_root)
    item: dict[str, Any] = {
        "capture_id": image_path.stem,
        "timestamp": capture_timestamp(image_path, name_timestamp),
        "source": source,
        "grow_id": detected_grow_id,
        "grow_name": grow_names.get(detected_grow_id, detected_grow_id) if detected_grow_id else None,
        "image_path": repo_relative(image_path, repo_root),
        "image_key": key,
        "image_url": f"/api/camera/images/{key}",
    }
    if kind:
        item["capture_kind"] = kind
    if camera_id:
        item["camera_id"] = camera_id
    return item


def collect_camera_captures(
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    grows_dir: Path = GROWS_DIR,
    config_file: Path = CONFIG_FILE,
    source: str = "all",
    grow_id: str | None = None,
) -> list[dict[str, Any]]:
    if source not in {"all", "camera_roll", "grow"}:
        source = "all"

    grow_names: dict[str, str] = {}
    grows_dirs = candidate_grows_dirs(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir)
    for candidate in grows_dirs:
        grow_names.update(grow_display_names(candidate))

    captures: list[dict[str, Any]] = []
    scan_dirs = scan_capture_dirs(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir, config_file=config_file)
    seen: set[Path] = set()
    for image_path in iter_capture_images(scan_dirs):
        resolved = image_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        item = normalized_capture_from_image(
            image_path,
            repo_root=repo_root,
            data_dir=data_dir,
            grows_dirs=grows_dirs,
            grow_names=grow_names,
        )
        if source != "all" and item.get("source") != source:
            continue
        if grow_id is not None and item.get("grow_id") != grow_id:
            continue
        captures.append(item)

    captures.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return captures


def list_camera_captures(
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    grows_dir: Path = GROWS_DIR,
    config_file: Path = CONFIG_FILE,
    source: str = "all",
    grow_id: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[dict[str, Any]]:
    captures = collect_camera_captures(
        repo_root=repo_root,
        data_dir=data_dir,
        grows_dir=grows_dir,
        config_file=config_file,
        source=source,
        grow_id=grow_id,
    )
    start = max(0, offset)
    stop = start + max(0, limit)
    return captures[start:stop]
