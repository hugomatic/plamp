import unittest

from plamp_web.pages import render_api_test_page, render_config_page, render_settings_page, render_timer_dashboard_page


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_page_links_to_config(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('<a href="/config">Config</a>', html)

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


    def test_settings_page_includes_git_software_identity(self):
        html = render_settings_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "tools": {"mpremote": None, "pyserial": "3.5"},
            "software": {
                "git_commit": "d5883da4abcdef",
                "git_short_commit": "d5883da",
                "git_branch": "main",
                "git_dirty": True,
            },
            "storage": {
                "path": "/home/hugo/.openclaw/workspace/code/plamp",
                "free": "42.0 GB",
                "used": "10.0 GB",
                "total": "52.0 GB",
            },
        })

        self.assertIn("Git commit", html)
        self.assertIn("d5883da", html)
        self.assertIn("Git branch", html)
        self.assertIn("main", html)
        self.assertIn("Git dirty", html)
        self.assertIn("yes", html)

    def test_settings_page_includes_detected_raspberry_pi_cameras(self):
        html = render_settings_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "tools": {"mpremote": None, "pyserial": "3.5"},
            "software": {"git_short_commit": "d5883da", "git_branch": "main", "git_dirty": False},
            "cameras": {"rpicam": [{"key": "rpicam:cam0", "connector": "cam0", "index": 0, "sensor": "imx708", "model": "imx708_wide", "lens": "wide", "path": "/base/imx708@1a"}]},
            "storage": {"path": "/tmp", "free": "42.0 GB", "used": "10.0 GB", "total": "52.0 GB"},
        })

        self.assertIn("Raspberry Pi cameras", html)
        self.assertIn("rpicam:cam0", html)
        self.assertIn("imx708_wide", html)
        self.assertIn("wide", html)

    def test_config_page_includes_form_rows_for_controllers_devices_and_cameras(self):
        html = render_config_page(
            {
                "controllers": {"pump_lights": {"pico_serial": "e66038b71387a039"}},
                "devices": {"pump": {"controller": "pump_lights", "pin": 3, "editor": "cycle"}},
                "cameras": {"rpicam_cam0": {}},
            },
            {"picos": [{"serial": "e66038b71387a039", "port": "/dev/ttyACM0"}], "cameras": [{"key": "rpicam:cam0", "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]},
        )

        self.assertIn("<title>Plamp config</title>", html)
        self.assertIn("<h2>Controllers</h2>", html)
        self.assertIn('data-controller-key="pump_lights"', html)
        self.assertIn('class="controller-id"', html)
        self.assertIn('value="pump_lights"', html)
        self.assertIn('class="controller-pico-serial"', html)
        self.assertIn('value="e66038b71387a039"', html)
        self.assertIn("/dev/ttyACM0", html)
        self.assertIn("<h2>Devices</h2>", html)
        self.assertIn('data-device-id="pump"', html)
        self.assertIn('class="device-controller"', html)
        self.assertIn('value="3"', html)
        self.assertIn("<h2>Cameras</h2>", html)
        self.assertIn('data-camera-key="rpicam_cam0"', html)
        self.assertIn('value="rpicam_cam0"', html)
        self.assertIn("Detected: imx708_wide wide", html)
        self.assertNotIn('data-camera-key="rpicam:cam0"', html)
        self.assertIn("Save controllers", html)
        self.assertIn("Save devices", html)
        self.assertIn("Save cameras", html)
        self.assertNotIn("<textarea", html)
        self.assertNotIn('class="controller-name"', html)
        self.assertNotIn('class="controller-type"', html)
        self.assertNotIn('class="device-name"', html)
        self.assertNotIn('class="device-type"', html)
        self.assertNotIn(">Default editor<", html)
        self.assertNotIn("default_editor", html)

    def test_config_page_posts_section_updates_from_forms(self):
        html = render_config_page({"controllers": {}, "devices": {}, "cameras": {}}, {"picos": [], "cameras": []})

        self.assertIn("collectControllers()", html)
        self.assertIn("collectDevices()", html)
        self.assertIn("collectCameras()", html)
        self.assertIn('"/api/config/controllers"', html)
        self.assertIn('"/api/config/devices"', html)
        self.assertIn('"/api/config/cameras"', html)
        self.assertIn('result[key] = {controller: row.querySelector(".device-controller").value, pin: Number(row.querySelector(".device-pin").value), editor: row.querySelector(".device-editor").value};', html)
        self.assertNotIn("default_editor", html)

    def test_config_page_includes_blank_rows_for_new_controller_and_device(self):
        html = render_config_page({"controllers": {}, "devices": {}, "cameras": {}}, {"picos": [], "cameras": []})

        self.assertIn('class="controller-row new-row" data-controller-key=""', html)
        self.assertIn('placeholder="pump_lights"', html)
        self.assertIn('class="device-row new-row" data-device-id=""', html)
        self.assertIn('placeholder="pump"', html)
        self.assertIn('class="camera-row new-row" data-camera-key=""', html)
        self.assertNotIn("No configured controllers", html)
        self.assertNotIn("No configured devices", html)

    def test_api_test_page_includes_config_routes(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for route in [
            "GET /api/config",
            "PUT /api/config/controllers",
            "PUT /api/config/devices",
            "PUT /api/config/cameras",
        ]:
            self.assertIn(f"<legend>{route}</legend>", html)
        self.assertIn('data-copy-target="get-config-curl-command"', html)
        self.assertIn('data-copy-target="put-config-devices-curl-command"', html)

    def test_api_test_page_uses_uniform_route_sections(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn("<title>Plamp API test</title>", html)
        for title in [
            "POST /api/camera/captures",
            "GET /api/camera/captures",
            "GET /api/timers/{role}",
            "GET /api/timers/{role}?stream=true",
            "PUT /api/timers/{role}",
        ]:
            self.assertIn(f"<legend>{title}</legend>", html)
        self.assertIn("Captures a new image and returns capture metadata.", html)
        self.assertIn("Lists captures newest first. Options: limit and offset.", html)
        self.assertIn("Reads the current timer state for one role.", html)
        self.assertIn("Streams timer events with server-sent events.", html)
        self.assertIn("Writes timer state JSON and sends it to the Pico.", html)
        self.assertIn('<p class="helper-title">Helper: Generate 5s pin test</p>', html)
        self.assertIn('<p class="helper-title">Helper: Generate pump/lights</p>', html)
        self.assertNotIn("Payload helpers", html)
        self.assertNotIn("<h3>Generate 5s pin test</h3>", html)
        self.assertNotIn("<h3>PUT curl</h3>", html)
        self.assertLess(
            html.index('<p class="helper-title">Helper: Generate 5s pin test</p>'),
            html.index("<label>JSON payload"),
        )

    def test_api_test_page_has_copyable_curl_commands_and_camera_paging_inputs(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for target in [
            "camera-capture-curl-command",
            "list-captures-curl-command",
            "get-curl-command",
            "stream-curl-command",
            "put-curl-command",
        ]:
            self.assertIn(f'data-copy-target="{target}"', html)
        self.assertIn('id="list-captures-limit"', html)
        self.assertIn('id="list-captures-offset"', html)
        self.assertIn("listCapturesLimit()", html)
        self.assertIn("listCapturesOffset()", html)
        self.assertIn("copyCurlCommand", html)
        self.assertIn("navigator.clipboard.writeText", html)
        self.assertIn("/api/camera/captures?limit=10&amp;offset=0", html)

    def test_api_test_page_keeps_timer_controls(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn('id="get-curl-command"', html)
        self.assertIn('id="stream-curl-command"', html)
        self.assertIn('id="put-curl-command"', html)


if __name__ == "__main__":
    unittest.main()
