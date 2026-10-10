import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from plamp_web.camera_ribbon import (
    RibbonError,
    captures_from_records,
    ensure_thumbnail,
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

    def test_thumbnail_is_written_on_demand_at_one_height(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "full.jpg"
            _write_sample_jpeg(source)
            dest = root / "thumb.jpg"
            ensure_thumbnail(source, dest, 288)
            self.assertTrue(dest.read_bytes().startswith(b"\xff\xd8"))
            sized = subprocess.run(
                ["/usr/bin/python3", "-c", "import sys\nfrom PIL import Image\nprint(Image.open(sys.argv[1]).size)", str(dest)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(sized.stdout.strip(), "(512, 288)")
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
