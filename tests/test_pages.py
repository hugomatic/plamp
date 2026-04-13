import unittest

from plamp_web.pages import render_api_test_page, render_settings_page, render_timer_dashboard_page


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_page_reloads_every_30_seconds(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('id="refresh-countdown"', html)
        self.assertIn("let refreshSeconds = 30;", html)
        self.assertIn("window.location.reload();", html)


    def test_timer_dashboard_page_includes_camera_capture_and_gallery_controls(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("<h2>Camera</h2>", html)
        self.assertIn('id="camera-capture"', html)
        self.assertIn('id="camera-capture-status"', html)
        self.assertIn('id="camera-capture-filter"', html)
        self.assertIn('id="camera-viewer"', html)
        self.assertIn('id="camera-capture-list"', html)
        self.assertIn('id="camera-capture-prev"', html)
        self.assertIn('id="camera-capture-next"', html)
        self.assertIn('fetch(`/api/camera/captures?limit=${cameraCapturePageSize}&offset=${cameraCaptureOffset}`)', html)
        self.assertIn("|| captures[0];", html)
        self.assertIn("selectCameraCapture(selected);", html)
        self.assertIn("cameraViewer.src = capture.image_url;", html)
        self.assertNotIn('id="camera-capture-grid"', html)
        self.assertNotIn('id="camera-capture-links"', html)
        self.assertNotIn("thumbnailCaptures", html)



    def test_timer_dashboard_capture_list_is_compact_and_scrollable(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn(".capture-list {", html)
        self.assertIn("max-height: 22rem;", html)
        self.assertIn("overflow-y: auto;", html)
        self.assertIn(".capture-list button:nth-child(even)", html)
        self.assertIn(".capture-list button:nth-child(odd)", html)
        self.assertIn("border: 0;", html)
        self.assertIn("border-left: 4px solid #174ea6;", html)
        self.assertIn("padding: .35rem .5rem;", html)

    def test_timer_dashboard_page_pauses_and_resumes_auto_reload_for_camera_interaction(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('id="refresh-status"', html)
        self.assertIn('id="resume-refresh"', html)
        self.assertIn("let pageRefreshTimer = window.setInterval(tickPageRefresh, 1000);", html)
        self.assertIn("function stopPageAutoRefresh()", html)
        self.assertIn("function startPageAutoRefresh()", html)
        self.assertIn("window.clearInterval(pageRefreshTimer);", html)
        self.assertIn('refreshStatus.textContent = "Auto-refresh paused.";', html)
        self.assertIn("resumeRefreshButton.hidden = false;", html)
        self.assertIn('resumeRefreshButton.addEventListener("click", startPageAutoRefresh);', html)
        self.assertIn('cameraCaptureList.addEventListener("click", stopPageAutoRefresh);', html)
        self.assertIn('cameraCaptureFilter.addEventListener("change", () => {', html)
        self.assertIn("stopPageAutoRefresh();", html)

    def test_timer_dashboard_filter_change_resets_capture_paging(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('cameraCaptureFilter.addEventListener("change", () => {', html)
        self.assertIn("cameraCaptureOffset = 0;", html)
        self.assertIn("refreshCameraCaptures();", html)


    def test_settings_page_includes_storage_summary(self):
        html = render_settings_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "tools": {"mpremote": None, "pyserial": "3.5"},
            "storage": {
                "path": "/home/hugo/.openclaw/workspace/code/plamp",
                "free": "42.0 GB",
                "used": "10.0 GB",
                "total": "52.0 GB",
            },
        })

        self.assertIn("<h2>Storage</h2>", html)
        self.assertIn("Free", html)
        self.assertIn("42.0 GB", html)
        self.assertIn("10.0 GB", html)
        self.assertIn("52.0 GB", html)

    def test_api_test_page_includes_camera_capture_controls(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn("<title>Plamp API test</title>", html)
        self.assertIn("POST /api/camera/captures", html)
        self.assertIn('id="camera-capture-curl-command"', html)
        self.assertIn('id="camera-capture"', html)
        self.assertIn('id="camera-capture-status"', html)
        self.assertIn('id="camera-capture-result"', html)
        self.assertIn('id="camera-capture-preview"', html)
        self.assertIn('id="list-captures-curl-command"', html)
        self.assertIn('id="list-captures"', html)
        self.assertIn('id="list-captures-result"', html)
        self.assertIn("GET /api/camera/captures", html)
        self.assertIn("/api/camera/captures?limit=10&offset=0", html)

    def test_api_test_page_keeps_timer_controls(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn('id="get-curl-command"', html)
        self.assertIn('id="stream-curl-command"', html)
        self.assertIn('id="put-curl-command"', html)


if __name__ == "__main__":
    unittest.main()
