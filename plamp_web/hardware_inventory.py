from __future__ import annotations

import re
import subprocess
from typing import Any

CAMERA_RE = re.compile(r"^\s*(\d+)\s*:\s*([^\s\[]+)\s*\[[^\]]*\]\s*\(([^)]+)\)")


def rpicam_key(connector: str) -> str:
    return f"rpicam:{connector}"


def sensor_from_model(model: str) -> str:
    return model.split("_", 1)[0]


def lens_from_model(model: str) -> str:
    return "wide" if "wide" in model.lower() else "normal"


def parse_rpicam_list_cameras(output: str) -> list[dict[str, Any]]:
    cameras = []
    for line in output.splitlines():
        match = CAMERA_RE.match(line)
        if not match:
            continue
        index = int(match.group(1))
        model = match.group(2)
        connector = f"cam{index}"
        cameras.append({
            "key": rpicam_key(connector),
            "connector": connector,
            "index": index,
            "sensor": sensor_from_model(model),
            "model": model,
            "lens": lens_from_model(model),
            "path": match.group(3),
        })
    return cameras


def detect_rpicam_cameras() -> list[dict[str, Any]]:
    for command in (["rpicam-hello", "--list-cameras"], ["libcamera-hello", "--list-cameras"]):
        try:
            output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=5)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        return parse_rpicam_list_cameras(output)
    return []
