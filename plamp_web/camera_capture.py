from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"
TRANSITIONAL_GROW_CONFIG_FILE = REPO_ROOT / "grow" / "grows" / "grow-thai-basil-siam-queen-2026-03-27" / "grow.json"
GROWS_DIR = REPO_ROOT / "grow" / "grows"


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


def configured_capture_script(config_file: Path = CONFIG_FILE, grow_config_file: Path = TRANSITIONAL_GROW_CONFIG_FILE) -> Path:
    config = load_json_object(config_file)
    camera = config.get("camera")
    if isinstance(camera, dict) and isinstance(camera.get("capture_script"), str) and camera["capture_script"]:
        return Path(camera["capture_script"]).expanduser()

    grow = load_json_object(grow_config_file)
    grow_camera = grow.get("camera")
    if isinstance(grow_camera, dict) and isinstance(grow_camera.get("capture_script"), str) and grow_camera["capture_script"]:
        return Path(grow_camera["capture_script"]).expanduser()

    raise CameraCaptureError("no camera capture script configured; set camera.capture_script in data/config.json")


def parse_camera_output(stdout: str) -> dict[str, str]:
    summary: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"timestamp", "image", "command", "exit_code", "log", "camera_id"}:
            summary[key] = value
    return summary


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


def new_capture_id() -> str:
    return f"cap-{secrets.token_hex(3)}"


def capture_camera_image(
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    config_file: Path = CONFIG_FILE,
    grow_config_file: Path = TRANSITIONAL_GROW_CONFIG_FILE,
    capture_id: str | None = None,
    camera_id: str | None = None,
) -> dict[str, Any]:
    script = configured_capture_script(config_file, grow_config_file)
    if not script.exists():
        raise CameraCaptureError(f"capture script not found: {script}")

    now = utc_now_dt()
    final_capture_id = capture_id or new_capture_id()
    day_dir = data_dir / "camera" / "captures" / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    image_path = day_dir / f"{final_capture_id}.jpg"
    sidecar_path = image_path.with_suffix(".json")
    command = [str(script), str(image_path)]
    env = os.environ.copy()
    selected_camera_id = str(camera_id or "").strip()
    if selected_camera_id:
        env["PLAMP_CAMERA_ID"] = selected_camera_id

    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        detail = f"camera command failed with exit code {exc.returncode}"
        if stderr:
            detail = f"{detail}: {stderr}"
        raise CameraCaptureError(detail, status_code=502) from exc

    wait_for_file(image_path)
    brightness = image_mean_brightness(image_path)

    metadata: dict[str, Any] = {
        "capture_id": final_capture_id,
        "timestamp": now.isoformat(),
        "image_url": f"/api/camera/captures/{final_capture_id}/image",
        "image_path": repo_relative(image_path, repo_root),
        "sidecar_path": repo_relative(sidecar_path, repo_root),
        "camera_script": str(script),
        "camera_command": command,
        "camera_summary": parse_camera_output(completed.stdout),
        "camera_stderr": completed.stderr.strip(),
    }
    if selected_camera_id:
        metadata["camera_id"] = selected_camera_id
    if brightness is not None:
        metadata["brightness_mean"] = brightness

    sidecar_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def find_capture_image(capture_id: str, *, data_dir: Path = DATA_DIR) -> Path | None:
    if not capture_id.startswith("cap-") or "/" in capture_id or "\\" in capture_id:
        return None
    matches = sorted((data_dir / "camera" / "captures").glob(f"*/{capture_id}.jpg"))
    for match in matches:
        if match.exists() and match.is_file():
            return match
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


def candidate_grows_dirs(*, repo_root: Path, data_dir: Path, grows_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    for candidate in [grows_dir, data_dir.resolve().parent / "grow" / "grows"]:
        resolved = candidate.resolve()
        if any(existing.resolve() == resolved for existing in dirs):
            continue
        dirs.append(candidate)
    return dirs


def path_from_metadata(metadata: dict[str, Any], key: str, root_base: Path) -> Path | None:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root_base / path


def normalized_capture_from_sidecar(
    sidecar_path: Path,
    *,
    repo_root: Path,
    root_base: Path,
    source: str,
    grow_names: dict[str, str],
) -> dict[str, Any] | None:
    try:
        metadata = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    image_path = path_from_metadata(metadata, "image_path", root_base) or sidecar_path.with_suffix(".jpg")
    if not image_path.exists() or not image_path.is_file():
        return None
    grow_id = metadata.get("grow_id") if isinstance(metadata.get("grow_id"), str) else None
    capture_id = metadata.get("capture_id") if isinstance(metadata.get("capture_id"), str) else image_path.stem
    timestamp = metadata.get("timestamp") if isinstance(metadata.get("timestamp"), str) else ""
    key = capture_image_key(image_path, repo_root=repo_root)
    item: dict[str, Any] = {
        "capture_id": capture_id,
        "timestamp": timestamp,
        "source": source,
        "grow_id": grow_id,
        "grow_name": grow_names.get(grow_id, grow_id) if grow_id else None,
        "image_path": repo_relative(image_path, repo_root),
        "sidecar_path": repo_relative(sidecar_path, repo_root),
        "image_key": key,
        "image_url": f"/api/camera/images/{key}",
    }
    if "brightness_mean" in metadata:
        item["brightness_mean"] = metadata["brightness_mean"]
    if isinstance(metadata.get("camera_id"), str) and metadata["camera_id"]:
        item["camera_id"] = metadata["camera_id"]
    return item


def collect_camera_captures(
    *,
    repo_root: Path = REPO_ROOT,
    data_dir: Path = DATA_DIR,
    grows_dir: Path = GROWS_DIR,
    source: str = "all",
    grow_id: str | None = None,
) -> list[dict[str, Any]]:
    if source not in {"all", "camera_roll", "grow"}:
        source = "all"
    grow_names: dict[str, str] = {}
    grows_dirs = candidate_grows_dirs(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir)
    for candidate in grows_dirs:
        grow_names.update(grow_display_names(candidate))
    sidecars: list[tuple[str, Path, Path]] = []
    shared_root = data_dir.resolve().parent
    if source in {"all", "camera_roll"} and grow_id is None:
        sidecars.extend(("camera_roll", path, shared_root) for path in (data_dir / "camera" / "captures").glob("*/*.json"))
    if source in {"all", "grow"}:
        for candidate in grows_dirs:
            sidecars.extend(("grow", path, candidate.resolve().parents[1]) for path in candidate.glob("*/captures/*/*.json"))

    captures: list[dict[str, Any]] = []
    for item_source, sidecar, root_base in sidecars:
        item = normalized_capture_from_sidecar(
            sidecar,
            repo_root=repo_root,
            root_base=root_base,
            source=item_source,
            grow_names=grow_names,
        )
        if item is None:
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
    source: str = "all",
    grow_id: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[dict[str, Any]]:
    captures = collect_camera_captures(repo_root=repo_root, data_dir=data_dir, grows_dir=grows_dir, source=source, grow_id=grow_id)
    start = max(0, offset)
    stop = start + max(0, limit)
    return captures[start:stop]
