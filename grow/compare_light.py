#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GROWS_DIR = REPO_ROOT / "grow" / "grows"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_sidecars(grow_id: str) -> tuple[Path, list[Path]]:
    grow_dir = GROWS_DIR / grow_id
    if not (grow_dir / "grow.json").exists():
        raise SystemExit(f"missing grow config: {grow_dir / 'grow.json'}")
    sidecars = sorted((grow_dir / "captures").glob("*/*.json"))
    if not sidecars:
        raise SystemExit("no capture sidecars found")
    return grow_dir, sidecars


def classify(current_brightness: float, previous_brightness: float | None) -> tuple[str, str]:
    if previous_brightness is None:
        return "unknown", "no previous capture available"

    delta = current_brightness - previous_brightness
    if current_brightness >= 90 and delta >= 8:
        return "on", f"brightness increased by {delta:.3f}"
    if current_brightness <= 70 and delta <= -8:
        return "off", f"brightness decreased by {delta:.3f}"
    if current_brightness >= 115:
        return "on", "current frame is bright enough to classify as on"
    if current_brightness <= 45:
        return "off", "current frame is dark enough to classify as off"
    return "unclear", f"delta {delta:.3f} is not decisive"


def append_event(grow_dir: Path, event: dict) -> None:
    with (grow_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare latest grow capture with the previous one for light-state inference.")
    parser.add_argument("--grow", required=True)
    args = parser.parse_args()

    grow_dir, sidecars = load_sidecars(args.grow)
    current_path = sidecars[-1]
    current = json.loads(current_path.read_text(encoding="utf-8"))

    previous = None
    if len(sidecars) >= 2:
        previous = json.loads(sidecars[-2].read_text(encoding="utf-8"))

    current_brightness = float(current["brightness_mean"])
    previous_brightness = None if previous is None else float(previous["brightness_mean"])
    state, reason = classify(current_brightness, previous_brightness)

    result = {
        "timestamp": utc_now(),
        "grow_id": args.grow,
        "current_image_path": current["image_path"],
        "previous_image_path": None if previous is None else previous["image_path"],
        "current_brightness_mean": current_brightness,
        "previous_brightness_mean": previous_brightness,
        "light_state": state,
        "reason": reason,
        "ai_compare": {
            "status": "ready",
            "current_image_path": current["image_path"],
            "previous_image_path": None if previous is None else previous["image_path"],
            "question": current["ai_compare"]["question"],
        },
    }

    current["comparison"] = result
    current["ai_compare"] = result["ai_compare"]
    current_path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    append_event(
        grow_dir,
        {
            "ts": result["timestamp"],
            "kind": "light_compare",
            "message": f"latest capture inferred light_state={state}",
            "data": result,
        },
    )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
