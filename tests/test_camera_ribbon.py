import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from plamp_web.camera_ribbon import (
    RibbonError,
    captures_from_records,
    ensure_thumbnail,
    load_picks,
    pick_key,
    ribbon_view,
    save_pick,
)

HST = ZoneInfo("Pacific/Honolulu")


def capture(capture_id: str, local: str) -> dict[str, str]:
    taken = datetime.fromisoformat(local).replace(tzinfo=HST)
    return {"capture_id": capture_id, "timestamp": taken.isoformat(), "image_path": f"captures/{capture_id}.jpg"}


class CameraRibbonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.captures = captures_from_records(
            [
                capture("start", "2026-03-27T12:00:00"),
                capture("wed-noon", "2026-10-07T12:10:00"),
                capture("morning", "2026-10-09T08:00:00"),
                capture("noon", "2026-10-09T12:05:00"),
                capture("h14", "2026-10-09T14:20:00"),
                capture("h15", "2026-10-09T15:05:00"),
                capture("h16", "2026-10-09T16:40:00"),
                capture("h17", "2026-10-09T17:10:00"),
                capture("h18", "2026-10-09T18:00:00"),
            ]
        )
        self.at = datetime(2026, 10, 9, 16, 40, tzinfo=HST)

    def test_hour_row_is_five_frames_around_the_hour(self) -> None:
        view = ribbon_view(self.captures, at=self.at, tz=HST)
        hours = view["rows"][0]

        self.assertEqual([row["scale"] for row in view["rows"]], ["hours", "days", "weeks"])
        self.assertEqual([frame["role"] for frame in hours["frames"]], ["outer", "mid", "center", "mid", "outer"])
        self.assertEqual([frame["height"] for frame in hours["frames"]], [24, 48, 72, 48, 24])
        self.assertEqual([frame["capture_id"] for frame in hours["frames"]], ["h14", "h15", "h16", "h17", "h18"])
        self.assertEqual(hours["frames"][2]["label"], "Oct 9, Friday, 16 hr")
        self.assertIsNone(hours["frames"][0]["label"])
        self.assertEqual(hours["frames"][2]["thumb_url"], "/api/camera/ribbon/thumbs/h16?height=72")

    def test_missing_hour_stays_empty(self) -> None:
        view = ribbon_view(self.captures, at=datetime(2026, 10, 9, 13, tzinfo=HST), tz=HST)
        center = view["rows"][0]["frames"][2]

        self.assertIsNone(center["capture_id"])
        self.assertIsNone(center["thumb_url"])
        self.assertEqual(center["label"], "Oct 9, Friday, 13 hr")

    def test_day_and_week_rows_use_midday_until_a_pick(self) -> None:
        view = ribbon_view(self.captures, at=self.at, tz=HST)
        day = view["rows"][1]["frames"][2]
        week = view["rows"][2]["frames"][2]

        self.assertEqual(day["capture_id"], "noon")
        self.assertEqual(day["label"], "Oct 9, Friday")
        self.assertEqual(week["capture_id"], "wed-noon")
        self.assertEqual(week["label"], "week 29/29")

    def test_pick_replaces_the_midday_frame(self) -> None:
        picks = {"days": {"2026-10-09": "h16"}, "weeks": {"2026-10-05": "h18"}}
        view = ribbon_view(self.captures, at=self.at, tz=HST, picks=picks)

        self.assertEqual(view["rows"][1]["frames"][2]["capture_id"], "h16")
        self.assertEqual(view["rows"][2]["frames"][2]["capture_id"], "h18")

    def test_save_pick_remembers_the_day_and_week(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "picks.json"
            save_pick(path, scale="day", key=pick_key("day", self.at, HST), capture_id="h16")
            save_pick(path, scale="week", key=pick_key("week", self.at, HST), capture_id="h18")
            picks = load_picks(path)

        self.assertEqual(picks["days"]["2026-10-09"], "h16")
        self.assertEqual(picks["weeks"]["2026-10-05"], "h18")

    def test_thumbnail_is_written_on_demand_for_the_three_heights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "full.jpg"
            _write_sample_jpeg(source)
            dest = root / "thumb.jpg"
            ensure_thumbnail(source, dest, 24)
            self.assertTrue(dest.is_file())
            self.assertLess(dest.stat().st_size, source.stat().st_size)
            with self.assertRaises(RibbonError):
                ensure_thumbnail(source, root / "nope.jpg", 4)


def _write_sample_jpeg(path: Path) -> None:
    import subprocess

    script = (
        "import sys\n"
        "from PIL import Image\n"
        "image = Image.new('RGB', (160, 90), (40, 120, 50))\n"
        "image.save(sys.argv[1], 'JPEG', quality=90)\n"
    )
    completed = subprocess.run(["/usr/bin/python3", "-c", script, str(path)], capture_output=True, check=False)
    if completed.returncode != 0:
        raise unittest.SkipTest("system Pillow is unavailable")
