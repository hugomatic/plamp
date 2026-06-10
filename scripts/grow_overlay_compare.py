#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

STAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z")
DEFAULT_BRIGHTNESS_THRESHOLD = 20.0
DEFAULT_DAYLIGHT_HOURS_UTC = set(range(16, 24)) | set(range(0, 9))
DEFAULT_WIDTH = 1080
DEFAULT_JPG_QUALITY = 88


@dataclass(frozen=True)
class Capture:
    path: Path
    ts: datetime


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Create a phone-friendly vertical stack comparing month-ago, week-ago, and current grow captures.",
    )
    p.add_argument("--grow-dir", type=Path, required=True, help="Grow directory containing captures/")
    p.add_argument("--anchor", type=Path, help="Current image path. Defaults to latest daylight capture.")
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Output width in pixels. Default: 1080")
    p.add_argument("--jpg-quality", type=int, default=DEFAULT_JPG_QUALITY, help="JPEG quality. Default: 88")
    p.add_argument(
        "--output",
        type=Path,
        help="Output JPG path. Defaults to <grow-dir>/summaries/overlays/<anchor-date>/stack-month-week-today.jpg",
    )
    return p.parse_args()


def iter_captures(captures_dir: Path) -> Iterable[Capture]:
    for path in sorted(captures_dir.rglob("*.jpg")):
        match = STAMP_RE.search(path.name)
        if not match:
            continue
        stamp = f"{match.group(1)}T{match.group(2)}:{match.group(3)}:{match.group(4)}+00:00"
        yield Capture(path=path, ts=datetime.fromisoformat(stamp).astimezone(UTC))


def load_captures(grow_dir: Path) -> list[Capture]:
    captures_dir = grow_dir / "captures"
    if not captures_dir.is_dir():
        raise SystemExit(f"captures dir not found: {captures_dir}")
    captures = list(iter_captures(captures_dir))
    if not captures:
        raise SystemExit(f"no timestamped jpg captures found under: {captures_dir}")
    return captures


@lru_cache(maxsize=4096)
def image_brightness(path: Path) -> float:
    img = Image.open(path).convert("L").resize((64, 64))
    pixels = list(img.getdata())
    return sum(pixels) / len(pixels)


def is_daylight_capture(capture: Capture) -> bool:
    return image_brightness(capture.path) >= DEFAULT_BRIGHTNESS_THRESHOLD and capture.ts.hour in DEFAULT_DAYLIGHT_HOURS_UTC


def choose_anchor(captures: list[Capture], anchor_path: Path | None) -> Capture:
    if anchor_path is None:
        daylight = [c for c in captures if is_daylight_capture(c)]
        if daylight:
            return daylight[-1]
        bright = [c for c in captures if image_brightness(c.path) >= DEFAULT_BRIGHTNESS_THRESHOLD]
        if bright:
            return bright[-1]
        return captures[-1]
    resolved = anchor_path.resolve()
    for capture in captures:
        if capture.path.resolve() == resolved:
            return capture
    raise SystemExit(f"anchor not found in captures set: {anchor_path}")


def nearest_capture(captures: list[Capture], target: datetime) -> Capture:
    daylight = [c for c in captures if is_daylight_capture(c)]
    bright = [c for c in captures if image_brightness(c.path) >= DEFAULT_BRIGHTNESS_THRESHOLD]
    pool = daylight or bright or captures
    return min(pool, key=lambda c: (abs((c.ts - target).total_seconds()), abs(c.ts.hour - target.hour)))


def format_delta(older_ts: datetime, newer_ts: datetime) -> str:
    delta = newer_ts - older_ts
    total_hours = int(round(delta.total_seconds() / 3600))
    days, hours = divmod(total_hours, 24)
    if days and hours:
        return f"{days}d {hours}h apart"
    if days:
        return f"{days}d apart"
    return f"{hours}h apart"


def resize_to_width(img: Image.Image, width: int) -> Image.Image:
    if img.width == width:
        return img
    height = int(img.height * (width / img.width))
    return img.resize((width, height))


def add_panel_label(img: Image.Image, title: str, detail: str) -> Image.Image:
    font = ImageFont.load_default()
    draw_probe = ImageDraw.Draw(img)
    boxes = [draw_probe.textbbox((0, 0), line, font=font) for line in [title, detail]]
    pad = 10
    banner_h = sum(box[3] for box in boxes) + pad * 3
    canvas = Image.new("RGB", (img.width, img.height + banner_h), "white")
    canvas.paste(img, (0, banner_h))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, img.width, banner_h), fill="white")
    y = pad
    draw.text((pad, y), title, fill="black", font=font)
    y += boxes[0][3] + pad
    draw.text((pad, y), detail, fill=(60, 60, 60), font=font)
    return canvas


def build_panel(capture: Capture, title: str, detail: str, width: int) -> Image.Image:
    img = Image.open(capture.path).convert("RGB")
    img = resize_to_width(img, width)
    return add_panel_label(img, title, detail)


def main() -> None:
    args = parse_args()
    captures = load_captures(args.grow_dir)
    anchor = choose_anchor(captures, args.anchor)
    month = nearest_capture(captures, anchor.ts - timedelta(days=30))
    week = nearest_capture(captures, anchor.ts - timedelta(days=7))

    output_path = args.output
    if output_path is None:
        output_dir = args.grow_dir / "summaries" / "overlays" / anchor.ts.strftime("%Y-%m-%d")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "stack-month-week-today.jpg"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    panels = [
        build_panel(
            month,
            "MONTH AGO",
            f"{month.ts:%Y-%m-%d %H:%MZ} · {format_delta(month.ts, anchor.ts)}",
            args.width,
        ),
        build_panel(
            week,
            "LAST WEEK",
            f"{week.ts:%Y-%m-%d %H:%MZ} · {format_delta(week.ts, anchor.ts)}",
            args.width,
        ),
        build_panel(
            anchor,
            "TODAY",
            f"{anchor.ts:%Y-%m-%d %H:%MZ} · current daylight reference",
            args.width,
        ),
    ]

    total_height = sum(panel.height for panel in panels)
    stack = Image.new("RGB", (args.width, total_height), "#f4f4f4")
    y = 0
    for panel in panels:
        stack.paste(panel, (0, y))
        y += panel.height

    stack.save(output_path, quality=args.jpg_quality)

    manifest_path = output_path.with_suffix(".txt")
    manifest_path.write_text(
        "\n".join(
            [
                f"output: {output_path}",
                f"month: {month.path}",
                f"month_ts: {month.ts.isoformat()}",
                f"week: {week.path}",
                f"week_ts: {week.ts.isoformat()}",
                f"today: {anchor.path}",
                f"today_ts: {anchor.ts.isoformat()}",
                f"width: {args.width}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"output: {output_path}")
    print(f"month: {month.path}")
    print(f"week: {week.path}")
    print(f"today: {anchor.path}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
