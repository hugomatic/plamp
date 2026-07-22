import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw

from plamp_web.grow_diagnostics import (
    Capture,
    choose_anchor,
    compute_region_metrics,
    generate_droop_diagnostics,
    nearest_capture,
)


class GrowDiagnosticsTests(unittest.TestCase):
    def make_image(self, path: Path, green_box: tuple[int, int, int, int], color=(30, 160, 40)) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (120, 120), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle(green_box, fill=color)
        img.save(path, quality=90)

    def test_compute_region_metrics_detects_lower_shift(self):
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((20, 55, 80, 95), fill=(40, 180, 50))

        metrics = compute_region_metrics(img)

        self.assertGreater(metrics.coverage_ratio, 0.20)
        self.assertIsNotNone(metrics.centroid_y)
        self.assertGreater(metrics.centroid_y, 0.65)
        self.assertGreater(metrics.lower_ratio, metrics.upper_ratio)
        self.assertGreater(metrics.lower_minus_upper, 0)

    def test_anchor_and_nearest_capture_prefer_daylight_images(self):
        captures = [
            Capture(path=Path("/tmp/night.jpg"), ts=datetime(2026, 6, 26, 11, 0, tzinfo=UTC)),
            Capture(path=Path("/tmp/day1.jpg"), ts=datetime(2026, 6, 26, 20, 0, tzinfo=UTC)),
            Capture(path=Path("/tmp/day2.jpg"), ts=datetime(2026, 6, 27, 21, 0, tzinfo=UTC)),
        ]

        import plamp_web.grow_diagnostics as gd

        original = gd.image_brightness
        try:
            gd.image_brightness = lambda path: 5.0 if "night" in str(path) else 50.0
            anchor = choose_anchor(captures, None)
            self.assertEqual(anchor.path.name, "day2.jpg")
            nearest = nearest_capture(captures, datetime(2026, 6, 19, 22, 0, tzinfo=UTC))
            self.assertIn(nearest.path.name, {"day1.jpg", "day2.jpg"})
            self.assertNotEqual(nearest.path.name, "night.jpg")
        finally:
            gd.image_brightness = original

    def test_generate_droop_diagnostics_writes_expected_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grow = root / "grow-basil"
            self.make_image(grow / "captures/2026-05-27/auto-rpicam_cam0-2026-05-27T21-02-36Z-aaaaaa.jpg", (75, 15, 112, 42))
            self.make_image(grow / "captures/2026-06-19/auto-rpicam_cam0-2026-06-19T21-28-48Z-bbbbbb.jpg", (72, 18, 113, 54))
            self.make_image(grow / "captures/2026-06-26/auto-rpicam_cam0-2026-06-26T21-11-07Z-cccccc.jpg", (68, 20, 115, 65))

            report = generate_droop_diagnostics(grow)
            outdir = Path(report["output_dir"])

            self.assertTrue((outdir / "droop-reference-boxes.jpg").exists())
            self.assertTrue((outdir / "droop-evolution-crops.jpg").exists())
            self.assertTrue((outdir / "droop-context-stack.jpg").exists())
            self.assertTrue((outdir / "droop-evolution-report.json").exists())
            self.assertTrue((outdir / "droop-evolution-notes.md").exists())

            data = json.loads((outdir / "droop-evolution-report.json").read_text(encoding="utf-8"))
            self.assertEqual(data["sources"]["today"]["path"], str(grow / "captures/2026-06-26/auto-rpicam_cam0-2026-06-26T21-11-07Z-cccccc.jpg"))
            self.assertEqual([region["key"] for region in data["regions"]], ["A", "B", "C"])
            self.assertIn(data["regions"][0]["evidence_tag"], {"more mass and lower spillover", "mixed change", "stable posture", "lower-hanging posture without much mass gain"})


if __name__ == "__main__":
    unittest.main()
