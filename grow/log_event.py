#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GROWS_DIR = REPO_ROOT / "grow" / "grows"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_grow_dir(grow_id: str) -> Path:
    grow_dir = GROWS_DIR / grow_id
    grow_file = grow_dir / "grow.json"
    if not grow_file.exists():
        raise SystemExit(f"missing grow config: {grow_file}")
    return grow_dir


def append_event(grow_dir: Path, event: dict) -> Path:
    path = grow_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one structured grow event.")
    parser.add_argument("--grow", required=True, help="grow id, for example grow-thai-basil-siam-queen-2026-03-27")
    parser.add_argument("--kind", required=True, help="event kind, for example capture or note")
    parser.add_argument("--message", required=True, help="short human-readable message")
    parser.add_argument("--data", default=None, help="optional JSON object string with extra data")
    args = parser.parse_args()

    grow_dir = load_grow_dir(args.grow)
    payload = None
    if args.data:
        payload = json.loads(args.data)
        if not isinstance(payload, dict):
            raise SystemExit("--data must decode to a JSON object")

    event = {
        "ts": utc_now(),
        "kind": args.kind,
        "message": args.message,
    }
    if payload:
        event["data"] = payload

    path = append_event(grow_dir, event)
    print(path)
    print(json.dumps(event, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
