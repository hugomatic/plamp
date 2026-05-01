import unittest

from plamp_web.pages import render_api_test_page, render_settings_page, render_timer_dashboard_page


class PageRenderTests(unittest.TestCase):
    def test_timer_dashboard_page_links_to_settings(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn('<a href="/settings">Settings</a>', html)
        self.assertNotIn('href="/config"', html)


    def test_pages_use_same_nav_with_github_link(self):
        expected = '<nav><a href="/">Plamp</a> | <a href="/settings">Settings</a> | <a href="/api/test">API test</a> | <a href="https://github.com/hugomatic/plamp">GitHub</a></nav>'
        settings_summary = {
            "config": {"controllers": {}, "devices": {}, "cameras": {}},
            "detected": {"picos": [], "cameras": []},
            "host": {"hostname": "plamp", "network": []},
            "picos": [],
            "software": {},
            "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
        }

        pages = [
            render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0),
            render_settings_page(settings_summary),
            render_api_test_page(["pump_lights"], "pump_lights", "{}", "12h"),
        ]

        for html in pages:
            self.assertIn(expected, html)
            self.assertEqual(html.count("<nav>"), 1)

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
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertLess(
            html.index('<img id="camera-viewer"'),
            html.index('<div class="camera-actions">'),
        )


    def test_timer_dashboard_camera_controls_include_camera_selector_and_total(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0, ["rpicam_cam0", "rpicam_cam1"])

        self.assertIn('<option value="rpicam_cam0">rpicam_cam0</option>', html)
        self.assertIn('<option value="rpicam_cam1">rpicam_cam1</option>', html)
        self.assertIn('params.set("camera_id", cameraCaptureCamera.value);', html)
        self.assertIn('const total = Number(data.total ?? 0);', html)
        self.assertIn('cameraCapturePageStatus.textContent = `Page ${currentPage} of ${cameraCaptureTotalPages} | Showing ${start}-${end} of ${cameraCaptureTotal}`;', html)
        self.assertIn('cameraCaptureOffset = pageOffset();', html)
        self.assertIn('cameraCapturePage.max = String(Math.max(1, cameraCaptureTotalPages));', html)
        self.assertIn('if (capture.camera_id) parts.push("camera " + capture.camera_id);', html)

    def test_timer_dashboard_capture_list_is_compact_and_scrollable(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

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

    def test_timer_dashboard_capture_filter_is_applied_before_paging(self):
        html = render_timer_dashboard_page(["pump_lights"], "12h", {"pump_lights": []}, 0)

        self.assertIn("function cameraCaptureRequestUrl()", html)
        self.assertIn('params.set("source", "camera_roll");', html)
        self.assertIn('params.set("source", "grow");', html)
        self.assertIn('params.set("grow_id", filter.slice(5));', html)
        self.assertIn("fetch(cameraCaptureRequestUrl())", html)
        self.assertNotIn("visibleCameraCaptures", html)

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
        self.assertIn("const event = item.event || {id: channel.id, pin: channel.pin, type: channel.type || \"gpio\"};", html)


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
        self.assertIn("<th>Port</th><th>USB Device</th><th>Serial</th><th>Assigned</th><th>USB ID</th>", html)
        self.assertNotIn("<th>Role</th>", html)
        self.assertIn("Pump lights", html)
        self.assertIn("Main pump", html)
        self.assertIn("Tent cam", html)
        self.assertIn('href="/settings"', html)
        self.assertIn('href="/api/test"', html)
        self.assertNotIn('href="/config"', html)

    def test_settings_page_shows_peripheral_assignment_status(self):
        html = render_settings_page(
            {
                "config": {
                    "controllers": {
                        "alpha": {"type": "manual", "pico_serial": "abc"},
                        "beta": {"pico_serial": "abc"},
                    },
                    "devices": {},
                    "cameras": {},
                },
                "detected": {
                    "picos": [],
                    "cameras": [],
                },
                "host": {"hostname": "plamp", "network": []},
                "picos": [
                    {"serial": "abc", "port": "/dev/ttyACM0", "usb_device": "USB Serial", "vendor_id": "1234", "product_id": "abcd"},
                    {"serial": "def", "port": "/dev/ttyACM1", "usb_device": "USB Serial", "vendor_id": "1234", "product_id": "abcd"},
                ],
                "software": {},
                "storage": {},
            }
        )

        self.assertIn("<th>Assigned</th>", html)
        self.assertIn("<td>beta</td>", html)
        self.assertNotIn("<td>alpha, beta</td>", html)
        self.assertIn("<td>Unassigned</td>", html)

    def test_settings_page_uses_detected_picos_when_status_picos_are_missing_or_empty(self):
        detected_picos = [
            {"serial": "abc", "port": "/dev/ttyACM0", "usb_device": "USB Serial", "vendor_id": "1234", "product_id": "abcd"},
        ]

        missing_status_html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": detected_picos, "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "software": {},
                "storage": {},
            }
        )
        empty_status_html = render_settings_page(
            {
                "config": {"controllers": {}, "devices": {}, "cameras": {}},
                "detected": {"picos": detected_picos, "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {},
                "storage": {},
            }
        )

        for html in [missing_status_html, empty_status_html]:
            self.assertIn("/dev/ttyACM0", html)
            self.assertIn("<td>Unassigned</td>", html)

    def test_settings_page_uses_five_column_empty_peripherals_row(self):
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

        self.assertIn('<tr><td colspan="5">No peripherals found.</td></tr>', html)

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
        self.assertIn('data-camera-detected-key="rpicam_cam0"', html)
        self.assertIn("Detected: Camera Module 3 Wide wide", html)
        self.assertNotIn('value="rpicam_cam0"', html)
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
        self.assertIn('data-camera-detected-key="rpicam_cam0"', html)
        self.assertNotIn('value="rpicam_cam0"', html)

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
        self.assertIn('detected_key: row.dataset.cameraDetectedKey || ""', html)
        self.assertIn('const pinValue = row.querySelector(".device-pin").value', html)
        self.assertIn('pin: Number(pinValue)', html)
        self.assertIn("if (response.ok) window.location.reload();", html)
        self.assertIn("throw new Error(`Pin required for device ${key}.`);", html)
        self.assertIn('try {', html)
        self.assertIn('catch (error)', html)

    def test_settings_page_keeps_camera_blank_row(self):
        html = render_settings_page({"config": {"controllers": {}, "devices": {}, "cameras": {}}, "detected": {"picos": [], "cameras": []}, "host": {"hostname": "plamp", "network": []}, "picos": [], "software": {}, "storage": {}})

        self.assertIn('class="camera-row new-row" data-camera-key=""', html)

    def test_settings_page_edits_controller_type_and_report_interval(self):
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

        self.assertIn("<th>Report every seconds</th>", html)
        self.assertIn('class="controller-report-every"', html)
        self.assertIn('value="15"', html)
        self.assertIn("report_every: Number(reportEvery)", html)

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
        self.assertNotIn("<h3>Controllers</h3>", html)
        self.assertEqual(html.count('class="pico-scheduler-block"'), 1)
        self.assertIn('class="pico-scheduler-block" data-controller-key="pump_lights"', html)
        self.assertNotIn('data-controller-key="unused"', html)
        self.assertIn("<th>Assigned peripheral</th>", html)
        self.assertIn("Pump lights", html)
        self.assertIn('value="10"', html)
        self.assertIn("/dev/ttyACM0", html)
        self.assertIn("<th>Output type</th>", html)
        self.assertNotIn("<h3>Devices</h3>", html)
        self.assertNotIn('class="device-row new-row"', html)
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
        self.assertIn('data-device-id="fan"', beta_block)
        self.assertNotIn('data-device-id="pump"', beta_block)
        self.assertIn('value="rpicam_cam0"', html)
        self.assertIn("Detected: Camera Module 3 Wide wide", html)

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
