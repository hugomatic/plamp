from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

STAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z")
DEFAULT_BRIGHTNESS_THRESHOLD = 20.0
DEFAULT_DAYLIGHT_HOURS_UTC = set(range(16, 24)) | set(range(0, 9))
DEFAULT_WIDTH = 1080
DEFAULT_JPG_QUALITY = 88
GREEN_HUE_MIN = 28
GREEN_HUE_MAX = 110
GREEN_SAT_MIN = 40
GREEN_VAL_MIN = 25


@dataclass(frozen=True)
class Capture:
    path: Path
    ts: datetime


@dataclass(frozen=True)
class Region:
    key: str
    title: str
    description: str
    box: tuple[float, float, float, float]
    color: tuple[int, int, int]


@dataclass(frozen=True)
class RegionMetrics:
    coverage_ratio: float
    centroid_y: float | None
    upper_ratio: float
    lower_ratio: float
    lower_minus_upper: float


DEFAULT_REGIONS: tuple[Region, ...] = (
    Region(
        key="A",
        title="Top-right edge",
        description="edge leaves + terminal cluster",
        box=(0.72, 0.12, 0.95, 0.34),
        color=(255, 80, 80),
    ),
    Region(
        key="B",
        title="Upper-center band",
        description="leaf angle under top rail",
        box=(0.38, 0.16, 0.68, 0.40),
        color=(80, 180, 255),
    ),
    Region(
        key="C",
        title="Mid-right curtain",
        description="dense hanging sheet / spillover",
        box=(0.62, 0.36, 0.88, 0.70),
        color=(255, 190, 60),
    ),
)


@lru_cache(maxsize=4096)
def image_brightness(path: Path) -> float:
    img = Image.open(path).convert("L").resize((64, 64))
    pixels = list(img.getdata())
    return sum(pixels) / len(pixels)


@lru_cache(maxsize=256)
def _load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


@lru_cache(maxsize=256)
def _load_hsv(path: Path) -> Image.Image:
    return _load_rgb(path).convert("HSV")


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


def is_daylight_capture(capture: Capture) -> bool:
    return image_brightness(capture.path) >= DEFAULT_BRIGHTNESS_THRESHOLD and capture.ts.hour in DEFAULT_DAYLIGHT_HOURS_UTC


def choose_anchor(captures: Sequence[Capture], anchor_path: Path | None) -> Capture:
    if anchor_path is None:
        hour_candidates = [c for c in captures if c.ts.hour in DEFAULT_DAYLIGHT_HOURS_UTC]
        recent = hour_candidates[-24:] or list(captures)[-24:]
        bright_recent = [c for c in recent if image_brightness(c.path) >= DEFAULT_BRIGHTNESS_THRESHOLD]
        if bright_recent:
            return bright_recent[-1]
        return recent[-1]
    resolved = anchor_path.resolve()
    for capture in captures:
        if capture.path.resolve() == resolved:
            return capture
    raise SystemExit(f"anchor not found in captures set: {anchor_path}")


def nearest_capture(captures: Sequence[Capture], target: datetime) -> Capture:
    shortlist = sorted(
        captures,
        key=lambda c: (abs((c.ts - target).total_seconds()), abs(c.ts.hour - target.hour)),
    )[:48]
    hour_candidates = [c for c in shortlist if c.ts.hour in DEFAULT_DAYLIGHT_HOURS_UTC]
    bright_candidates = [c for c in hour_candidates if image_brightness(c.path) >= DEFAULT_BRIGHTNESS_THRESHOLD]
    pool = bright_candidates or hour_candidates or shortlist
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


