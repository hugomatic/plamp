#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GROWS_DIR = REPO_ROOT / "grow" / "grows"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(cmd: list[str]) -> dict:
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    return json.loads(stdout)


def append_event(grow_dir: Path, event: dict) -> None:
    with (grow_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one hourly grow-tending pass.")
    parser.add_argument("--grow", required=True)
    args = parser.parse_args()

    grow_dir = GROWS_DIR / args.grow
    if not (grow_dir / "grow.json").exists():
        raise SystemExit(f"missing grow config: {grow_dir / 'grow.json'}")

    base = [sys.executable]
    capture = run(base + [str(REPO_ROOT / "grow" / "capture_photo.py"), "--grow", args.grow])
    compare = run(base + [str(REPO_ROOT / "grow" / "compare_light.py"), "--grow", args.grow])

    summary = {
        "ts": utc_now(),
        "kind": "hourly_tend",
        "message": f"captured {capture['image_path']} and inferred light_state={compare['light_state']}",
        "data": {
            "capture": {
                "timestamp": capture["timestamp"],
                "image_path": capture["image_path"],
                "brightness_mean": capture["brightness_mean"],
            },
            "comparison": compare,
        },
    }
    append_event(grow_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
