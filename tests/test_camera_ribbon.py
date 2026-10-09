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
        self.assertEqual([frame["height"] for frame in hours["frames"]], [120, 240, 360, 240, 120])
        self.assertEqual([frame["capture_id"] for frame in hours["frames"]], ["h14", "h15", "h16", "h17", "h18"])
        self.assertEqual(hours["frames"][2]["label"], "Oct 9, Friday, 16 hr")
        self.assertIsNone(hours["frames"][0]["label"])
        self.assertEqual(hours["frames"][2]["thumb_url"], "/api/camera/ribbon/thumbs/h16?height=360")

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

    def test_finder_lists_only_pictures_that_exist(self) -> None:
        from plamp_web.camera_ribbon import finder_view

        view = finder_view(self.captures, at=datetime(2026, 10, 9, 16, 10, tzinfo=HST), tz=HST, now=datetime(2026, 10, 9, 18, tzinfo=HST))
        lines = {line["scale"]: line for line in view["lines"]}
        hours = lines["hours"]
        days = lines["days"]
        weeks = lines["weeks"]
        day_number = (datetime(2026, 10, 9).date() - datetime(2026, 3, 27).date()).days + 1

        self.assertEqual([line["scale"] for line in view["lines"]], ["hours", "days", "weeks"])
        self.assertEqual(len(hours["frames"]), 24)
        self.assertIsNone(hours["frames"][13]["capture_id"])
        self.assertEqual(hours["frames"][hours["index"]]["capture_id"], "h16")
        self.assertEqual(hours["label"], "hours 16/24")
        self.assertEqual(len(days["frames"]), 7)
        self.assertEqual(days["label"], "days 5/7")
        self.assertIsNone(days["frames"][0]["capture_id"])
        self.assertEqual(days["frames"][2]["capture_id"], "wed-noon")
        self.assertEqual(days["frames"][4]["capture_id"], "noon")
        self.assertIsNone(days["frames"][6]["capture_id"])
        self.assertEqual(len(weeks["frames"]), 29)
        self.assertEqual(weeks["frames"][0]["slider_label"], "weeks 01/29")
        self.assertEqual(weeks["label"], "weeks 29/29")
        self.assertIsNone(weeks["frames"][1]["capture_id"])
        self.assertEqual(view["detail"], f"Friday, October 9, 2026, 16 hr, day {day_number}, today")

    def test_finder_hour_slider_keeps_extra_pictures_and_empty_hours(self) -> None:
        from plamp_web.camera_ribbon import finder_view

        captures = captures_from_records(
            [
                capture("morning", "2026-10-09T08:00:00"),
                capture("extra", "2026-10-09T08:20:00"),
                capture("later", "2026-10-09T08:40:00"),
            ]
        )
        view = finder_view(captures, at=datetime(2026, 10, 9, 8, 40, tzinfo=HST), tz=HST, now=datetime(2026, 10, 9, 18, tzinfo=HST))
        hours = next(line for line in view["lines"] if line["scale"] == "hours")
        taken = [frame["capture_id"] for frame in hours["frames"] if frame["capture_id"]]

        self.assertEqual(len(hours["frames"]), 26)
        self.assertEqual(taken, ["morning", "extra", "later"])
        self.assertEqual(hours["frames"][hours["index"]]["capture_id"], "later")
        self.assertIsNone(hours["frames"][0]["capture_id"])
        self.assertEqual(hours["frames"][-1]["slider_label"], "hours 23/24")

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
            ensure_thumbnail(source, dest, 120)
            self.assertTrue(dest.read_bytes().startswith(b"\xff\xd8"))
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