def crop_box(size: tuple[int, int], box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = size
    x1 = int(box[0] * width)
    y1 = int(box[1] * height)
    x2 = int(box[2] * width)
    y2 = int(box[3] * height)
    return x1, y1, x2, y2


def green_mask(img: Image.Image) -> list[bool]:
    hsv = img.convert("HSV")
    mask: list[bool] = []
    for h, s, v in hsv.getdata():
        mask.append(GREEN_HUE_MIN <= h <= GREEN_HUE_MAX and s >= GREEN_SAT_MIN and v >= GREEN_VAL_MIN)
    return mask


def compute_region_metrics(img: Image.Image) -> RegionMetrics:
    width, height = img.size
    mask = green_mask(img)
    total = width * height
    green_indices = [i for i, ok in enumerate(mask) if ok]
    if not green_indices:
        return RegionMetrics(coverage_ratio=0.0, centroid_y=None, upper_ratio=0.0, lower_ratio=0.0, lower_minus_upper=0.0)
    ys = [idx // width for idx in green_indices]
    coverage_ratio = len(green_indices) / total
    centroid_y = sum(ys) / len(ys) / max(1, height - 1)
    half = height / 2
    upper = sum(1 for y in ys if y < half)
    lower = len(ys) - upper
    upper_ratio = upper / total
    lower_ratio = lower / total
    return RegionMetrics(
        coverage_ratio=coverage_ratio,
        centroid_y=centroid_y,
        upper_ratio=upper_ratio,
        lower_ratio=lower_ratio,
        lower_minus_upper=lower_ratio - upper_ratio,
    )


def classify_region_evolution(month: RegionMetrics, week: RegionMetrics, today: RegionMetrics) -> str:
    coverage_gain = today.coverage_ratio - month.coverage_ratio
    lower_shift = (today.lower_minus_upper - month.lower_minus_upper)
    centroid_shift = None
    if month.centroid_y is not None and today.centroid_y is not None:
        centroid_shift = today.centroid_y - month.centroid_y

    if coverage_gain >= 0.05 and lower_shift >= 0.03:
        return "more mass and lower spillover"
    if centroid_shift is not None and centroid_shift >= 0.05 and coverage_gain <= 0.02:
        return "lower-hanging posture without much mass gain"
    if centroid_shift is not None and abs(centroid_shift) < 0.03 and abs(today.coverage_ratio - week.coverage_ratio) < 0.03:
        return "stable posture"
    return "mixed change"


def metrics_text(metrics: RegionMetrics) -> str:
    centroid = "n/a" if metrics.centroid_y is None else f"{metrics.centroid_y:.2f}"
    return f"cover {metrics.coverage_ratio:.2f}  center_y {centroid}"


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
    img = _load_rgb(capture.path)
    img = resize_to_width(img, width)
    return add_panel_label(img, title, detail)


def render_reference_image(img: Image.Image, regions: Sequence[Region]) -> Image.Image:
    ref = img.copy()
    draw = ImageDraw.Draw(ref)
    font = ImageFont.load_default()
    for region in regions:
        x1, y1, x2, y2 = crop_box(ref.size, region.box)
        draw.rectangle((x1, y1, x2, y2), outline=region.color, width=8)
        draw.rectangle((x1, max(0, y1 - 22), x1 + 36, y1), fill=region.color)
        draw.text((x1 + 8, max(0, y1 - 18)), region.key, fill="black", font=font)
    return ref


def build_crop_row(region: Region, panels: Sequence[tuple[str, Image.Image]], metrics_by_panel: dict[str, RegionMetrics], crop_width: int = 320, pad: int = 18) -> Image.Image:
    font = ImageFont.load_default()
    label_h = 42
    row_title_h = 28
    metric_h = 20
    crops: list[Image.Image] = []
    for panel_title, img in panels:
        x1, y1, x2, y2 = crop_box(img.size, region.box)
        crop = img.crop((x1, y1, x2, y2))
        crop.thumbnail((crop_width, 9999))
        metrics = metrics_by_panel[panel_title]
        canvas = Image.new("RGB", (crop_width, crop.height + label_h + metric_h), "white")
        x = (crop_width - crop.width) // 2
        canvas.paste(crop, (x, label_h))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, crop_width, label_h), fill=region.color)
        draw.text((10, 8), panel_title, fill="black", font=font)
        draw.text((10, label_h + crop.height + 4), metrics_text(metrics), fill=(70, 70, 70), font=font)
        crops.append(canvas)
    row_h = max(crop.height for crop in crops)
    row = Image.new("RGB", (crop_width * len(crops) + pad * (len(crops) - 1), row_title_h + row_h), "#f6f6f6")
    draw = ImageDraw.Draw(row)
    draw.text((0, 4), f"{region.key} {region.title} - {region.description}", fill="black", font=font)
    x = 0
    for crop in crops:
        row.paste(crop, (x, row_title_h))
        x += crop_width + pad
    return row


