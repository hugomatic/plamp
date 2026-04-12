import unittest

from plamp_web.pages import render_timer_dashboard_page


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_page_reloads_every_30_seconds(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('id="refresh-countdown"', html)
        self.assertIn("let refreshSeconds = 30;", html)
        self.assertIn("window.location.reload();", html)


if __name__ == "__main__":
    unittest.main()
