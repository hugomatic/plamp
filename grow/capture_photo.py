#!/usr/bin/env python3
import argparse
import json
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageStat

REPO_ROOT = Path(__file__).resolve().parents[1]
GROWS_DIR = REPO_ROOT / "grow" / "grows"


def append_event(grow_dir: Path, event: dict) -> None:
    with (grow_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def load_grow(grow_id: str) -> tuple[Path, dict]:
    grow_dir = GROWS_DIR / grow_id
    grow_file = grow_dir / "grow.json"
    if not grow_file.exists():
        raise SystemExit(f"missing grow config: {grow_file}")
    return grow_dir, json.loads(grow_file.read_text(encoding="utf-8"))


def latest_capture_sidecar(grow_dir: Path) -> Path | None:
    captures_dir = grow_dir / "captures"
    if not captures_dir.exists():
        return None
    sidecars = sorted(captures_dir.glob("*/*.json"))
    return sidecars[-1] if sidecars else None


def image_mean_brightness(image_path: Path) -> float:
    with Image.open(image_path) as image:
        gray = image.convert("L")
        return round(ImageStat.Stat(gray).mean[0], 3)


def wait_for_file(path: Path, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.1)
    raise SystemExit(f"capture completed but image file is missing: {path}")


def parse_camera_output(stdout: str) -> dict:
    summary = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"timestamp", "image", "command", "exit_code", "log"}:
            summary[key] = value
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one grow photo into the canonical grow folder.")
    parser.add_argument("--grow", required=True)
    args = parser.parse_args()

    grow_dir, grow = load_grow(args.grow)
    script = Path(grow["camera"]["capture_script"]).expanduser()
    if not script.exists():
        raise SystemExit(f"capture script not found: {script}")

    now = utc_now_dt()
    day = now.strftime("%Y-%m-%d")
    capture_dir = grow_dir / "captures" / day
    capture_dir.mkdir(parents=True, exist_ok=True)

    token = secrets.token_hex(3)
    image_path = capture_dir / f"cap-{token}.jpg"
    completed = subprocess.run([str(script), str(image_path)], check=True, capture_output=True, text=True)
    wait_for_file(image_path)

    camera_summary = parse_camera_output(completed.stdout)
    previous_sidecar_path = latest_capture_sidecar(grow_dir)
    brightness = image_mean_brightness(image_path)

    metadata = {
        "timestamp": now.isoformat(),
        "grow_id": args.grow,
        "image_path": str(image_path.relative_to(REPO_ROOT)),
        "camera_script": str(script),
        "camera_command": [str(script), str(image_path)],
        "camera_summary": camera_summary,
        "camera_stderr": completed.stderr.strip(),
        "brightness_mean": brightness,
        "previous_capture": None,
        "comparison": {
            "status": "pending",
            "reason": "run compare_light.py or hourly_tend.py to evaluate against previous capture"
        },
        "ai_compare": {
            "status": "ready",
            "current_image_path": str(image_path.relative_to(REPO_ROOT)),
            "previous_image_path": None,
            "question": "Compare the two grow photos. Is the grow light on or off in the current image? Note any obvious scene change or camera framing problem."
        }
    }

    if previous_sidecar_path and previous_sidecar_path != image_path.with_suffix('.json'):
        previous = json.loads(previous_sidecar_path.read_text(encoding="utf-8"))
        metadata["previous_capture"] = {
            "timestamp": previous.get("timestamp"),
            "image_path": previous.get("image_path"),
            "brightness_mean": previous.get("brightness_mean"),
        }
        metadata["ai_compare"]["previous_image_path"] = previous.get("image_path")

    sidecar_path = image_path.with_suffix(".json")
    sidecar_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    append_event(
        grow_dir,
        {
            "ts": now.isoformat(),
            "kind": "capture",
            "message": f"captured {metadata['image_path']}",
            "data": {
                "image_path": metadata["image_path"],
                "brightness_mean": metadata["brightness_mean"],
                "previous_image_path": None if metadata["previous_capture"] is None else metadata["previous_capture"]["image_path"],
            },
        },
    )

    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