def build_crop_board(panels: Sequence[tuple[str, Image.Image]], region_metrics: dict[str, dict[str, RegionMetrics]], regions: Sequence[Region]) -> Image.Image:
    font = ImageFont.load_default()
    rows = [build_crop_row(region, panels, region_metrics[region.key]) for region in regions]
    pad = 18
    header_h = 48
    board_w = max(row.width for row in rows)
    board_h = header_h + sum(row.height for row in rows) + pad * (len(rows) - 1)
    board = Image.new("RGB", (board_w, board_h), "white")
    draw = ImageDraw.Draw(board)
    draw.text((0, 6), "Basil droop evolution crops", fill="black", font=font)
    draw.text((0, 24), "Same regions across month/week/today with simple region metrics", fill=(80, 80, 80), font=font)
    y = header_h
    for row in rows:
        board.paste(row, (0, y))
        y += row.height + pad
    return board


def diagnostics_output_dir(grow_dir: Path, anchor: Capture, output_dir: Path | None) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    target = grow_dir / "summaries" / "diagnostics" / anchor.ts.strftime("%Y-%m-%d")
    target.mkdir(parents=True, exist_ok=True)
    return target


def generate_droop_diagnostics(
    grow_dir: Path,
    anchor_path: Path | None = None,
    output_dir: Path | None = None,
    width: int = DEFAULT_WIDTH,
    jpg_quality: int = DEFAULT_JPG_QUALITY,
    regions: Sequence[Region] = DEFAULT_REGIONS,
) -> dict[str, object]:
    captures = load_captures(grow_dir)
    anchor = choose_anchor(captures, anchor_path)
    month = nearest_capture(captures, anchor.ts - timedelta(days=30))
    week = nearest_capture(captures, anchor.ts - timedelta(days=7))
    outdir = diagnostics_output_dir(grow_dir, anchor, output_dir)

    panels = [
        (
            "MONTH AGO",
            _load_rgb(month.path),
        ),
        (
            "LAST WEEK",
            _load_rgb(week.path),
        ),
        (
            "TODAY",
            _load_rgb(anchor.path),
        ),
    ]

    reference = render_reference_image(panels[-1][1], regions)
    reference_path = outdir / "droop-reference-boxes.jpg"
    reference.save(reference_path, quality=jpg_quality)

    region_metrics: dict[str, dict[str, RegionMetrics]] = {}
    for region in regions:
        per_panel: dict[str, RegionMetrics] = {}
        for panel_title, img in panels:
            x1, y1, x2, y2 = crop_box(img.size, region.box)
            per_panel[panel_title] = compute_region_metrics(img.crop((x1, y1, x2, y2)))
        region_metrics[region.key] = per_panel

    crop_board = build_crop_board(panels, region_metrics, regions)
    crop_board_path = outdir / "droop-evolution-crops.jpg"
    crop_board.save(crop_board_path, quality=jpg_quality)

    summary_stack = Image.new("RGB", (width, sum(panel.height for panel in [
        build_panel(month, "MONTH AGO", f"{month.ts:%Y-%m-%d %H:%MZ} · {format_delta(month.ts, anchor.ts)}", width),
        build_panel(week, "LAST WEEK", f"{week.ts:%Y-%m-%d %H:%MZ} · {format_delta(week.ts, anchor.ts)}", width),
        build_panel(anchor, "TODAY", f"{anchor.ts:%Y-%m-%d %H:%MZ} · current daylight reference", width),
    ])), "#f4f4f4")
    stacked_panels = [
        build_panel(month, "MONTH AGO", f"{month.ts:%Y-%m-%d %H:%MZ} · {format_delta(month.ts, anchor.ts)}", width),
        build_panel(week, "LAST WEEK", f"{week.ts:%Y-%m-%d %H:%MZ} · {format_delta(week.ts, anchor.ts)}", width),
        build_panel(anchor, "TODAY", f"{anchor.ts:%Y-%m-%d %H:%MZ} · current daylight reference", width),
    ]
    y = 0
    for panel in stacked_panels:
        summary_stack.paste(panel, (0, y))
        y += panel.height
    summary_stack_path = outdir / "droop-context-stack.jpg"
    summary_stack.save(summary_stack_path, quality=jpg_quality)

    report = {
        "output_dir": str(outdir),
        "reference_image": str(reference_path),
        "crop_board": str(crop_board_path),
        "context_stack": str(summary_stack_path),
        "sources": {
            "month": {"path": str(month.path), "ts": month.ts.isoformat()},
            "week": {"path": str(week.path), "ts": week.ts.isoformat()},
            "today": {"path": str(anchor.path), "ts": anchor.ts.isoformat()},
        },
        "regions": [],
    }

    lines = [
        "# Droop evolution diagnostics",
        "",
        f"Reference image: `{reference_path}`",
        f"Crop board: `{crop_board_path}`",
        f"Context stack: `{summary_stack_path}`",
        "",
        "## Source images",
        f"- month ago: `{month.path}`",
        f"- last week: `{week.path}`",
        f"- today: `{anchor.path}`",
        "",
        "## Region summaries",
    ]

    for region in regions:
        month_metrics = region_metrics[region.key]["MONTH AGO"]
        week_metrics = region_metrics[region.key]["LAST WEEK"]
        today_metrics = region_metrics[region.key]["TODAY"]
        evidence_tag = classify_region_evolution(month_metrics, week_metrics, today_metrics)
        region_report = {
            "key": region.key,
            "title": region.title,
            "description": region.description,
            "box": list(region.box),
            "evidence_tag": evidence_tag,
            "metrics": {
                "month": asdict(month_metrics),
                "week": asdict(week_metrics),
                "today": asdict(today_metrics),
            },
        }
        report["regions"].append(region_report)
        lines.extend(
            [
                f"- {region.key} {region.title}: {evidence_tag}",
                f"  - month: {metrics_text(month_metrics)}",
                f"  - week: {metrics_text(week_metrics)}",
                f"  - today: {metrics_text(today_metrics)}",
            ]
        )

    report_path = outdir / "droop-evolution-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    notes_path = outdir / "droop-evolution-notes.md"
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create fixed-region droop diagnostics comparing month-ago, week-ago, and current grow captures.",
    )
    parser.add_argument("--grow-dir", type=Path, required=True, help="Grow directory containing captures/")
    parser.add_argument("--anchor", type=Path, help="Current image path. Defaults to latest daylight capture.")
    parser.add_argument("--output-dir", type=Path, help="Output directory. Defaults to <grow-dir>/summaries/diagnostics/<anchor-date>")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"Context stack width in pixels. Default: {DEFAULT_WIDTH}")
    parser.add_argument("--jpg-quality", type=int, default=DEFAULT_JPG_QUALITY, help=f"JPEG quality. Default: {DEFAULT_JPG_QUALITY}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = generate_droop_diagnostics(
        grow_dir=args.grow_dir,
        anchor_path=args.anchor,
        output_dir=args.output_dir,
        width=args.width,
        jpg_quality=args.jpg_quality,
    )
    print(f"output_dir: {report['output_dir']}")
    print(f"reference_image: {report['reference_image']}")
    print(f"crop_board: {report['crop_board']}")
    print(f"context_stack: {report['context_stack']}")
    print(f"report: {Path(report['output_dir']) / 'droop-evolution-report.json'}")


if __name__ == "__main__":
    main()
