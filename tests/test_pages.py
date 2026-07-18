import html as html_module
import json
import re
import unittest
from pathlib import Path

from plamp_web.pages import json_script_text, main_nav, render_api_test_page, render_controller_page, render_settings_page, render_system_info_page


def static_timer_dashboard(*args, **kwargs) -> str:
    return Path("plamp_web/static/index.html").read_text(encoding="utf-8")


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_static_file_bootstraps_only_through_rest(self):
        path = Path("plamp_web/static/index.html")
        self.assertTrue(path.is_file())
        html = path.read_text(encoding="utf-8")

        for endpoint in ("/api/timer-config", "/api/host-time", "/api/config", "/api/system"):
            self.assertIn(f'fetch("{endpoint}")', html)
        self.assertIn("let clockTimeFormat", html)
        self.assertIn("let timerRoles", html)
        self.assertIn("let timerChannels", html)
        self.assertIn("let timerHostSecondsAtLoad", html)
        self.assertIn("function renderMainNav", html)
        self.assertIn("function populateCameraSelectors", html)
        self.assertIn("async function bootstrapDashboard", html)
        bootstrap = html.split("async function bootstrapDashboard()", 1)[1].split("function formatChangeTime", 1)[0]
        self.assertLess(bootstrap.index('fetch("/api/system")'), bootstrap.index("startTimerStreams();"))
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

    def hidden_scheduler_controllers_payload(self, html: str) -> dict:
        match = re.search(
            r'<script id="hidden-scheduler-controllers" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def scheduler_empty_state_block(self, html: str) -> str:
        match = re.search(
            r'(<div class="pico-scheduler-block pico-scheduler-new" data-controller-key="">.*?</div>)\s*<button id="save-controllers"',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def scheduler_blocks(self, html: str) -> list[str]:
        return re.findall(r'<div class="pico-scheduler-block[^"]*" data-controller-key=".*?">.*?</div>', html, re.DOTALL)

    def test_timer_dashboard_page_links_to_settings(self):
        html = static_timer_dashboard(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('navLink("/settings", "Settings")', html)
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


    def test_pages_use_same_nav_with_github_link(self):
        expected = '<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | [rev unknown]</nav>'
        settings_summary = {
            "config": {"controllers": {}, "devices": {}, "cameras": {}},
            "detected": {"picos": [], "cameras": []},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "software": {},
            "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
        }

        pages = [
            render_settings_page(settings_summary),
            render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h"),
        ]

        for html in pages:
            self.assertIn(expected, html)
        dashboard = static_timer_dashboard()
        for link in ('navLink("/", "Plamp")', 'navLink("/settings", "Settings")', 'navLink("/system", "System")', 'navLink("/api/test", "API test")'):
            self.assertIn(link, dashboard)

    def test_pages_use_same_nav_with_system_link(self):
        expected = '<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/system">System</a> | <a href="/api/test">API test</a> | [rev unknown]</nav>'
        html = render_system_info_page({"host": {"hostname": "sprout"}})
        self.assertIn(expected, html)
        self.assertEqual(html.count("<nav>"), 1)

    def test_pages_can_include_controller_links_in_nav(self):
        expected = '<a href="/controllers/octo_relay">octo_relay</a>'
        settings_summary = {
            "config": {"controllers": {}, "devices": {}, "cameras": {}},
            "detected": {"picos": [], "cameras": []},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "software": {},
            "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
        }

        pages = [
            render_settings_page(settings_summary, ["octo_relay"]),
            render_system_info_page({"host": {"hostname": "sprout"}}, controller_ids=["octo_relay"]),
            render_api_test_page(["octo_relay"], "octo_relay", "{}", "12h", controller_ids=["octo_relay"]),
        ]

        for page in pages:
            self.assertIn(expected, page)
        dashboard = static_timer_dashboard()
        self.assertIn('navLink(`/controllers/${encodeURIComponent(controllerId)}`, controllerId)', dashboard)

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

    def test_controller_page_includes_report_pulse_and_serial_log_controls(self):
        status = {
            "state": "connected",
            "serial": "abc",
            "firmware": {"current": True},
            "raw_lines": ["report evidence"],
        }
        html = render_controller_page(
            "pump_lights",
            [
                {"id": "pump", "name": "Pump", "pin": 21, "type": "gpio", "visibility": "visible"},
                {"id": "fan", "name": "Fan", "pin": 22, "type": "pwm", "visibility": "visible"},
                {"id": "hidden", "name": "Hidden", "pin": 23, "type": "gpio", "visibility": "hidden"},
            ],
            status,
            [{"at": "now", "direction": "tx", "text": "r"}],
        )

        self.assertIn('<button id="report-now" type="button">Report now</button>', html)
        self.assertIn('<input id="pulse-pin" name="pin" type="number"', html)
        self.assertIn('<input id="pulse-seconds" name="seconds" type="number"', html)
        self.assertIn('<button id="pulse-send" type="button">Pulse</button>', html)
        self.assertIn("<td>Pump</td>", html)
        self.assertIn("<td>21</td>", html)
        self.assertIn("<td>Fan</td>", html)
        self.assertIn("<td>22</td>", html)
        self.assertIn("<td>Hidden</td>", html)
        self.assertIn("<td>23</td>", html)
        self.assertIn("Are you sure you want to pulse pin", html)
        self.assertIn('id="refresh-log"', html)
        self.assertIn('postCommand(`/api/controllers/${encodeURIComponent(controller)}/pins/${encodeURIComponent(pin)}/pulse`', html)
        self.assertIn('postCommand(`/api/controllers/${encodeURIComponent(controller)}/commands/report`', html)
        self.assertIn('fetch(`/api/controllers/${encodeURIComponent(controller)}/serial-log`', html)
        self.assertIn('}).join("\\n");', html)
        self.assertNotIn('}).join("\n");', html)
        self.assertIn("<h2>Diagnostics</h2>", html)
        self.assertIn('id="controller-diagnostics"', html)
        self.assertIn('<button id="refresh-diagnostics" type="button">Refresh diagnostics</button>', html)
        self.assertIn('fetch(`/api/controllers/${encodeURIComponent(controller)}`)', html)
        self.assertIn("diagnosticsNode.textContent = JSON.stringify(data.telemetry || data, null, 2);", html)
        self.assertIn('setStatus("Diagnostics refreshed.");', html)
        self.assertIn(html_module.escape(json.dumps(status, indent=2, sort_keys=True)), html)

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

    def test_settings_page_device_editor_offers_disabled_and_hidden(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"pump_lights": {"type": "pico_scheduler"}},
                    "devices": {"pump": {"controller": "pump_lights", "pin": 3, "editor": "disabled"}},
                    "cameras": {},
                },
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        self.assertIn('<option value="disabled" selected>disabled</option>', html)
        self.assertIn('<option value="hidden">hidden</option>', html)

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

    def test_settings_page_includes_plamp_setup_without_system_status_or_hostname_editor(self):
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
        self.assertIn("<th>Label</th>", html)
        self.assertNotIn("<th>Role</th>", html)
        self.assertIn("Pump lights", html)
        self.assertIn("Main pump", html)
        self.assertIn("Tent cam", html)
        self.assertIn('href="/settings"', html)
        self.assertIn('href="/api/test"', html)
        self.assertNotIn('href="/config"', html)
        self.assertNotIn("System status", html)
        self.assertNotIn("Device control", html)
        self.assertNotIn('id="hostname-input"', html)
        self.assertNotIn('id="hostname-confirm"', html)
        self.assertNotIn('id="hostname-status"', html)

    def test_settings_page_preserves_config_order_for_setup_rows(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {"second": {"pico_serial": "2"}, "first": {"pico_serial": "1"}},
                    "devices": {
                        "lights": {"controller": "second", "pin": 3, "editor": "clock_window"},
                        "pump": {"controller": "first", "pin": 2, "editor": "cycle"},
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

    def test_settings_page_merges_renamed_camera_with_detected_hardware(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {"picam0": {"label": "Tent", "detected_key": "rpicam_cam0"}}},
                "detected": {"picos": [], "cameras": [{"key": "rpicam:cam0", "model": "imx708", "lens": "wide"}]},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        self.assertIn('value="picam0"', html)
        self.assertIn('class="camera-detected-key"', html)
        self.assertIn('<option value="rpicam_cam0" selected>', html)
        self.assertIn("Camera Module 3 Wide | wide", html)
        self.assertEqual(html.count('class="camera-row"'), 1)

    def test_settings_page_pairs_existing_renamed_camera_without_saved_detected_key(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {"picam0": {}}},
                "detected": {"picos": [], "cameras": [{"key": "rpicam:cam0", "model": "imx708", "lens": "wide"}]},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        self.assertIn('value="picam0"', html)
        self.assertIn('<option value="rpicam_cam0" selected>', html)

    def test_settings_page_posts_config_section_updates_from_forms(self):
        html = render_settings_page({"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}})

        self.assertIn("collectControllers()", html)
        self.assertIn("collectControllerDevices()", html)
        self.assertIn("collectCameras()", html)
        self.assertIn("function controllerRenames()", html)
        self.assertIn("collectConfigWithControllerRenames()", html)
        self.assertIn('saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())', html)
        self.assertIn('saveSection("devices-status", "/api/config", collectConfigWithControllerRenames())', html)
        self.assertNotIn('saveSection("devices-status", "/api/config/devices", collectDevices())', html)
        self.assertIn('"/api/config/cameras"', html)
        self.assertIn('label: row.querySelector(".device-label").value.trim()', html)
        self.assertIn('const labelInput = row.querySelector(".controller-label");', html)
        self.assertIn('const label = labelInput.value.trim();', html)
        self.assertIn('label: row.querySelector(".camera-label").value.trim()', html)
        self.assertIn('detected_key: row.querySelector(".camera-detected-key").value', html)
        self.assertIn('const pinValue = row.querySelector(".device-pin").value', html)
        self.assertIn('pin: Number(pinValue)', html)
        self.assertIn("if (response.ok) window.location.reload();", html)
        self.assertIn("throw new Error(`Pin required for device ${key}.`);", html)
        self.assertIn('try {', html)
        self.assertIn('catch (error)', html)

    def test_settings_page_keeps_camera_blank_row(self):
        html = render_settings_page({"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}})

        self.assertIn('class="camera-row new-row" data-camera-key=""', html)

    def test_settings_page_does_not_offer_obsolete_report_interval(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "pico_serial": "abc",
                            "report_every": 15,
                            "label": "Pump lights",
                        }
                    },
                    "devices": {"pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle"}},
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertNotIn("Pico poll interval (seconds)", html)
        self.assertNotIn('class="controller-report-every"', html)
        self.assertNotIn("payload.payload.report_every", html)

    def test_settings_page_groups_scheduler_settings_by_controller(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "pico_serial": "abc",
                            "report_every": 10,
                            "label": "Pump lights",
                        },
                        "unused": {
                            "type": "pico_scheduler",
                            "pico_serial": "def",
                            "report_every": 20,
                            "label": "Unused",
                        },
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                        "lights": {"controller": "pump_lights", "pin": 4, "type": "pwm", "editor": "clock_window", "label": "Lights"},
                    },
                    "cameras": {},
                },
                "detected": {
                    "picos": [
                        {"serial": "abc", "port": "/dev/ttyACM0"},
                        {"serial": "def", "port": "/dev/ttyACM1"},
                    ],
                    "cameras": [],
                },
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("<h3>Pico schedulers</h3>", html)
        self.assertEqual(html.count("<h3>Pico schedulers</h3>"), 1)
        self.assertNotIn("<h3>Controllers</h3>", html)
        self.assertEqual(html.count('class="pico-scheduler-block"'), 1)
        self.assertIn('class="pico-scheduler-block" data-controller-key="pump_lights"', html)
        self.assertNotIn('data-controller-key="unused"', html)
        self.assertIn("<th>Assigned peripheral</th>", html)
        self.assertIn("Pump lights", html)
        self.assertIn("/dev/ttyACM0", html)
        self.assertIn("<h4>Devices</h4>", html)
        self.assertIn("<th>Output type</th>", html)
        self.assertNotIn("<h3>Devices</h3>", html)
        self.assertIn('class="device-row new-row"', html)
        self.assertNotIn('class="pico-scheduler-new"', html)

    def test_settings_page_renders_only_devices_for_each_scheduler_controller(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "alpha": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Alpha"},
                        "beta": {"type": "pico_scheduler", "pico_serial": "def", "report_every": 20, "label": "Beta"},
                    },
                    "devices": {
                        "pump": {"controller": "alpha", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                        "fan": {"controller": "beta", "pin": 4, "type": "pwm", "editor": "clock_window", "label": "Fan"},
                    },
                    "cameras": {"rpicam_cam0": {"label": "Tent cam"}},
                },
                "detected": {
                    "picos": [
                        {"serial": "abc", "port": "/dev/ttyACM0"},
                        {"serial": "def", "port": "/dev/ttyACM1"},
                    ],
                    "cameras": [{"key": "rpicam:cam0", "model": "imx708", "lens": "wide"}],
                },
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        alpha_block_start = html.index('class="pico-scheduler-block" data-controller-key="alpha"')
        beta_block_start = html.index('class="pico-scheduler-block" data-controller-key="beta"')
        cameras_start = html.index("<h3>Cameras</h3>")

        alpha_block = html[alpha_block_start:beta_block_start]
        beta_block = html[beta_block_start:cameras_start]

        self.assertIn('data-device-id="pump"', alpha_block)
        self.assertNotIn('data-device-id="fan"', alpha_block)
        self.assertIn('class="device-row new-row" data-device-id=""', alpha_block)
        self.assertIn('data-device-id="fan"', beta_block)
        self.assertNotIn('data-device-id="pump"', beta_block)
        self.assertIn('class="device-row new-row" data-device-id=""', beta_block)
        self.assertIn('value="rpicam_cam0"', html)
        self.assertIn("Camera Module 3 Wide | wide", html)

    def test_settings_page_preserves_hidden_scheduler_controllers_in_combined_save_script(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Pump lights"},
                        "unused": {
                            "type": "pico_scheduler",
                            "pico_serial": "def",
                            "report_every": 20,
                            "label": "Unused & <grow> > flower </script> bloom",
                        },
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                    },
                    "cameras": {},
                },
                "detected": {
                    "picos": [
                        {"serial": "abc", "port": "/dev/ttyACM0"},
                        {"serial": "def", "port": "/dev/ttyACM1"},
                    ],
                    "cameras": [],
                },
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        hidden_payload = self.hidden_scheduler_controllers_payload(html)

        self.assertEqual(
            hidden_payload["unused"],
            {
                "type": "pico_scheduler",
                "config": {"pico_serial": "def", "label": "Unused & <grow> > flower </script> bloom"},
                "settings": {"report_every": 20},
                "devices": {},
            },
        )
        self.assertIn(r'"Unused & <grow> > flower <\/script> bloom"', html)
        self.assertNotIn('"Unused & <grow> > flower </script> bloom"', html)
        self.assertNotIn("&amp;", hidden_payload["unused"]["config"]["label"])
        self.assertNotIn("&lt;", hidden_payload["unused"]["config"]["label"])
        self.assertNotIn("&gt;", hidden_payload["unused"]["config"]["label"])
        self.assertIn('const hiddenControllers = JSON.parse(document.getElementById("hidden-scheduler-controllers").textContent || "{}");', html)
        self.assertIn("const result = structuredClone(hiddenControllers);", html)

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

    def test_settings_page_combined_save_posts_config_to_api_config(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        self.assertIn('saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())', html)
        self.assertNotIn('saveSection("controllers-status", "/api/config/controllers", collectControllers())', html)

    def test_settings_page_grouped_device_save_uses_combined_config_payload(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Pump lights"},
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                    },
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('saveSection("devices-status", "/api/config", collectConfigWithControllerRenames())', html)
        self.assertNotIn('saveSection("devices-status", "/api/config/devices", collectDevices())', html)
        self.assertIn("function collectControllerDevices()", html)
        self.assertIn("function collectConfigWithControllerRenames()", html)

    def test_settings_page_preserves_hidden_controller_fields_when_empty_state_reuses_hidden_id(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "unused": {"type": "pico_scheduler", "pico_serial": "def", "report_every": 20, "label": "Unused"},
                    },
                    "devices": {},
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "def", "port": "/dev/ttyACM1"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('const existingController = hiddenControllers[key] ? structuredClone(hiddenControllers[key]) : (oldKey && hiddenControllers[oldKey] ? structuredClone(hiddenControllers[oldKey]) : {});', html)
        self.assertIn('const isHiddenReuse = !row.dataset.controllerKey && Object.keys(existingController).length > 0;', html)
        self.assertIn('const payload = isHiddenReuse ? existingController : {type, payload: {}, settings: {}};', html)
        self.assertIn('if (!isHiddenReuse || label !== labelInput.defaultValue) payload.settings.label = label;', html)
        self.assertIn('if (!isHiddenReuse || picoSerial !== picoSerialDefault) payload.payload.pico_serial = picoSerial;', html)
        self.assertNotIn("reportEveryInput", html)

    def test_settings_page_collects_devices_with_visible_block_controller_after_rename(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Pump lights"},
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                    },
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('const blockController = row.closest(".pico-scheduler-block")?.querySelector(".controller-row .controller-id")?.value.trim() || "";', html)
        self.assertIn('const controller = blockController || row.dataset.deviceController || "";', html)
        self.assertNotIn('controller: row.querySelector(".device-controller").value || blockController', html)

    def test_settings_page_removes_old_controller_key_after_rename(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "protocon": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Proto"},
                    },
                    "devices": {},
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('const oldKey = row.dataset.controllerKey || "";', html)
        self.assertIn('oldKey && hiddenControllers[oldKey] ? structuredClone(hiddenControllers[oldKey]) : {}', html)
        self.assertIn("if (oldKey && oldKey !== key) delete result[oldKey];", html)

    def test_settings_page_renders_create_block_even_when_scheduler_exists(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Pump lights"},
                        "unused": {"type": "pico_scheduler", "pico_serial": "def", "report_every": 20, "label": "Unused"},
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                    },
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}, {"serial": "def", "port": "/dev/ttyACM1"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        blocks = self.scheduler_blocks(html)

        self.assertEqual(len(blocks), 2)
        self.assertIn('class="pico-scheduler-block" data-controller-key="pump_lights"', blocks[0])
        self.assertIn('class="pico-scheduler-block pico-scheduler-new" data-controller-key=""', blocks[1])
        self.assertIn('class="controller-row new-row" data-controller-key=""', blocks[1])
        self.assertIn('class="device-row new-row" data-device-id=""', blocks[1])
        self.assertIn("<h4>Devices</h4>", blocks[1])

    def test_settings_page_renders_create_path_when_no_scheduler_groups_exist(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "unused": {"type": "pico_scheduler", "pico_serial": "def", "report_every": 20, "label": "Unused"},
                    },
                    "devices": {},
                    "cameras": {},
                },
                "detected": {
                    "picos": [
                        {"serial": "def", "port": "/dev/ttyACM1"},
                    ],
                    "cameras": [],
                },
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        empty_block = self.scheduler_empty_state_block(html)

        self.assertIn('class="controller-row new-row" data-controller-key=""', empty_block)
        self.assertIn('class="device-row new-row" data-device-id=""', empty_block)
        self.assertIn('data-device-controller=""', empty_block)
        self.assertNotIn('class="device-controller" value="" type="hidden"', empty_block)
        self.assertEqual(empty_block.count('class="controller-row'), 1)
        self.assertEqual(empty_block.count('class="device-row'), 1)
        self.assertIn('class="controller-id" placeholder="pump_lights" value=""', empty_block)
        self.assertIn("<h3>Pico schedulers</h3>", html)
        self.assertIn("<h4>Devices</h4>", empty_block)
        self.assertIn("<h3>Cameras</h3>", html)
        self.assertNotIn("<h3>Controllers</h3>", html)
        self.assertIn('const blockController = row.closest(".pico-scheduler-block")?.querySelector(".controller-row .controller-id")?.value.trim() || "";', html)
        self.assertIn('const controller = blockController || row.dataset.deviceController || "";', html)

    def test_settings_page_hydrates_create_block_from_hidden_controller_data(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "pump_lights": {"type": "pico_scheduler", "pico_serial": "abc", "report_every": 10, "label": "Pump lights"},
                        "unused": {"type": "pico_scheduler", "pico_serial": "def", "report_every": 20, "label": "Unused"},
                    },
                    "devices": {
                        "pump": {"controller": "pump_lights", "pin": 3, "type": "gpio", "editor": "cycle", "label": "Pump"},
                    },
                    "cameras": {},
                },
                "detected": {"picos": [{"serial": "abc", "port": "/dev/ttyACM0"}, {"serial": "def", "port": "/dev/ttyACM1"}], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn('function hydrateControllerRowFromHidden(row) {', html)
        self.assertIn('const hiddenController = hiddenControllers[key];', html)
        self.assertIn('const labelInput = row.querySelector(".controller-label");', html)
        self.assertIn('labelInput.defaultValue = hiddenSettings.label || "";', html)
        self.assertIn('const picoSerialSelect = row.querySelector(".controller-pico-serial");', html)
        self.assertIn('picoSerialSelect.dataset.defaultValue = hiddenPayload.pico_serial || "";', html)
        self.assertNotIn("reportEveryInput", html)
        self.assertIn('row.querySelector(".controller-id").addEventListener("input", () => hydrateControllerRowFromHidden(row));', html)

    def test_settings_page_no_longer_renders_hostname_confirm_apply_controls(self):
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

        self.assertNotIn('id="hostname-input"', html)
        self.assertNotIn('id="hostname-confirm"', html)
        self.assertNotIn('id="hostname-status"', html)
        self.assertNotIn('/api/host-config/hostname', html)

    def test_settings_page_uses_hostname_in_title_and_heading(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "sprout", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            }
        )

        self.assertIn("<title>sprout Settings</title>", html)
        self.assertIn("<h1>sprout Settings</h1>", html)

    def test_settings_page_links_to_new_github_issue(self):
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

        self.assertIn('href="https://github.com/hugomatic/plamp/issues/new"', html)
        self.assertIn("Report an issue", html)

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

    def test_pages_link_favicon_svg(self):
        settings_html = render_settings_page(
            {"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}}
        )
        dashboard_html = static_timer_dashboard(
            [],
            "pump_n_lights",
            {"host_time": {"display": "-"}, "host": {"hostname": "plamp"}, "captures": {"items": []}, "timer_states": []},
            "CLOCK_24",
        )
        api_html = render_api_test_page(["pump_n_lights"], "pump_n_lights", '{"channels":[]}', "CLOCK_24")
        expected = '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        self.assertIn(expected, settings_html)
        self.assertIn(expected, dashboard_html)
        self.assertIn(expected, api_html)

    def test_settings_page_explains_camera_capture_dir_and_schedule_and_shows_paths(self):
        html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
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
                    "git_dirty": False,
                    "git_dirty_files": [],
                    "git_commit_timestamp": "2026-05-08T09:00:00+00:00",
                    "mpremote_path": "/home/hugo/.local/bin/mpremote",
                    "mpremote_version": "mpremote 1.28.0",
                },
                "paths": {"repo_root": "/repo/plamp", "data_dir": "/repo/plamp/data"},
                "storage": {"path": "/repo/plamp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
                "tools": {"pyserial": "3.5"},
            }
        )

        self.assertIn("Capture dir must stay inside Plamp root.", html)
        self.assertIn("data/grow/grows/&lt;grow-id&gt;/captures", html)
        self.assertIn("absolute paths are rejected", html)
        self.assertIn("Set it to <code>0</code> to disable scheduling for that camera.", html)
        self.assertIn("<title>plamp Settings</title>", html)
        self.assertIn("<h1>plamp Settings</h1>", html)
        self.assertNotIn("System info", html)
        self.assertNotIn("Operating system", html)

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
