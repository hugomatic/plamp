from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FRAME_SHAPES = (
    (-2, "outer", 120),
    (-1, "mid", 240),
    (0, "center", 360),
    (1, "mid", 240),
    (2, "outer", 120),
)
THUMB_HEIGHTS = {96, 120, 160, 240, 320, 360}
FINDER_HEIGHTS = {"hours": 320, "days": 160, "weeks": 96}


class RibbonError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class RibbonCapture:
    capture_id: str
    taken_at: datetime
    image_path: str | None = None

    def local(self, tz: datetime.tzinfo) -> datetime:
        return self.taken_at.astimezone(tz)


def parse_moment(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise RibbonError("at must be an ISO timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def captures_from_records(records: list[dict[str, Any]]) -> list[RibbonCapture]:
    captures: list[RibbonCapture] = []
    for record in records:
        capture_id = str(record.get("capture_id") or "").strip()
        timestamp = str(record.get("timestamp") or "").strip()
        if not capture_id or not timestamp:
            continue
        try:
            taken_at = parse_moment(timestamp)
        except RibbonError:
            continue
        image_path = record.get("image_path")
        captures.append(
            RibbonCapture(
                capture_id=capture_id,
                taken_at=taken_at,
                image_path=str(image_path) if image_path else None,
            )
        )
    captures.sort(key=lambda item: item.taken_at)
    return captures


def load_picks(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {"days": {}, "weeks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"days": {}, "weeks": {}}
    if not isinstance(payload, dict):
        return {"days": {}, "weeks": {}}
    return {
        "days": _string_map(payload.get("days")),
        "weeks": _string_map(payload.get("weeks")),
    }


def save_pick(path: Path, *, scale: str, key: str, capture_id: str) -> dict[str, dict[str, str]]:
    if scale not in {"day", "week"}:
        raise RibbonError("scale must be day or week")
    picks = load_picks(path)
    bucket = "days" if scale == "day" else "weeks"
    picks[bucket][key] = capture_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(picks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return picks


def ribbon_view(
    captures: list[RibbonCapture],
    *,
    at: datetime,
    tz: datetime.tzinfo,
    picks: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    moment = at.astimezone(tz).replace(minute=0, second=0, microsecond=0)
    chosen = picks or {"days": {}, "weeks": {}}
    by_id = {item.capture_id: item for item in captures}
    rows = [
        _row("hours", "hours", _hour_frames(captures, moment, tz)),
        _row("days", "days", _day_frames(captures, moment, tz, chosen, by_id)),
        _row("weeks", "weeks", _week_frames(captures, moment, tz, chosen, by_id)),
    ]
    empty = all(frame["capture_id"] is None for row in rows for frame in row["frames"])
    return {"at": moment.isoformat(timespec="seconds"), "empty": empty, "rows": rows}


def finder_view(
    captures: list[RibbonCapture],
    *,
    at: datetime,
    tz: datetime.tzinfo,
    picks: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    chosen = picks or {"days": {}, "weeks": {}}
    by_id = {item.capture_id: item for item in captures}
    anchor = _nearest_local(captures, at.astimezone(tz), tz)
    first_monday, total = _grow_weeks(captures, anchor, tz)
    weeks = _finder_weeks(captures, tz, chosen, by_id, first_monday, total)
    week_index = _index_of_monday(weeks, _monday(anchor.date()))
    selected_week = weeks[week_index]["key"] if weeks else _monday(anchor.date()).isoformat()
    days = _finder_days(captures, tz, chosen, by_id, datetime.fromisoformat(selected_week).date())
    day_index = _index_of_day(days, anchor.date())
    selected_day = datetime.fromisoformat(days[day_index]["key"]).date() if days else anchor.date()
    hours = _finder_hours(captures, tz, selected_day)
    hour_index = _index_of_hour(hours, anchor)
    _mark_selected(weeks, week_index, lambda frame: frame["week_label"])
    _mark_selected(days, day_index, lambda frame: frame["day_label"])
    _mark_selected(hours, hour_index, lambda frame: frame["hour_label"])
    return {
        "at": anchor.isoformat(timespec="seconds"),
        "empty": not captures,
        "lines": [
            {"scale": "hours", "height": FINDER_HEIGHTS["hours"], "index": hour_index, "frames": hours},
            {"scale": "days", "height": FINDER_HEIGHTS["days"], "index": day_index, "frames": days},
            {"scale": "weeks", "height": FINDER_HEIGHTS["weeks"], "index": week_index, "frames": weeks},
        ],
    }


def thumbnail_path(cache_dir: Path, capture_id: str, height: int) -> Path:
    if height not in THUMB_HEIGHTS:
        raise RibbonError("unsupported thumbnail height", 422)
    if not _safe_capture_id(capture_id):
        raise RibbonError("unknown capture", 404)
    return cache_dir / f"{capture_id}-{height}.jpg"


def ensure_thumbnail(source: Path, dest: Path, height: int) -> Path:
    if height not in THUMB_HEIGHTS:
        raise RibbonError("unsupported thumbnail height", 422)
    if not source.is_file():
        raise RibbonError("unknown capture", 404)
    if dest.is_file() and dest.stat().st_mtime >= source.stat().st_mtime:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    width = round(height * 16 / 9)
    if _resize_with_pillow(source, dest, width, height):
        return dest
    if _resize_with_ffmpeg(source, dest, width, height):
        return dest
    raise RibbonError("thumbnail support is not available", 503)


def pick_key(scale: str, at: datetime, tz: datetime.tzinfo) -> str:
    if scale not in {"day", "week"}:
        raise RibbonError("scale must be day or week")
    local = at.astimezone(tz)
    if scale == "day":
        return local.date().isoformat()
    return _monday(local.date()).isoformat()


def _nearest_local(captures: list[RibbonCapture], moment: datetime, tz: datetime.tzinfo) -> datetime:
    local = moment.astimezone(tz)
    if not captures:
        return local.replace(minute=0, second=0, microsecond=0)
    nearest = min(captures, key=lambda item: abs((item.local(tz) - local).total_seconds()))
    return nearest.local(tz).replace(minute=0, second=0, microsecond=0)


def _finder_weeks(captures, tz, picks, by_id, first_monday, total) -> list[dict[str, Any]]:
    mondays = sorted({_monday(item.local(tz).date()) for item in captures})
    frames = []
    height = FINDER_HEIGHTS["weeks"]
    for monday in mondays:
        capture = _picked(by_id, picks["weeks"].get(monday.isoformat())) or _capture_for_week(captures, monday, tz)
        if capture is None:
            continue
        index = ((monday - first_monday).days // 7) + 1
        frame = _frame(capture.local(tz), "finder", height, capture, None)
        frame["key"] = monday.isoformat()
        frame["week_label"] = f"week {index}/{total}"
        frames.append(frame)
    return frames


def _finder_days(captures, tz, picks, by_id, monday) -> list[dict[str, Any]]:
    week_end = monday + timedelta(days=7)
    days = sorted({item.local(tz).date() for item in captures if monday <= item.local(tz).date() < week_end})
    frames = []
    height = FINDER_HEIGHTS["days"]
    for day in days:
        capture = _picked(by_id, picks["days"].get(day.isoformat())) or _capture_near_noon(captures, day, tz)
        if capture is None:
            continue
        slot = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
        frame = _frame(capture.local(tz), "finder", height, capture, None)
        frame["key"] = day.isoformat()
        frame["day_label"] = _date_phrase(slot)
        frames.append(frame)
    return frames


def _finder_hours(captures, tz, day) -> list[dict[str, Any]]:
    grouped: dict[datetime, RibbonCapture] = {}
    for item in captures:
        local = item.local(tz)
        if local.date() != day:
            continue
        hour = local.replace(minute=0, second=0, microsecond=0)
        current = grouped.get(hour)
        if current is None or abs((local - hour).total_seconds()) < abs((current.local(tz) - hour).total_seconds()):
            grouped[hour] = item
    frames = []
    height = FINDER_HEIGHTS["hours"]
    for hour in sorted(grouped):
        capture = grouped[hour]
        frame = _frame(capture.local(tz), "finder", height, capture, None)
        frame["key"] = hour.isoformat(timespec="seconds")
        frame["hour_label"] = _hour_phrase(hour)
        frames.append(frame)
    return frames


def _index_of_monday(frames: list[dict[str, Any]], monday) -> int:
    key = monday.isoformat()
    for index, frame in enumerate(frames):
        if frame.get("key") == key:
            return index
    return 0


def _index_of_day(frames: list[dict[str, Any]], day) -> int:
    key = day.isoformat()
    for index, frame in enumerate(frames):
        if frame.get("key") == key:
            return index
    return 0


def _index_of_hour(frames: list[dict[str, Any]], moment: datetime) -> int:
    hour = moment.replace(minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    for index, frame in enumerate(frames):
        if frame.get("key") == hour:
            return index
    return 0


def _mark_selected(frames: list[dict[str, Any]], index: int, label_of) -> None:
    if not frames:
        return
    index = min(max(index, 0), len(frames) - 1)
    frames[index]["label"] = label_of(frames[index])
    frames[index]["selected"] = True


def _row(scale: str, label: str, frames: list[dict[str, Any]]) -> dict[str, Any]:
    return {"scale": scale, "label": label, "frames": frames}


def _hour_frames(captures: list[RibbonCapture], moment: datetime, tz: datetime.tzinfo) -> list[dict[str, Any]]:
    frames = []
    for offset, role, height in FRAME_SHAPES:
        slot = moment + timedelta(hours=offset)
        frames.append(_frame(slot, role, height, _capture_in_hour(captures, slot, tz), _hour_phrase(slot) if offset == 0 else None))
    return frames


def _day_frames(
    captures: list[RibbonCapture],
    moment: datetime,
    tz: datetime.tzinfo,
    picks: dict[str, dict[str, str]],
    by_id: dict[str, RibbonCapture],
) -> list[dict[str, Any]]:
    frames = []
    for offset, role, height in FRAME_SHAPES:
        day = (moment + timedelta(days=offset)).date()
        slot = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
        capture = _picked(by_id, picks["days"].get(day.isoformat())) or _capture_near_noon(captures, day, tz)
        label = _date_phrase(slot) if offset == 0 else None
        frames.append(_frame(slot, role, height, capture, label))
    return frames


def _week_frames(
    captures: list[RibbonCapture],
    moment: datetime,
    tz: datetime.tzinfo,
    picks: dict[str, dict[str, str]],
    by_id: dict[str, RibbonCapture],
) -> list[dict[str, Any]]:
    first_monday, total = _grow_weeks(captures, moment, tz)
    frames = []
    center_monday = _monday(moment.date())
    for offset, role, height in FRAME_SHAPES:
        monday = center_monday + timedelta(days=7 * offset)
        wednesday = monday + timedelta(days=2)
        slot = datetime(wednesday.year, wednesday.month, wednesday.day, 12, tzinfo=tz)
        capture = _picked(by_id, picks["weeks"].get(monday.isoformat())) or _capture_for_week(captures, monday, tz)
        index = ((monday - first_monday).days // 7) + 1
        label = f"week {index}/{total}" if offset == 0 else None
        frames.append(_frame(slot, role, height, capture, label))
    return frames


def _frame(slot: datetime, role: str, height: int, capture: RibbonCapture | None, label: str | None) -> dict[str, Any]:
    capture_id = capture.capture_id if capture else None
    thumb_url = f"/api/camera/ribbon/thumbs/{capture_id}?height={height}" if capture_id else None
    return {
        "role": role,
        "height": height,
        "at": slot.isoformat(timespec="seconds"),
        "capture_id": capture_id,
        "thumb_url": thumb_url,
        "label": label,
    }


def _capture_in_hour(captures: list[RibbonCapture], hour: datetime, tz: datetime.tzinfo) -> RibbonCapture | None:
    end = hour + timedelta(hours=1)
    found = [item for item in captures if hour <= item.local(tz) < end]
    if not found:
        return None
    return min(found, key=lambda item: abs((item.local(tz) - hour).total_seconds()))


def _capture_near_noon(captures: list[RibbonCapture], day: datetime.date, tz: datetime.tzinfo) -> RibbonCapture | None:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
    found = [item for item in captures if item.local(tz).date() == day]
    if not found:
        return None
    return min(found, key=lambda item: abs((item.local(tz) - noon).total_seconds()))


def _capture_for_week(captures: list[RibbonCapture], monday: datetime.date, tz: datetime.tzinfo) -> RibbonCapture | None:
    wednesday = monday + timedelta(days=2)
    exact = _capture_near_noon(captures, wednesday, tz)
    if exact is not None:
        return exact
    target = datetime(wednesday.year, wednesday.month, wednesday.day, 12, tzinfo=tz)
    week_end = monday + timedelta(days=7)
    found = [item for item in captures if monday <= item.local(tz).date() < week_end]
    if not found:
        return None
    return min(found, key=lambda item: abs((item.local(tz) - target).total_seconds()))


def _picked(by_id: dict[str, RibbonCapture], capture_id: str | None) -> RibbonCapture | None:
    if not capture_id:
        return None
    return by_id.get(capture_id)


def _grow_weeks(captures: list[RibbonCapture], moment: datetime, tz: datetime.tzinfo) -> tuple[datetime.date, int]:
    if not captures:
        monday = _monday(moment.date())
        return monday, 1
    dates = [item.local(tz).date() for item in captures]
    first = _monday(min(dates))
    last = _monday(max(dates))
    return first, ((last - first).days // 7) + 1


def _monday(day: datetime.date) -> datetime.date:
    return day - timedelta(days=day.weekday())


def _date_phrase(moment: datetime) -> str:
    return f"{MONTHS[moment.month - 1]} {moment.day}, {WEEKDAYS[moment.weekday()]}"


def _hour_phrase(moment: datetime) -> str:
    return f"{_date_phrase(moment)}, {moment.hour} hr"


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(key) and str(item)}


def _safe_capture_id(capture_id: str) -> bool:
    if not capture_id or len(capture_id) > 180:
        return False
    return all(character.isalnum() or character in {"-", "_", "."} for character in capture_id)


def _resize_with_pillow(source: Path, dest: Path, width: int, height: int) -> bool:
    interpreters = [sys.executable, "/usr/bin/python3"]
    script = (
        "import sys\n"
        "from PIL import Image\n"
        "source, dest, width, height = sys.argv[1:]\n"
        "with Image.open(source) as image:\n"
        "    frame = image.convert('RGB').resize((int(width), int(height)), Image.Resampling.LANCZOS)\n"
        "    frame.save(dest, 'JPEG', quality=70)\n"
    )
    seen: set[str] = set()
    for interpreter in interpreters:
        if interpreter in seen or not Path(interpreter).exists():
            continue
        seen.add(interpreter)
        completed = subprocess.run(
            [interpreter, "-c", script, str(source), str(dest), str(width), str(height)],
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0 and dest.is_file():
            return True
    return False


def _resize_with_ffmpeg(source: Path, dest: Path, width: int, height: int) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    completed = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-vf", f"scale={width}:{height}:flags=lanczos", str(dest)],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0 and dest.is_file()
