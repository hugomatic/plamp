import unittest

from plamp_web.pages import render_api_test_page, render_settings_page, render_timer_dashboard_page


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_page_links_to_settings(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('<a href="/settings">Settings</a>', html)
        self.assertNotIn('href="/config"', html)

    def test_timer_dashboard_page_reloads_every_30_seconds(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('id="refresh-countdown"', html)
        self.assertIn("let refreshSeconds = 30;", html)
        self.assertIn("window.location.reload();", html)

    def test_timer_dashboard_page_uses_server_schedule_success_message(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('showEditorMessage(message, "editor-success", parsed?.message || "Schedule applied. Waiting for report...");', html)

    def test_timer_dashboard_page_places_editor_under_active_timer_and_pauses_refresh(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("let activeEditor = null;", html)
        self.assertIn("function openScheduleEditor(role, channel, event) {", html)
        self.assertIn("activeEditor = {role, channelId: channel.id};", html)
        self.assertIn("stopPageAutoRefresh();", html)
        self.assertIn("activeEditor = null;", html)
        self.assertIn('edit.addEventListener("click", () => openScheduleEditor(role, channel, event));', html)
        self.assertIn("if (activeEditor && activeEditor.role === role && activeEditor.channelId === channel.id) {", html)
        self.assertIn("timerBoard.append(timerEditorPanel);", html)

    def test_timer_dashboard_page_preserves_editor_focus_on_timer_updates(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("let pendingTimerRender = false;", html)
        self.assertIn("function flushPendingTimerRender() {", html)
        self.assertIn("if (activeEditor && timerEditorPanel.contains(document.activeElement)) {", html)
        self.assertIn("pendingTimerRender = true;", html)
        self.assertIn('form.addEventListener("focusout", () => window.setTimeout(flushPendingTimerRender, 0));', html)

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

    def test_timer_dashboard_page_ignores_unconfigured_runtime_pins(self):
        html = render_timer_dashboard_page(
            ["pump_lights"],
            "12h",
            {
                "pump_lights": [
                    {"role": "pump_lights", "id": "pump", "name": "pump", "pin": 2, "type": "gpio", "default_editor": "cycle"},
                    {"role": "pump_lights", "id": "lights", "name": "lights", "pin": 3, "type": "gpio", "default_editor": "clock_window"},
                ]
            },
            0,
        )

        self.assertIn("const liveByPin = new Map();", html)
        self.assertIn("const byPin = channels.find((channel) => Number(channel.pin) === eventPin);", html)
        self.assertIn("channels.map((channel) => ({channel, event: liveByPin.get(Number(channel.pin)), index: 0}))", html)
        self.assertIn("const event = item.event || {id: channel.id, ch: channel.pin, type: channel.type || \"gpio\"};", html)


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
        self.assertIn("<th>Camera</th>", html)
        self.assertIn("cam0", html)
        self.assertNotIn("<th>Key</th>", html)
        self.assertIn("Camera Module 3 Wide", html)
        self.assertIn("imx708", html)
        self.assertIn("wide", html)

    def test_settings_page_includes_plamp_setup_system_status_and_device_control(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"pump_lights": {"pico_serial": "abc", "label": "Pump lights"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 2, "editor": "cycle", "label": "Main pump"}},
                    "cameras": {"rpicam_cam0": {"label": "Tent cam"}},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": [{"key": "rpicam:cam0", "model": "imx708", "lens": "wide"}]},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("Plamp config", html)
        self.assertIn("System status", html)
        self.assertIn("Device control", html)
        self.assertIn("<th>Label</th>", html)
        self.assertIn("Peripherals", html)
        self.assertIn("<th>Port</th><th>USB Device</th><th>Serial</th><th>USB ID</th>", html)
        self.assertNotIn("<th>Role</th>", html)
        self.assertIn("Pump lights", html)
        self.assertIn("Main pump", html)
        self.assertIn("Tent cam", html)
        self.assertIn('href="/settings"', html)
        self.assertIn('href="/api/test"', html)
        self.assertNotIn('href="/config"', html)

    def test_settings_page_preserves_config_order_for_setup_rows(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"second": {"pico_serial": "2"}, "first": {"pico_serial": "1"}},
                    "devices": {
                        "lights": {"controller": "second", "pin": 3, "editor": "clock_window"},
                        "pump": {"controller": "second", "pin": 2, "editor": "cycle"},
                    },
                    "cameras": {},
                },
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        self.assertLess(html.index('data-controller-key="second"'), html.index('data-controller-key="first"'))
        self.assertLess(html.index('data-device-id="lights"'), html.index('data-device-id="pump"'))

    def test_settings_page_posts_config_section_updates_from_forms(self):
        html = render_settings_page({"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}})

        self.assertIn("collectControllers()", html)
        self.assertIn("collectDevices()", html)
        self.assertIn("collectCameras()", html)
        self.assertIn("function controllerRenames()", html)
        self.assertIn("collectConfigWithControllerRenames()", html)
        self.assertIn('saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())', html)
        self.assertIn('"/api/config/devices"', html)
        self.assertIn('"/api/config/cameras"', html)
        self.assertIn('label: row.querySelector(".device-label").value.trim()', html)
        self.assertIn('label: row.querySelector(".controller-label").value.trim()', html)
        self.assertIn('label: row.querySelector(".camera-label").value.trim()', html)
        self.assertIn('const pinValue = row.querySelector(".device-pin").value', html)
        self.assertIn('pin: Number(pinValue)', html)
        self.assertIn("if (response.ok) window.location.reload();", html)
        self.assertIn("throw new Error(`Pin required for device ${key}.`);", html)
        self.assertIn('try {', html)
        self.assertIn('catch (error)', html)

    def test_settings_page_includes_blank_rows_for_new_controller_device_and_camera(self):
        html = render_settings_page({"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}})

        self.assertIn('class="controller-row new-row" data-controller-key=""', html)
        self.assertIn('placeholder="pump_lights"', html)
        self.assertIn('class="device-row new-row" data-device-id=""', html)
        self.assertIn('placeholder="pump"', html)
        self.assertIn('class="camera-row new-row" data-camera-key=""', html)

    def test_settings_page_includes_hostname_confirm_apply_controls(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('id="hostname-input"', html)
        self.assertIn('id="hostname-confirm"', html)
        self.assertIn('id="hostname-status"', html)
        self.assertIn('/api/host-config/hostname', html)

    def test_api_test_page_includes_config_routes(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for route in [
            "GET /api/config",
            "PUT /api/config",
            "PUT /api/config/controllers",
            "PUT /api/config/devices",
            "PUT /api/config/cameras",
        ]:
            self.assertIn(f"<legend>{route}</legend>", html)
        self.assertIn('data-copy-target="get-config-curl-command"', html)
        self.assertIn('data-copy-target="put-config-devices-curl-command"', html)
        for button_id in [
            "get-config",
            "put-config",
            "put-config-controllers",
            "put-config-devices",
            "put-config-cameras",
        ]:
            self.assertIn(f'id="{button_id}"', html)
        for result_id in [
            "get-config-result",
            "put-config-result",
            "put-config-controllers-result",
            "put-config-devices-result",
            "put-config-cameras-result",
        ]:
            self.assertIn(f'id="{result_id}"', html)
        self.assertIn("async function runConfigRequest", html)
        self.assertIn('document.getElementById("put-config-devices").addEventListener("click", () => runConfigRequest("devices"));', html)

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
