import html as html_module
import json
import unittest
from pathlib import Path

from plamp_web.pages import json_script_text, main_nav, render_api_test_page, render_system_info_page


def static_timer_dashboard(*args, **kwargs) -> str:
    return Path("plamp_web/static/index.html").read_text(encoding="utf-8")


def static_text(name: str) -> str:
    return (Path("plamp_web/static") / name).read_text(encoding="utf-8")


class PageRenderTests(unittest.TestCase):
    def test_controller_static_client_uses_rest_and_sse_without_injected_state(self):
        html = static_text("controller.html")
        script = static_text("controller.js")

        self.assertIn("data-plamp-nav", html)
        self.assertIn('src="/static/controller.js"', html)
        self.assertNotIn("octo_relay", html)
        self.assertNotIn("pump_lights", html)
        self.assertIn("decodeURIComponent", script)
        self.assertIn('new URLSearchParams({path: `controllers.${controller}`})', script)
        self.assertIn("/serial-log`)", script)
        self.assertIn("new EventSource", script)
        self.assertIn('?stream=true`', script)

    def test_controller_static_client_preserves_diagnostic_commands(self):
        html = static_text("controller.html")
        script = static_text("controller.js")

        for element_id in ("report-now", "pulse-pin", "pulse-seconds", "pulse-send", "refresh-diagnostics", "refresh-log"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("/commands/report`", script)
        self.assertIn("/pins/${encodeURIComponent(pin)}/pulse`", script)
        self.assertIn("window.confirm", script)
        self.assertIn("Stream disconnected; showing last valid report.", script)

    def test_controller_report_events_preserve_last_monitor_status(self):
        script = static_text("controller.js")

        self.assertIn("function renderStreamEvent(eventName, data)", script)
        self.assertIn('if (eventName !== "report") renderStatus(telemetry);', script)
        self.assertIn("renderStreamEvent(eventName, JSON.parse(event.data))", script)

    def test_settings_static_client_bootstraps_only_from_rest(self):
        html = static_text("settings.html")
        script = static_text("settings.js")

        self.assertIn("data-plamp-nav", html)
        self.assertIn('fetch("/api/config")', script)
        self.assertIn("PlampWeb.bootstrapShell", script)
        self.assertNotIn("pump_lights", html)
        self.assertNotIn("abc123", html)

    def test_settings_load_failure_disables_saves(self):
        script = static_text("settings.js")

        self.assertIn("PlampWeb.loadSystem()", script)
        self.assertIn("setSaveDisabled(true)", script)
        self.assertIn("Settings setup failed:", script)

    def test_settings_static_client_preserves_save_contract(self):
        html = static_text("settings.html")
        script = static_text("settings.js")

        for function_name in (
            "collectControllers",
            "collectControllerDevices",
            "collectCameras",
            "controllerRenames",
            "collectConfigWithControllerRenames",
        ):
            self.assertIn(f"function {function_name}", script)
        self.assertIn('saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())', script)
        self.assertIn('saveSection("devices-status", "/api/config", collectConfigWithControllerRenames())', script)
        self.assertIn('saveSection("cameras-status", "/api/config/cameras", collectCameras())', script)
        self.assertIn("Pin required for device", script)
        self.assertIn("delete result[oldKey]", script)
        self.assertIn("window.location.reload()", script)
        self.assertIn('id="save-controllers"', html)
        self.assertIn('id="save-devices"', html)
        self.assertIn('id="save-cameras"', html)

    def test_settings_static_client_preserves_hidden_and_camera_matching(self):
        html = static_text("settings.html")
        script = static_text("settings.js")

        self.assertIn("hiddenControllers = {}", script)
        self.assertIn("hydrateControllerRowFromHidden", script)
        self.assertIn("structuredClone(hiddenControllers)", script)
        self.assertIn("function cameraMatches", script)
        self.assertIn("normalizeCameraKey", script)
        self.assertIn("Capture dir must be inside repo root", script)
        self.assertIn('row.className = `camera-row${isNew ? " new-row" : ""}`', script)
        self.assertIn("Report an issue", html)

    def test_shared_shell_discovers_navigation_from_rest(self):
        shell = static_text("app.js")
        dashboard = static_text("index.html")

        self.assertIn('fetch("/api/controllers")', shell)
        self.assertIn('fetch("/api/system")', shell)
        self.assertIn("window.PlampWeb", shell)
        self.assertIn('<script src="/static/app.js"></script>', dashboard)
        self.assertNotIn("function renderMainNav", dashboard)

    def test_timer_dashboard_static_file_bootstraps_only_through_rest(self):
        path = Path("plamp_web/static/index.html")
        self.assertTrue(path.is_file())
        html = path.read_text(encoding="utf-8")
        shell = static_text("app.js")

        for endpoint in ("/api/timer-config", "/api/host-time", "/api/config"):
            self.assertIn(f'fetch("{endpoint}")', html)
        self.assertIn('fetch("/api/system")', shell)
        self.assertIn("let clockTimeFormat", html)
        self.assertIn("let timerRoles", html)
        self.assertIn("let timerChannels", html)
        self.assertIn("let timerHostSecondsAtLoad", html)
        self.assertIn("PlampWeb.bootstrapShell", html)
        self.assertIn("function populateCameraSelectors", html)
        self.assertIn("async function bootstrapDashboard", html)
        bootstrap = html.split("async function bootstrapDashboard()", 1)[1].split("function formatChangeTime", 1)[0]
        self.assertLess(bootstrap.index("PlampWeb.bootstrapShell"), bootstrap.index("startTimerStreams();"))
        self.assertIn("await bootstrapDashboard()", html)

    def test_nav_uses_single_link_to_running_revision(self):
        nav = main_nav(revision="ebaf545")

        self.assertIn('<a href="https://github.com/hugomatic/plamp/commit/ebaf545">[rev ebaf545]</a>', nav)
        self.assertNotIn('>GitHub</a>', nav)

    def test_nav_renders_unknown_revision_without_a_link(self):
        nav = main_nav(revision="unknown")

        self.assertIn("[rev unknown]", nav)
        self.assertNotIn("/commit/unknown", nav)

    def test_nav_escapes_revision_text(self):
        nav = main_nav(revision='abc\"<script>')

        self.assertNotIn("<script>", nav)

    def test_timer_dashboard_page_links_to_settings(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)
        shell = static_text("app.js")

        self.assertIn('navLink("/settings", "Settings", activePath)', shell)
        self.assertNotIn('href="/config"', html)

    def test_timer_dashboard_page_uses_hostname_in_title_and_heading(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0, hostname="nurse-plamp")

        self.assertIn('const hostname = String(systemPayload?.host?.hostname || "");', html)
        self.assertIn('document.title = pageName;', html)
        self.assertIn('document.getElementById("page-name").textContent = pageName;', html)
        self.assertNotIn("nurse-plamp", html)

    def test_api_test_page_uses_hostname_in_title_and_heading(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h", hostname="nurse-plamp")

        self.assertIn("<title>nurse-plamp API test</title>", html)
        self.assertIn("<h1>nurse-plamp API test</h1>", html)


    def test_pages_use_same_nav_with_system_link(self):
        expected = '<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | [rev unknown]</nav>'
        html = render_system_info_page({"host": {"hostname": "sprout"}})
        self.assertIn(expected, html)
        self.assertEqual(html.count("<nav>"), 1)

    def test_timer_dashboard_page_reloads_every_30_seconds(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('id="refresh-countdown"', html)
        self.assertIn("let refreshSeconds = 30;", html)
        self.assertIn("window.location.reload();", html)

    def test_timer_dashboard_page_uses_server_schedule_success_message(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('lastMessage = scheduleParsed?.message || "Schedule settings saved.";', html)
        self.assertIn('showEditorMessage(message, "editor-success", lastMessage || "Schedule settings saved.");', html)

    def test_system_info_page_shows_actions_and_no_hostname_editor(self):
        html = render_system_info_page(
            {
                "host": {"hostname": "sprout", "hardware_model": "Raspberry Pi Zero 2 W Rev 1.0"},
                "host_time": {"display": "10:15 AM"},
                "software": {
                    "git_branch": "main",
                    "git_short_commit": "6e2cf82",
                    "git_dirty": False,
                    "git_commit_timestamp": "2026-05-20T10:15:00-07:00",
                    "os_name": "Debian GNU/Linux",
                    "os_version": "12",
                    "os_arch": "aarch64",
                    "user_name": "hugo",
                    "user_is_sudoer": True,
                    "user_has_serial_access": True,
                    "user_has_video_access": True,
                },
                "paths": {"repo_root": "/home/hugo/plamp", "data_dir": "/home/hugo/plamp/data"},
                "storage": {"path": "/home/hugo/plamp", "free": "2.0 GB", "used": "1.0 GB", "total": "3.0 GB"},
                "log": {"path": "/var/log/plamp-web.log"},
                "detected": {"picos": [{"port": "/dev/ttyACM0", "serial": "abc", "vendor_id": "1234", "product_id": "abcd"}], "cameras": [{"connector": "cam0", "model": "Camera Module 3 Wide", "sensor": "imx708", "lens": "wide", "path": "/dev/video0"}]},
                "camera_worker": {"state": "idle", "available": True, "queue_depth": 0, "last_capture_at": "2026-05-20T10:15:00", "last_error": None, "scheduled_cameras": ["cam0"]},
                "monitors": {"pump_lights": {"serial": "abc", "state": "idle", "connected": True, "port": "/dev/ttyACM0", "last_seen": "2026-05-20T10:14:59", "last_error": None}},
            }
        , "plamp-web started")

        self.assertIn("<h2>System info</h2>", html)
        self.assertIn("<h2>Storage</h2>", html)
        self.assertIn("<h2>Camera worker</h2>", html)
        self.assertIn("<h2>Controller workers</h2>", html)
        self.assertIn('class="host-clock"', html)
        self.assertIn("<strong>Host time:</strong> 10:15 AM", html)
        self.assertEqual(html.count("Git commit</th>"), 1)
        self.assertEqual(html.count("Root folder</th>"), 1)
        self.assertEqual(html.count("Repo root</th>"), 0)
        self.assertEqual(html.count("Data dir</th>"), 1)
        self.assertEqual(html.count("Storage path</th>"), 0)
        self.assertEqual(html.count("Plamp root"), 0)
        self.assertEqual(html.count("Plamp data"), 0)
        self.assertEqual(html.count("Operating system</th>"), 1)
        self.assertEqual(html.count("User name</th>"), 1)
        self.assertEqual(html.count("Computer hardware model</th>"), 1)
        self.assertIn("Raspberry Pi Zero 2 W Rev 1.0", html)
        self.assertEqual(html.count("Log file</th>"), 1)
        self.assertNotIn("<th scope=\"row\">Log file</th><td>/var/log/plamp-web.log</td>", html)
        self.assertNotIn("Detected picos", html)
        self.assertNotIn("Detected cameras", html)
        self.assertIn("Restart", html)
        self.assertIn("Reinstall", html)
        self.assertIn("Upgrade", html)
        self.assertIn("Logs", html)
        self.assertIn("plamp-web started", html)
        self.assertNotIn('id="hostname-input"', html)
        self.assertIn("2.0 GB", html)
        self.assertIn("3.0 GB", html)
        self.assertIn("cam0", html)
        self.assertIn("pump_lights", html)

    def test_timer_dashboard_page_groups_devices_by_controller_and_edits_as_one_schedule(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("<h2>Controllers</h2>", html)
        self.assertNotIn("<h2>Timers</h2>", html)
        self.assertIn("let activeEditor = null;", html)
        self.assertIn("async function openControllerScheduleEditor(role) {", html)
        self.assertIn("activeEditor = {role};", html)
        self.assertIn("stopPageAutoRefresh();", html)
        self.assertIn('controllerCard.dataset.role = role;', html)
        self.assertIn('edit.textContent = "Edit schedule";', html)
        self.assertIn('edit.addEventListener("click", () => openControllerScheduleEditor(role));', html)
        self.assertIn('button type="submit">Apply schedule</button>', html)
        self.assertIn('button type="button" name="cancel">Close</button>', html)
        self.assertNotIn("Edit octo_relay schedule", html)
        self.assertIn('const form = timerBoard.querySelector("#timer-schedule-form");', html)
        self.assertIn('const activeForm = timerBoard.querySelector("#timer-schedule-form");', html)
        self.assertIn("if (!force && activeEditor && activeForm && activeForm.contains(document.activeElement)) {", html)
        self.assertIn('const controllerCard = document.createElement(isEditing ? "form" : "section");', html)
        self.assertIn('controllerCard.id = "timer-schedule-form";', html)
        self.assertIn('editor.innerHTML = scheduleEditorBlock(role, channel, event);', html)
        self.assertIn('card.append(block);', html)
        self.assertIn('const actions = document.createElement("div");', html)
        self.assertIn('actions.className = "controller-actions controller-actions-editing";', html)
        self.assertIn('for (const block of controllerCard.querySelectorAll(".device-schedule-editor")) {', html)
        self.assertIn('actions.querySelector(\'[name="cancel"]\').addEventListener("click", () => { activeEditor = null; renderTimerStatus(true); });', html)
        self.assertIn('controllerCard.classList.add("controller-card-editing");', html)
        self.assertIn('class="editor-cycle-unit"', html)
        self.assertIn('<option value="disabled"${mode === "disabled" ? " selected" : ""}>disabled</option>', html)
        self.assertIn('<option value="hidden"${mode === "hidden" ? " selected" : ""}>hidden</option>', html)
        self.assertIn('message?.telemetry?.last_report?.content?.devices,', html)
        self.assertIn('message?.telemetry?.report?.content?.devices,', html)
        self.assertIn('const source = new EventSource(`/api/controllers/${encodeURIComponent(role)}?stream=true`);', html)
        self.assertIn('for (const eventName of ["snapshot", "report"]) {', html)
        self.assertIn('source.addEventListener("status"', html)
        self.assertIn('const data = JSON.parse(event.data);', html)
        self.assertIn('timerMessages.set(role, data);', html)
        self.assertIn('"value" in message[0]', html)
        self.assertIn("return message[0].value;", html)
        self.assertIn('const cycleUnit = block.querySelector(".editor-cycle-unit").value;', html)
        self.assertIn('const startAtSeconds = Number(block.querySelector(".editor-start-at").value) * multiplier;', html)
        self.assertIn('start_at_seconds: startAtSeconds', html)
        self.assertIn('const configResponse = await fetch("/api/config");', html)
        self.assertIn('controller.settings.devices = structuredClone(controller.settings.devices || {});', html)
        self.assertIn('controller.settings.devices[channelId] = device;', html)
        self.assertIn('data-channel-pin="${escapeHtml(channel.pin ?? "")}"', html)
        self.assertIn('const scheduleResponse = await fetch(`/api/controllers/${encodeURIComponent(role)}/schedule`, {', html)
        self.assertNotIn('const saveConfigResponse = await fetch("/api/config/controllers", {', html)
        self.assertNotIn('const applyConfigResponse = await fetch(`/api/controllers/${encodeURIComponent(role)}/apply`', html)
        self.assertIn("function clockValuesForEvent(channel, event) {", html)
        self.assertIn('if (editor?.kind === "daily_window" && editor.on_time && editor.off_time)', html)
        self.assertNotIn('/channels/${encodeURIComponent(channelId)}/schedule', html)
        self.assertIn('syncSavedEditorMetadata(role, block, controller.settings.devices[channelId]);', html)
        self.assertIn('activeEditor = null;', html)
        self.assertIn('renderTimerStatus(true);', html)
        self.assertNotIn('/api/status?stream=true&path=', html)
        self.assertNotIn('/api/timers', html)
        self.assertNotIn("Stream error or reconnecting...", html)
        self.assertNotIn('class="editor-on-unit"', html)
        self.assertNotIn('class="editor-off-unit"', html)
        self.assertNotIn("function openScheduleEditor(role, channel, event) {", html)
        self.assertNotIn("timerEditorPanel", html)
        self.assertNotIn("controllerScheduleForm", html)

        report_request = html.index('await fetch(`/api/controllers/${encodeURIComponent(role)}/commands/report`, {method: "POST"})')
        open_editor = html.index("activeEditor = {role};", report_request)
        self.assertLess(report_request, open_editor)
        rejected_schedule = html.index("if (!scheduleResponse.ok)")
        sync_metadata = html.index("syncSavedEditorMetadata(role, block, controller.settings.devices[channelId]);")
        self.assertLess(rejected_schedule, sync_metadata)

    def test_timer_dashboard_renders_binary_controller_health(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("const timerStatuses = new Map();", html)
        self.assertIn("controller-card-error", html)
        self.assertIn('status.textContent = ok', html)
        self.assertIn('`ERROR: ${health?.error?.message || "no valid report"}`', html)
        self.assertIn("last verified", html)
        self.assertNotIn("controller-diagnostics", html)
        self.assertIn('diagnostics.href = `/controllers/${encodeURIComponent(role)}`;', html)
        self.assertIn('diagnostics.textContent = "Diagnostics";', html)
        self.assertIn("edit.disabled = !ok;", html)
        self.assertIn("timer-card-stale", html)
        self.assertIn("setInterval(() => renderTimerStatus(), 1000);", html)
        self.assertIn("currentTimerStep(event, messageAge)", html)
        self.assertIn('error: {message: "controller status stream disconnected"}', html)

    def test_timer_dashboard_freezes_stale_pin_animation(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn(
            "const messageAge = ok && item.event ? Math.floor((Date.now() - (timerMessageTimes.get(role) || Date.now())) / 1000) : 0;",
            html,
        )
        self.assertIn("const value = Number(event.current_value ?? 0);", html)
        self.assertNotIn("const value = Number(step?.step?.val ?? event.current_value ?? 0);", html)

    def test_timer_dashboard_page_preserves_editor_focus_on_timer_updates(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("let pendingTimerRender = false;", html)
        self.assertIn("function flushPendingTimerRender() {", html)
        self.assertIn("function renderTimerStatus(force = false) {", html)
        self.assertIn('const activeForm = timerBoard.querySelector("#timer-schedule-form");', html)
        self.assertIn("if (!force && activeEditor && activeForm && activeForm.contains(document.activeElement)) {", html)
        self.assertIn("renderTimerStatus(true);", html)
        self.assertIn("pendingTimerRender = true;", html)
        self.assertIn('controllerCard.addEventListener("focusout", () => window.setTimeout(flushPendingTimerRender, 0));', html)

    def test_timer_dashboard_editor_prefers_saved_cycle_values_over_live_progress(self):
        html = static_timer_dashboard(
            ["pump_lights"],
            "12h",
            {
                "pump_lights": [
                    {
                        "id": "pump",
                        "pin": 3,
                        "type": "gpio",
                        "default_editor": "cycle",
                        "editor": {"kind": "cycle", "on_seconds": 300, "off_seconds": 1800, "start_at_seconds": 0, "unit": "minutes"},
                    }
                ]
            },
            0,
        )

        self.assertIn("function cycleEditorValues(channel, event) {", html)
        self.assertIn('const editor = channel.editor && typeof channel.editor === "object" ? channel.editor : null;', html)
        self.assertIn('if (editor?.kind === "cycle" && Number.isFinite(Number(editor.on_seconds)) && Number.isFinite(Number(editor.off_seconds))) {', html)
        self.assertIn('const unit = ["seconds", "minutes", "hours"].includes(editor.unit) ? editor.unit : chooseSharedUnit([onSeconds, offSeconds, startAtSeconds]);', html)
        self.assertIn("const cycleValues = cycleEditorValues(channel, event);", html)
        self.assertIn('value="${cycleValues.onValue}"', html)
        self.assertIn('value="${cycleValues.offValue}"', html)
        self.assertIn('value="${cycleValues.startAtValue}"', html)

    def test_timer_dashboard_saves_cycle_editor_values_and_unit_to_config(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('device.editor = {kind: "cycle", on_seconds: onSeconds, off_seconds: offSeconds, start_at_seconds: startAtSeconds, unit: cycleUnit};', html)
        self.assertIn("const cycleUnit = block.querySelector(\".editor-cycle-unit\").value;", html)
        self.assertIn("const onSeconds = Number(block.querySelector(\".editor-on-value\").value) * multiplier;", html)
        self.assertIn("const offSeconds = Number(block.querySelector(\".editor-off-value\").value) * multiplier;", html)
        self.assertIn("const startAtSeconds = Number(block.querySelector(\".editor-start-at\").value) * multiplier;", html)

    def test_timer_dashboard_formats_change_time_from_server_clock(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 90)

        self.assertIn("function formatDuration(secondsValue) {", html)
        self.assertIn('return parts.length ? parts.join(" ") : "0s";', html)
        self.assertIn("function serverDateForSecondsFromNow(secondsFromNow) {", html)
        self.assertIn("const deltaSeconds = targetSeconds - hostSecondsNow();", html)
        self.assertIn('return secondsToClock(targetSeconds) + " (" + formatDuration(seconds) + ")";', html)

    def test_timer_dashboard_does_not_treat_schedule_response_as_live_state(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertNotIn("function applyScheduleResponseState(role, parsed) {", html)
        self.assertNotIn("timerMessages.set(role, {devices: parsed.state.devices});", html)
        self.assertNotIn("applyScheduleResponseState(role, parsed);", html)

    def test_timer_dashboard_updates_local_editor_metadata_after_save(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertNotIn("timerReportPeriods[role]", html)
        self.assertIn("function syncSavedEditorMetadata(role, block, device) {", html)
        self.assertIn("channel.default_editor = block.querySelector(\".editor-mode\").value;", html)
        self.assertIn("channel.editor = structuredClone(device.editor);", html)
        self.assertIn("syncSavedEditorMetadata(role, block, controller.settings.devices[channelId]);", html)

    def test_timer_dashboard_keeps_manual_controls_off_cards(self):
        html = static_timer_dashboard(
            ["pump_lights"],
            "12h",
            {
                "pump_lights": [
                    {"id": "pump", "name": "Pump", "pin": 21, "type": "gpio", "visibility": "visible", "programming": "enabled"},
                    {"id": "fan", "name": "Fan", "pin": 22, "type": "pwm", "visibility": "visible", "programming": "enabled"},
                    {"id": "hidden", "name": "Hidden", "pin": 23, "type": "gpio", "visibility": "hidden", "programming": "enabled"},
                ]
            },
            0,
        )

        self.assertIn('diagnostics.href = `/controllers/${encodeURIComponent(role)}`;', html)
        self.assertNotIn('textContent = "Report now";', html)
        self.assertNotIn('textContent = "Refresh log";', html)
        self.assertNotIn('textContent = "Pico";', html)

    def test_timer_dashboard_page_includes_camera_capture_and_gallery_controls(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("<h2>Camera</h2>", html)
        self.assertIn('id="camera-capture"', html)
        self.assertIn('id="camera-capture-status"', html)
        self.assertIn('id="camera-capture-camera"', html)
        self.assertIn('id="camera-capture-page"', html)
        self.assertIn('id="camera-capture-go"', html)
        self.assertIn('id="camera-capture-filter"', html)
        self.assertIn('id="camera-viewer"', html)
        self.assertIn('id="camera-capture-list"', html)
        self.assertIn('id="camera-capture-prev"', html)
        self.assertIn('id="camera-capture-next"', html)
        self.assertIn("fetch(cameraCaptureRequestUrl())", html)
        self.assertIn("|| captures[0];", html)
        self.assertIn("selectCameraCapture(selected);", html)
        self.assertIn("cameraViewer.src = capture.image_url;", html)
        self.assertNotIn('id="camera-capture-grid"', html)
        self.assertNotIn('id="camera-capture-links"', html)
        self.assertNotIn("thumbnailCaptures", html)

    def test_timer_dashboard_places_take_picture_button_below_image(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertLess(
            html.index('<img id="camera-viewer"'),
            html.index('<div class="camera-actions">'),
        )


    def test_timer_dashboard_camera_controls_include_camera_selector_and_total(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0, ["rpicam_cam0", "rpicam_cam1"])

        self.assertIn("function populateCameraSelectors(cameraIds)", html)
        self.assertIn("option.value = cameraId;", html)
        self.assertIn("option.textContent = cameraId;", html)
        self.assertIn("Object.keys(cameras)", html)
        self.assertIn('params.set("camera_id", cameraCaptureCamera.value);', html)
        self.assertIn('const total = Number(data.total ?? 0);', html)
        self.assertIn('cameraCapturePageStatus.textContent = `Page ${currentPage} of ${cameraCaptureTotalPages} | Showing ${start}-${end} of ${cameraCaptureTotal}`;', html)
        self.assertIn('cameraCaptureOffset = pageOffset();', html)
        self.assertIn('cameraCapturePage.max = String(Math.max(1, cameraCaptureTotalPages));', html)
        self.assertIn('if (capture.camera_id) parts.push("camera " + capture.camera_id);', html)

    def test_timer_dashboard_capture_list_is_compact_and_scrollable(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn(".capture-list {", html)
        self.assertIn("max-height: 22rem;", html)
        self.assertIn("overflow-y: auto;", html)
        self.assertIn(".capture-list button:nth-child(even)", html)
        self.assertIn(".capture-list button:nth-child(odd)", html)
        self.assertIn("border: 0;", html)
        self.assertIn("border-radius: 0;", html)
        self.assertIn("width: 100%;", html)
        self.assertIn("border-left: 4px solid #174ea6;", html)
        self.assertIn("padding: .35rem .5rem;", html)

    def test_timer_dashboard_buttons_pin_readable_mobile_text_style(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("appearance: none;", html)
        self.assertIn("-webkit-appearance: none;", html)
        self.assertIn("color: #111;", html)
        self.assertIn("font: inherit;", html)

    def test_timer_dashboard_renders_disabled_and_hidden_channels_in_editor_flow(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": [{"id": "pump", "pin": 3, "type": "gpio", "default_editor": "disabled"}, {"id": "lights", "pin": 4, "type": "gpio", "default_editor": "hidden"}]}, 0)

        self.assertIn('const disabled = channel.default_editor === "disabled";', html)
        self.assertIn('const hidden = channel.default_editor === "hidden";', html)
        self.assertIn('badge.textContent = hidden ? "HIDDEN" : (disabled ? "DISABLED" : (isOn ? "ON" : "OFF"));', html)
        self.assertIn('const isEditing = ok && activeEditor && activeEditor.role === role;', html)
        self.assertIn('if (!hidden || isEditing) {', html)
        self.assertIn('if (configurableCount > 0) {', html)
        self.assertIn('edit.addEventListener("click", () => openControllerScheduleEditor(role));', html)
        self.assertIn('actions.textContent = "No configured device schedules.";', html)

    def test_timer_dashboard_edit_schedule_excludes_report_period(self):
        html = static_timer_dashboard(
            ["pump_lights"],
            "12h",
            {"pump_lights": [{"id": "pump", "pin": 3, "type": "gpio", "default_editor": "cycle"}]},
            0,
        )

        self.assertNotIn("Pico poll interval (seconds)", html)
        self.assertNotIn('class="controller-report-period"', html)
        self.assertNotIn('const reportPeriodInput = form.querySelector(".controller-report-period");', html)

    def test_timer_dashboard_page_pauses_and_resumes_auto_reload_for_camera_interaction(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

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
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('cameraCaptureFilter.addEventListener("change", () => {', html)
        self.assertIn("cameraCaptureOffset = 0;", html)
        self.assertIn("refreshCameraCaptures();", html)

    def test_timer_dashboard_capture_filter_is_applied_before_paging(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("function cameraCaptureRequestUrl()", html)
        self.assertIn('params.set("camera_id", filter.slice(7));', html)
        self.assertIn('const options = new Map([["all", "All cameras"]]);', html)
        self.assertNotIn("camera_roll", html)
        self.assertIn("fetch(cameraCaptureRequestUrl())", html)
        self.assertNotIn("visibleCameraCaptures", html)

    def test_timer_dashboard_page_ignores_unconfigured_runtime_pins(self):
        html = static_timer_dashboard(
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
        self.assertIn("const event = item.event || {id: channel.id, pin: channel.pin, type: channel.type || \"gpio\"};", html)

    def test_timer_dashboard_page_reads_devices_from_runtime_messages(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("message?.report?.content?.devices", html)
        self.assertIn("message?.last_report?.content?.devices", html)
        self.assertIn("message?.content?.devices", html)
        self.assertIn("message?.devices", html)
        self.assertNotIn("message?.report?.content?.events", html)
        self.assertNotIn("message?.last_report?.content?.events", html)
        self.assertNotIn("message?.content?.events", html)
        self.assertNotIn("message?.events", html)

    def test_api_test_page_reads_devices_from_timer_stream_payloads(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn("message?.report?.content?.devices", html)
        self.assertIn("message?.last_report?.content?.devices", html)
        self.assertIn("message?.content?.devices", html)
        self.assertIn("message?.devices", html)
        self.assertNotIn("message?.report?.content?.events", html)
        self.assertNotIn("message?.last_report?.content?.events", html)
        self.assertNotIn("message?.content?.events", html)
        self.assertNotIn("message?.events", html)

    def test_api_test_page_does_not_offer_compiled_scheduler_state_put(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertNotIn("PUT /api/controllers/{role}", html)
        self.assertNotIn('id="put-state"', html)
        self.assertNotIn('id="put-role"', html)
        self.assertNotIn('id="generate-quick"', html)
        self.assertNotIn('id="generate-pump-lights"', html)
        self.assertNotIn("async function putState", html)

    def test_api_test_page_includes_pico_scheduler_pulse_request(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn('<datalist id="timer-roles"><option value="pump_lights"></option></datalist>', html)
        self.assertIn("<legend>POST /api/controllers/{controller}/pins/{pin}/pulse</legend>", html)
        self.assertIn('id="pulse-controller"', html)
        self.assertIn('id="pulse-pin"', html)
        self.assertIn('id="pulse-seconds"', html)
        self.assertIn('id="pulse-curl-command"', html)
        self.assertIn('id="pulse-request"', html)
        self.assertIn('pulseUrl()', html)
        self.assertIn('fetch(pulseUrl(), {', html)
        self.assertIn('body: JSON.stringify({seconds: pulseSeconds()})', html)

    def test_api_test_page_documents_complete_scheduler_workflow(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn("GET /api/controllers/{controller}", html)
        self.assertIn("PUT /api/config/controllers", html)
        self.assertIn("GET /api/controllers/{controller}?stream=true", html)
        self.assertIn("POST /api/controllers/{controller}/schedule", html)
        self.assertIn("POST /api/controllers/{controller}/commands/report", html)
        self.assertIn("POST /api/controllers/{controller}/channels/{channel}/schedule", html)
        self.assertIn('id="controller-stream-start"', html)
        self.assertIn('id="controller-stream-result"', html)
        self.assertIn('id="scheduler-schedule-payload"', html)
        self.assertIn('id="scheduler-schedule-request"', html)
        self.assertIn('id="scheduler-schedule-result"', html)
        self.assertIn('fetch(`/api/controllers/${encodeURIComponent(schedulerController)}/schedule`', html)
        self.assertIn('for (const eventName of ["snapshot", "status", "report", "error"])', html)
        self.assertIn('&quot;mode&quot;:&quot;cycle&quot;', html)
        self.assertIn('&quot;mode&quot;:&quot;clock_window&quot;', html)
        self.assertIn('&quot;on_time&quot;:&quot;06:00&quot;', html)
        self.assertIn("Schedules are committed only after a verified Pico apply", html)
        self.assertIn("firmware_upgraded", html)
        self.assertIn("firmware identity", html)
        self.assertIn("Apply and commit the complete", html)
        self.assertIn("Applying and verifying...", html)
        self.assertNotIn("Flash and commit the complete", html)
        self.assertNotIn("Normal workflow: save desired config once, then apply the controller once.", html)
        self.assertIn("Compatibility endpoint for changing one channel", html)
        self.assertIn("<strong>Recovery:</strong> reapplies the current desired controller config", html)
        self.assertNotIn("desired config plus controller apply", html)


    def test_settings_page_includes_storage_summary(self):
        html = render_system_info_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "paths": {"repo_root": "/repo/plamp", "data_dir": "/repo/plamp/data"},
            "storage": {
                "path": "/path/to/plamp",
                "free": "42.0 GB",
                "used": "10.0 GB",
                "total": "52.0 GB",
            },
            "log": {"path": "/repo/plamp/data/plamp.log"},
        })

        self.assertIn("System info", html)
        self.assertIn("<h2>Storage</h2>", html)
        self.assertIn("<th scope=\"row\">Root folder</th>", html)
        self.assertIn("<th scope=\"row\">Data dir</th>", html)
        self.assertIn("PLAMP_ROOT", html)
        self.assertIn("PLAMP_DATA_DIR", html)
        self.assertNotIn("<th scope=\"row\">Storage path</th>", html)
        self.assertIn("<th scope=\"row\">Free disk space</th>", html)
        self.assertIn("<th scope=\"row\">Used disk space</th>", html)
        self.assertIn("<th scope=\"row\">Total disk space</th>", html)
        self.assertIn("<th scope=\"row\">Log file</th>", html)
        self.assertNotIn("<th>Path</th><th>Free</th><th>Used</th><th>Total</th>", html)
        self.assertIn("/repo/plamp", html)
        self.assertIn("/repo/plamp/data", html)
        self.assertIn("/repo/plamp/data/plamp.log", html)
        self.assertNotIn("/path/to/plamp", html)
        self.assertIn("42.0 GB", html)
        self.assertIn("10.0 GB", html)
        self.assertIn("52.0 GB", html)


    def test_settings_page_includes_git_software_identity(self):
        html = render_system_info_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "software": {
                "git_commit": "d5883da4abcdef",
                "git_short_commit": "d5883da",
                "git_branch": "main",
                "git_commit_timestamp": "2026-05-04T10:41:12-10:00",
                "git_dirty": True,
            },
        })

        self.assertIn("System info", html)
        self.assertIn("Git commit", html)
        self.assertIn("d5883da", html)
        self.assertIn("main", html)
        self.assertIn("Git commit time", html)
        self.assertIn("ago", html)
        self.assertIn("Git dirty", html)

    def test_settings_page_includes_detected_raspberry_pi_cameras(self):
        html = render_system_info_page({
            "host_time": {"display": "1:23 PM"},
            "host": {"hostname": "plamp", "network": []},
            "detected": {"picos": [], "cameras": [{"key": "rpicam:cam0", "connector": "cam0", "index": 0, "sensor": "imx708", "model": "imx708_wide", "lens": "wide", "path": "/base/imx708@1a"}]},
        })

        self.assertIn("System info", html)
        self.assertIn("<h2>Hardware</h2>", html)
        self.assertIn("<h3>Serial USB peripherals</h3>", html)
        self.assertIn("<h3>Cameras</h3>", html)
        self.assertNotIn("Detected hardware", html)
        self.assertNotIn("<h3>Peripherals</h3>", html)
        self.assertNotIn("<h3>Raspberry Pi cameras</h3>", html)
        self.assertNotIn("Detected cameras", html)
        self.assertNotIn("Detected picos", html)
        self.assertIn("cam0", html)

    def test_json_script_text_preserves_payload_and_escapes_script_end_tag(self):
        payload = {
            "unused": {
                "label": "Unused </script> & <grow> > flower",
                "type": "pico_scheduler",
                "report_every": 20,
            }
        }

        rendered = json_script_text(payload)

        self.assertEqual(json.loads(rendered), payload)
        self.assertIn(r"<\/script>", rendered)
        self.assertNotIn("</script>", rendered)

    def test_api_test_page_includes_config_routes(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for route in [
            "GET /api/config",
            "PUT /api/config",
            "PUT /api/config/cameras",
            "PUT /api/config/controllers",
        ]:
            self.assertIn(f"<legend>{route}</legend>", html)
        self.assertLess(html.index("<legend>GET /api/config</legend>"), html.index("<legend>PUT /api/config</legend>"))
        self.assertLess(html.index("<legend>PUT /api/config</legend>"), html.index("<legend>PUT /api/config/cameras</legend>"))
        self.assertLess(html.index("<legend>PUT /api/config/cameras</legend>"), html.index("<legend>PUT /api/config/controllers</legend>"))
        self.assertLess(html.index("<legend>PUT /api/config/controllers</legend>"), html.index("<legend>GET /api/system</legend>"))
        self.assertIn('data-copy-target="get-config-curl-command"', html)
        self.assertNotIn('data-copy-target="put-config-devices-curl-command"', html)
        for button_id in [
            "get-config",
            "put-config",
            "put-config-controllers",
            "put-config-cameras",
        ]:
            self.assertIn(f'id="{button_id}"', html)
        for result_id in [
            "get-config-result",
            "put-config-result",
            "put-config-controllers-result",
            "put-config-cameras-result",
        ]:
            self.assertIn(f'id="{result_id}"', html)
        self.assertIn("async function runConfigRequest", html)
        self.assertNotIn('document.getElementById("put-config-devices")', html)

    def test_api_test_page_uses_filtered_status_paths_and_streaming(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn("<title>Plamp API test</title>", html)
        self.assertIn('href="/openapi.json"', html)
        self.assertIn('href="/docs"', html)
        self.assertIn("For machine-readable integration", html)
        for title in [
            "POST /api/camera/captures",
            "GET /api/camera/captures",
            "GET /api/status",
            "GET /api/status?stream=true",
        ]:
            self.assertIn(f"<legend>{title}</legend>", html)
        self.assertIn("Captures a new image and returns capture metadata.", html)
        self.assertIn("Lists captures newest first. Options: camera_id, limit and offset.", html)
        self.assertIn("Status paths", html)
        self.assertIn('bindStatusPathRow(row);', html)
        self.assertIn('for (const row of Array.from(statusPathList.querySelectorAll(".status-path-row"))) {', html)
        self.assertIn("Reads filtered status nodes for one or more paths.", html)
        self.assertIn("Streams filtered status updates with server-sent events.", html)
        self.assertIn("Stream status updates will appear here.", html)
        self.assertIn('<label><input id="stream-pretty" type="checkbox" checked> Pretty JSON</label>', html)
        self.assertIn('const streamPrettyInput = document.getElementById("stream-pretty");', html)
        self.assertIn("display = JSON.stringify(parsed, null, streamPrettyInput.checked ? 2 : 0);", html)
        self.assertIn('<pre id="stream-result">Stream status updates will appear here.</pre>', html)
        self.assertNotIn("streamBoard.textContent = JSON.stringify(parsed, null, 2);", html)
        self.assertIn("Add path", html)
        self.assertIn("Remove", html)
        self.assertIn('value="config.controllers.pump_lights"', html)
        self.assertIn('value="controllers.pump_lights.telemetry"', html)
        self.assertIn('getResult.textContent = `Error: ${detail || response.statusText}`;', html)
        self.assertIn('streamStatus.textContent = `Connecting to ${statusUrl(true)}...`;', html)
        self.assertIn('fetch(statusUrl(false)).then(async (response) => {', html)
        self.assertNotIn('fetch(statusUrl(true)).then(async (response) => {', html)
        self.assertIn('streamResult.textContent = `Error: ${probeText}`;', html)
        self.assertIn('if (timerEventSource && timerEventSource.readyState === EventSource.CLOSED) {', html)
        self.assertIn('streamStatus.textContent = "Stream disconnected.";', html)
        self.assertNotIn("Stream error or reconnecting...", html)
        self.assertNotIn("Writes controller state JSON and sends it to the Pico.", html)
        self.assertNotIn("Helper: Generate 5s pin test", html)
        self.assertNotIn("Helper: Generate pump/lights", html)
        self.assertNotIn("GET /api/controllers/{role}", html)
        self.assertNotIn("GET /api/controllers/{role}?stream=true", html)

    def test_settings_page_shows_short_git_dirty_reason(self):
        html = render_system_info_page(
            {
                "host": {"hostname": "plamp", "network": []},
                "software": {
                    "path": "/repo/plamp",
                    "user_name": "hugo",
                    "user_is_sudoer": True,
                    "user_has_serial_access": True,
                    "user_has_video_access": True,
                    "os_name": "Debian GNU/Linux",
                    "os_arch": "aarch64",
                    "os_version": "12 (bookworm)",
                    "git_short_commit": "abc123",
                    "git_branch": "main",
                    "git_dirty": True,
                    "git_dirty_files": ["plamp_web/server.py", "tests/test_pages.py", "deploy/bootstrap/install-plamp.sh"],
                    "git_commit_timestamp": "2026-05-08T09:00:00+00:00",
                    "mpremote_path": "/home/hugo/.local/bin/mpremote",
                    "mpremote_version": "mpremote 1.28.0",
                },
                "storage": {"path": "/repo/plamp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
                "tools": {"pyserial": "3.5"},
                "paths": {"repo_root": "/repo/plamp", "data_dir": "/repo/plamp/data"},
            }
        )

        self.assertIn("Git dirty", html)
        self.assertIn("yes: plamp_web/server.py, tests/test_pages.py, ...", html)

    def test_api_test_page_has_copyable_curl_commands_and_camera_paging_inputs(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        for target in [
            "camera-capture-curl-command",
            "list-captures-curl-command",
            "get-status-curl-command",
            "stream-status-curl-command",
        ]:
            self.assertIn(f'data-copy-target="{target}"', html)
        self.assertIn('id="list-captures-limit"', html)
        self.assertIn('id="list-captures-offset"', html)
        self.assertIn('id="list-captures-camera-id"', html)
        self.assertIn('id="camera-capture-camera-id"', html)
        self.assertIn("listCapturesLimit()", html)
        self.assertIn("listCapturesOffset()", html)
        self.assertIn("listCapturesCameraId()", html)
        self.assertIn("captureCameraId()", html)
        self.assertIn("copyCurlCommand", html)
        self.assertIn("navigator.clipboard.writeText", html)
        self.assertIn("/api/camera/captures?limit=10&amp;offset=0", html)

    def test_api_test_page_keeps_status_controls(self):
        html = render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h")

        self.assertIn('id="status-path-list"', html)
        self.assertIn('id="get-status-curl-command"', html)
        self.assertIn('id="stream-status-curl-command"', html)
        self.assertNotIn('id="put-curl-command"', html)


if __name__ == "__main__":
    unittest.main()
