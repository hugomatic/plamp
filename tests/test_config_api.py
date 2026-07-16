import copy
import json
import subprocess
import tempfile
import unittest
from datetime import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from plamp.pico_health import PicoHealth, failed_health
from plamp.usb_events import UsbSerialEvent

import plamp_web.server as server


class DummyMonitor:
    def __init__(self, pico_serial: str, last_report=None):
        self.pico_serial = pico_serial
        self.started = False
        self.stopped = False
        self.joined = False
        self.woken = False
        self.sent_commands = []
        self.serial_log_entries = []
        self.last_report = last_report

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self) -> None:
        self.joined = True

    def wake(self) -> None:
        self.woken = True

    def send_serial_command(self, command: str):
        self.sent_commands.append(command)
        return {"role": "pump_lights", "command": command}

    def serial_log(self):
        return list(self.serial_log_entries)

    def snapshot(self):
        return {"last_report": self.last_report}


class FakeSerial:
    def __init__(self, port="/dev/ttyACM0"):
        self.port = port
        self.is_open = True
        self.writes = []
        self.flushed = False

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        self.flushed = True

    def close(self):
        self.is_open = False


class ConfigApiTests(unittest.TestCase):
    def test_startup_resolves_application_revision_once(self):
        previous_revision = server.APP_REVISION
        try:
            with (
                patch.object(server, "ensure_data_dir"),
                patch.object(server, "configure_logging"),
                patch.object(server, "start_configured_monitors"),
                patch.object(server, "start_usb_observer"),
                patch.object(server, "get_or_start_camera_worker"),
                patch.object(server, "set_app_revision") as set_app_revision,
                patch.object(server, "git_output", return_value="ebaf545") as git_output,
            ):
                server.startup()

            self.assertEqual(server.APP_REVISION, "ebaf545")
            set_app_revision.assert_called_once_with("ebaf545")
            git_output.assert_called_once_with(["git", "rev-parse", "--short", "HEAD"], repo_root=server.REPO_ROOT)
        finally:
            server.APP_REVISION = previous_revision

    def scheduler_controller(self, *, serial: str | None = None, report_every: int = 10, devices: dict | None = None):
        config = {}
        if serial:
            config["pico_serial"] = serial
        return {
            "type": "pico_scheduler",
            "config": config,
            "settings": {"report_every": report_every},
            "devices": devices or {},
        }

    def scheduled_output(self, pin: int, *, output_type: str = "gpio", kind: str = "cycle", programming: str | None = None, visibility: str | None = None):
        config = {"pin": pin, "output_type": output_type}
        if visibility:
            config["visibility"] = visibility
        schedule = {"kind": kind}
        if kind == "daily_window":
            schedule.update({"on_time": "06:00", "off_time": "18:00"})
        settings = {"schedule": schedule}
        if programming:
            settings["programming"] = programming
        return {"type": "scheduled_output", "config": config, "settings": settings}

    def make_config(self, root: Path, data: dict) -> Path:
        path = root / "data" / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def healthy_monitor(self):
        return SimpleNamespace(
            require_fresh_report=Mock(return_value={"type": "report", "content": {"devices": []}})
        )

    def test_get_config_returns_config_without_detected_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "abc"},
                            "settings": {"report_every": 10},
                            "devices": {
                                "pump": {
                                    "type": "scheduled_output",
                                    "config": {"pin": 3, "output_type": "gpio"},
                                    "settings": {"schedule": {"kind": "cycle"}},
                                }
                            },
                        }
                    },
                    "cameras": {"rpicam_cam0": {}},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
            ):
                data = server.get_config()

        self.assertIn("config", data)
        self.assertNotIn("detected", data)
        self.assertEqual(data["config"]["controllers"]["pump_lights"]["payload"]["pico_serial"], "abc")
        self.assertEqual(
            data["config"]["controllers"]["pump_lights"]["settings"]["devices"]["pump"]["editor"]["kind"],
            "cycle",
        )

    def test_system_response_contains_detected_hardware(self):
        with (
            patch.object(server, "enumerate_picos", return_value=[{"serial": "abc", "port": "/dev/ttyACM0"}]),
            patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[{"key": "rpicam:cam0", "index": 0, "model": "imx708_wide", "sensor": "imx708", "lens": "wide"}]),
            patch.object(server, "storage_summary", return_value={"path": "/repo/plamp", "free": "2 GB", "used": "1 GB", "total": "3 GB"}),
            patch.object(server, "computer_hardware_model", return_value="Raspberry Pi Zero 2 W Rev 1.0"),
        ):
            data = server.get_system()

        self.assertEqual(data["detected"]["picos"][0]["serial"], "abc")
        self.assertEqual(data["detected"]["cameras"][0]["key"], "rpicam_cam0")
        self.assertEqual(data["paths"]["repo_root"], str(server.REPO_ROOT.resolve()))
        self.assertEqual(data["paths"]["data_dir"], str(server.DATA_DIR.resolve()))
        self.assertEqual(data["storage"]["path"], "/repo/plamp")
        self.assertEqual(data["storage"]["free"], "2 GB")
        self.assertEqual(data["storage"]["used"], "1 GB")
        self.assertEqual(data["storage"]["total"], "3 GB")
        self.assertEqual(data["host"]["hardware_model"], "Raspberry Pi Zero 2 W Rev 1.0")

    def test_status_response_contains_config_tree_and_controller_telemetry(self):
        config = {
            "controllers": {
                "pump_lights": {
                    "type": "pico_scheduler",
                    "payload": {"report_every": 10, "devices": []},
                    "settings": {"devices": {}},
                }
            },
            "cameras": {},
        }
        monitor = DummyMonitor("abc")
        report = {"type": "report", "content": {"devices": [{"pin": 3, "type": "gpio"}]}}
        monitor.snapshot = lambda: {"connected": True, "port": "/dev/ttyACM0", "last_report": report}
        with (
            patch.object(server, "load_config", return_value=config),
            patch.object(server, "monitors", {"pump_lights": monitor}),
            patch.object(server, "monitor_summaries", return_value={"pump_lights": {"state": "idle"}}),
            patch.object(server, "camera_worker_summary", return_value={"state": "idle"}),
        ):
            data = server.get_status()

        self.assertIn("config", data)
        self.assertEqual(data["config"], config)
        self.assertEqual(
            data["controllers"]["pump_lights"]["telemetry"],
            {"connected": True, "port": "/dev/ttyACM0", "last_report": report},
        )
        self.assertNotIn("system", data)

    def test_get_status_filters_nested_paths_and_preserves_order(self):
        config = {
            "controllers": {
                "pump_lights": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "abc", "report_every": 10, "devices": []},
                    "settings": {"label": "Pump lights", "devices": {}},
                }
            },
            "cameras": {},
        }
        telemetry = {"connected": True, "port": "/dev/ttyACM0"}
        monitor = DummyMonitor("abc")
        monitor.snapshot = lambda: telemetry
        with (
            patch.object(server, "load_config", return_value=config),
            patch.object(server, "monitors", {"pump_lights": monitor}),
            patch.object(server, "monitor_summaries", return_value={}),
            patch.object(server, "camera_worker_summary", return_value={"state": "idle"}),
        ):
            data = server.get_status(
                path=["config.controllers.pump_lights", "controllers.pump_lights.telemetry"]
            )

        self.assertEqual(
            data,
            [
                {
                    "path": "config.controllers.pump_lights",
                    "value": config["controllers"]["pump_lights"],
                },
                {
                    "path": "controllers.pump_lights.telemetry",
                    "value": telemetry,
                },
            ],
        )

    def test_get_status_rejects_invalid_path(self):
        config = {"controllers": {}, "cameras": {}}
        with (
            patch.object(server, "load_config", return_value=config),
            patch.object(server, "monitor_summaries", return_value={}),
            patch.object(server, "camera_worker_summary", return_value={"state": "idle"}),
        ):
            with self.assertRaises(HTTPException) as cm:
                server.get_status(path=["config.controllers.missing"])

        self.assertEqual(cm.exception.status_code, 404)
        self.assertIn("config.controllers.missing", str(cm.exception.detail))

    def test_status_stream_emits_only_when_filtered_node_changes(self):
        config = {
            "controllers": {
                "pump_lights": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "abc", "report_every": 10, "devices": []},
                    "settings": {"label": "Pump lights", "devices": {}},
                }
            },
            "cameras": {},
        }
        status_one = {
            "config": config,
            "controllers": {
                "pump_lights": {
                    **config["controllers"]["pump_lights"],
                    "telemetry": {"connected": True, "port": "/dev/ttyACM0"},
                }
            },
            "monitors": {},
            "camera_worker": {"state": "idle"},
        }
        status_two = {
            "config": {
                "controllers": {
                    "pump_lights": {
                        "type": "pico_scheduler",
                        "payload": {"pico_serial": "abc", "report_every": 10, "devices": []},
                        "settings": {"label": "Pump lights changed", "devices": {}},
                    }
                },
                "cameras": {},
            },
            "controllers": {
                "pump_lights": {
                    **config["controllers"]["pump_lights"],
                    "telemetry": {"connected": True, "port": "/dev/ttyACM0"},
                }
            },
            "monitors": {},
            "camera_worker": {"state": "idle"},
        }
        status_three = {
            "config": status_two["config"],
            "controllers": {
                "pump_lights": {
                    **config["controllers"]["pump_lights"],
                    "telemetry": {"connected": False, "port": None},
                }
            },
            "monitors": {},
            "camera_worker": {"state": "idle"},
        }
        with (
            patch.object(server, "status_response_for_paths", side_effect=[status_one, status_two, status_three]),
            patch.object(server.time, "sleep", return_value=None),
        ):
            events = server.iter_status_events(
                ["config.controllers.pump_lights", "controllers.pump_lights.telemetry"],
                poll_interval=0.01,
            )
            first = next(events)
            second = next(events)

        def parse_event(text: str) -> tuple[str, object]:
            lines = text.splitlines()
            event_name = lines[0].removeprefix("event: ")
            payload = json.loads(lines[1].removeprefix("data: "))
            return event_name, payload

        first_event, first_payload = parse_event(first)
        second_event, second_payload = parse_event(second)

        self.assertEqual(first_event, "snapshot")
        self.assertEqual(second_event, "update")
        self.assertEqual(first_payload[0]["value"]["settings"]["label"], "Pump lights")
        self.assertEqual(second_payload[0]["value"]["settings"]["label"], "Pump lights changed")
        self.assertEqual(first_payload[1]["value"]["connected"], True)

    def test_get_status_stream_returns_streaming_response(self):
        with patch.object(server, "status_response", return_value={"config": {"controllers": {}, "cameras": {}}, "controllers": {}, "monitors": {}, "camera_worker": {"state": "idle"}}):
            response = server.get_status(stream=True, path=["config"])

        self.assertIsInstance(response, StreamingResponse)
        self.assertEqual(response.media_type, "text/event-stream")

    @patch.object(server, "run_plampctl_action")
    def test_post_system_restart_invokes_plampctl_restart(self, run_plampctl_action):
        run_plampctl_action.return_value = {"message": "restarted"}

        result = server.post_system_restart()

        self.assertEqual(result["message"], "restarted")
        run_plampctl_action.assert_called_once_with("restart")

    @patch.object(server, "run_plampctl_action")
    def test_post_system_reinstall_invokes_plampctl_reinstall(self, run_plampctl_action):
        run_plampctl_action.return_value = {"message": "reinstalled"}

        result = server.post_system_reinstall()

        self.assertEqual(result["message"], "reinstalled")
        run_plampctl_action.assert_called_once_with("reinstall")

    @patch.object(server, "run_plampctl_action")
    def test_post_system_upgrade_invokes_plampctl_upgrade(self, run_plampctl_action):
        run_plampctl_action.return_value = {"message": "upgraded"}

        result = server.post_system_upgrade()

        self.assertEqual(result["message"], "upgraded")
        run_plampctl_action.assert_called_once_with("upgrade")

    def test_runtime_route_is_removed(self):
        routes = {route.path for route in server.app.routes}
        self.assertNotIn("/runtime", routes)

    def test_scheduler_controller_normalizes_to_payload_and_settings(self):
        controller = {
            "type": "pico_scheduler",
            "payload": {
                "pico_serial": "abc",
                "report_every": 10,
                "devices": [
                    {
                        "pin": 3,
                        "type": "gpio",
                        "pattern": [{"val": 1, "dur": 90}, {"val": 0, "dur": 810}],
                    }
                ],
            },
            "settings": {
                "label": "Pump lights",
                "devices": {
                    "pump": {
                        "pin": 3,
                        "output_type": "gpio",
                        "label": "Pump",
                        "icon": "pump",
                        "display_order": 0,
                        "visibility": "visible",
                        "programming": "enabled",
                        "editor": {
                            "kind": "cycle",
                            "on_seconds": 90,
                            "off_seconds": 810,
                            "start_at_seconds": 0,
                        },
                    }
                }
            },
        }

        normalized = server.config_view({"controllers": {"pump_lights": controller}, "cameras": {}})

        self.assertEqual(normalized["controllers"]["pump_lights"], controller)

    def test_legacy_scheduler_controller_migrates_to_payload_and_settings(self):
        normalized = server.config_view(
            {
                "controllers": {
                    "pump_lights": {
                        "type": "pico_scheduler",
                        "config": {"pico_serial": "abc", "label": "Pump lights"},
                        "settings": {"report_every": 10},
                        "devices": {
                            "pump": {
                                "type": "scheduled_output",
                                "config": {
                                    "pin": 3,
                                    "output_type": "gpio",
                                    "label": "Pump",
                                    "icon": "pump",
                                },
                                "settings": {
                                    "schedule": {
                                        "kind": "cycle",
                                        "on_seconds": 90,
                                        "off_seconds": 810,
                                        "start_at_seconds": 0,
                                    }
                                },
                            }
                        },
                    }
                },
                "cameras": {},
            }
        )

        self.assertEqual(
            normalized["controllers"]["pump_lights"],
            {
                "type": "pico_scheduler",
                "payload": {
                    "pico_serial": "abc",
                    "report_every": 10,
                    "devices": [
                        {
                            "pin": 3,
                            "type": "gpio",
                            "pattern": [{"val": 1, "dur": 90}, {"val": 0, "dur": 810}],
                        }
                    ],
                },
                "settings": {
                    "label": "Pump lights",
                    "devices": {
                        "pump": {
                            "pin": 3,
                            "output_type": "gpio",
                            "label": "Pump",
                            "icon": "pump",
                            "display_order": 0,
                            "visibility": "visible",
                            "programming": "enabled",
                            "editor": {
                                "kind": "cycle",
                                "on_seconds": 90,
                                "off_seconds": 810,
                                "start_at_seconds": 0,
                            },
                        }
                    }
                },
            },
        )

    def test_scheduler_controller_rejects_missing_payload_pin(self):
        with self.assertRaisesRegex(ValueError, "payload devices pins"):
            server.config_view(
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "payload": {"report_every": 10, "devices": []},
                            "settings": {
                                "devices": {
                                    "pump": {
                                        "pin": 3,
                                        "display_order": 0,
                                        "visibility": "visible",
                                        "programming": "enabled",
                                        "editor": {"kind": "cycle"},
                                    }
                                }
                            },
                        }
                    },
                    "cameras": {},
                }
            )

    def test_scheduler_controller_rejects_extra_payload_pin(self):
        with self.assertRaisesRegex(ValueError, "payload devices pins"):
            server.config_view(
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "payload": {
                                "report_every": 10,
                                "devices": [{"pin": 3, "type": "gpio", "pattern": []}],
                            },
                            "settings": {"devices": {}},
                        }
                    },
                    "cameras": {},
                }
            )

    def test_scheduler_controller_rejects_duplicate_payload_pin(self):
        with self.assertRaisesRegex(ValueError, "duplicate payload pin"):
            server.config_view(
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "payload": {
                                "report_every": 10,
                                "devices": [
                                    {"pin": 3, "type": "gpio", "pattern": []},
                                    {"pin": 3, "type": "gpio", "pattern": []},
                                ],
                            },
                            "settings": {
                                "devices": {
                                    "pump": {
                                        "pin": 3,
                                        "display_order": 0,
                                        "visibility": "visible",
                                        "programming": "enabled",
                                        "editor": {"kind": "cycle"},
                                    }
                                }
                            },
                        }
                    },
                    "cameras": {},
                }
            )

    def test_get_controllers_returns_flat_discovery_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "abc"},
                            "settings": {"report_every": 10},
                            "devices": {},
                        },
                        "hello_doser": {"type": "pico_doser", "config": {}, "settings": {}, "devices": {}},
                    },
                    "cameras": {},
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                payload = server.get_controllers()

        self.assertEqual(
            payload,
            {
                "controllers": {
                    "pump_lights": {"firmware": "pico_scheduler"},
                    "hello_doser": {"firmware": "pico_doser"},
                }
            },
        )

    def test_get_controller_returns_full_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "abc"},
                            "settings": {"report_every": 10},
                            "devices": {},
                        }
                    },
                    "cameras": {},
                },
            )
            timer_path = root / "data" / "timers" / "pump_lights.json"
            timer_path.parent.mkdir(parents=True)
            timer_path.write_text(
                json.dumps(
                    {
                        "report_every": 10,
                        "devices": [{"type": "gpio", "pin": 3, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", root / "data" / "timers"),
                patch.object(server, "latest_timer_state", return_value=None),
            ):
                payload = server.get_controller("pump_lights")

        self.assertEqual(payload["controller"], "pump_lights")
        self.assertEqual(payload["firmware"], "pico_scheduler")
        self.assertIn("devices", payload)

    def test_put_controller_for_non_scheduler_persists_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"hello_doser": {"type": "pico_doser", "config": {}, "settings": {}, "devices": {}}},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
            ):
                payload = server.put_controller(
                    "hello_doser",
                    {"controller": "hello_doser", "firmware": "pico_doser", "report_every": 5, "message": "hello"},
                )

            saved = json.loads((timers_dir / "hello_doser.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["success"])
        self.assertEqual(payload["firmware"], "pico_doser")
        self.assertEqual(saved, {"report_every": 5, "message": "hello"})

    def test_settings_summary_includes_config_status_and_host_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "abc", "label": "Pump lights"},
                            "settings": {"report_every": 10},
                            "devices": {},
                        }
                    },
                    "cameras": {},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "load_config", return_value={"controllers": {"pump_lights": {}}, "cameras": {}}),
                patch.object(server, "monitor_summaries", return_value={}),
                patch.object(server, "camera_worker_summary", return_value={"state": "idle"}),
                patch.object(server.socket, "gethostname", return_value="sprout"),
                patch.object(server, "host_time_summary", return_value={}),
                patch.object(server, "computer_hardware_model", return_value="Raspberry Pi"),
                patch.object(server, "host_ips", return_value=[]),
                patch.object(server, "default_route", return_value=None),
                patch.object(server, "network_summary", return_value=[]),
                patch.object(server, "enumerate_picos", return_value=[]),
                patch.object(server.hardware_inventory, "detect_rpicam_cameras", return_value=[]),
                patch.object(server, "software_summary", return_value={"name": "plamp"}),
                patch.object(server, "storage_summary", return_value={}),
            ):
                summary = server.settings_summary()

        self.assertIn("config", summary)
        self.assertIn("controllers", summary)
        self.assertIn("camera_worker", summary)
        self.assertEqual(summary["host"]["hostname"], "sprout")
        self.assertEqual(summary["config"]["controllers"]["pump_lights"], {})
        self.assertIn("detected", summary)

    def test_get_settings_page_uses_combined_settings_payload(self):
        with patch.object(
            server,
            "settings_summary",
            return_value={
                "config": {"controllers": {}, "cameras": {}},
                "detected": {"picos": [], "cameras": []},
                "host": {"hostname": "plamp", "network": []},
                "picos": [],
                "software": {"git_short_commit": "abc123", "git_branch": "main", "git_dirty": False},
                "storage": {"path": "/tmp", "free": "1 GB", "used": "1 GB", "total": "2 GB"},
            },
        ):
            response = server.get_settings_page()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Plamp config", response.body)

    def test_get_controller_page_uses_monitor_status_and_serial_log(self):
        monitor = DummyMonitor("abc")
        monitor.serial_log_entries = [{"direction": "tx", "text": "r"}]
        monitor.snapshot = lambda: {"state": "connected", "serial": "abc"}
        with (
            patch.object(server, "get_or_start_monitor", return_value=monitor),
            patch.object(server, "configured_timer_channels", return_value={"pump_lights": [{"id": "pump", "name": "Pump", "pin": 21, "type": "gpio", "visibility": "visible"}]}),
        ):
            response = server.get_controller_page("pump_lights")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pump_lights Pico", response.body)
        self.assertIn(b'<input id="pulse-pin" name="pin" type="number"', response.body)
        self.assertIn(b'<button id="pulse-send" type="button">Pulse</button>', response.body)
        self.assertIn(b"<td>Pump</td>", response.body)
        self.assertIn(b"<td>21</td>", response.body)
        self.assertIn(b"TX r", response.body)

    def test_config_route_is_removed(self):
        routes = {route.path for route in server.app.routes}
        self.assertNotIn("/config", routes)

    def test_get_host_config_returns_hostname(self):
        with patch.object(server.socket, "gethostname", return_value="plamp"):
            data = server.get_host_config()

        self.assertEqual(data, {"hostname": "plamp"})

    def test_post_host_config_hostname_rejects_invalid_value(self):
        with self.assertRaises(HTTPException) as cm:
            server.post_host_config_hostname({"hostname": "bad host name"})

        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("hostname", cm.exception.detail)

    def test_post_host_config_hostname_applies_value(self):
        with patch.object(
            server,
            "apply_hostname",
            return_value={"hostname": "plamp-kiosk", "message": "hostname updated"},
        ) as apply_hostname:
            data = server.post_host_config_hostname({"hostname": "plamp-kiosk"})

        apply_hostname.assert_called_once_with("plamp-kiosk")
        self.assertEqual(data["hostname"], "plamp-kiosk")
        self.assertEqual(data["message"], "hostname updated")

    def test_update_hostname_hosts_file_rewrites_loopback_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            hosts_file = Path(tmp) / "hosts"
            hosts_file.write_text("127.0.0.1\tlocalhost\n127.0.1.1\traspberrypi\n", encoding="utf-8")

            server.update_hostname_hosts_file(hosts_file, "tower")

            self.assertEqual(
                hosts_file.read_text(encoding="utf-8"),
                "127.0.0.1\tlocalhost\n127.0.1.1\ttower\n",
            )

    def test_apply_hostname_updates_hosts_restarts_avahi_and_reports_local_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            hosts_file = Path(tmp) / "hosts"
            hosts_file.write_text("127.0.0.1\tlocalhost\n127.0.1.1\traspberrypi\n", encoding="utf-8")

            with (
                patch.object(server, "HOSTS_FILE", hosts_file),
                patch.object(
                    server.subprocess,
                    "run",
                    side_effect=[
                        subprocess.CompletedProcess(["hostnamectl", "set-hostname", "tower"], 0, "", ""),
                        subprocess.CompletedProcess(["systemctl", "restart", "avahi-daemon"], 0, "", ""),
                        subprocess.CompletedProcess(["avahi-resolve-host-name", "-4", "tower.local"], 0, "192.168.68.56 tower.local\n", ""),
                    ],
                ) as run,
            ):
                data = server.apply_hostname("tower")
                updated_hosts = hosts_file.read_text(encoding="utf-8")

        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["hostnamectl", "set-hostname", "tower"],
                ["systemctl", "restart", "avahi-daemon"],
                ["avahi-resolve-host-name", "-4", "tower.local"],
            ],
        )
        self.assertIn("127.0.1.1\ttower\n", updated_hosts)
        self.assertEqual(
            data,
            {
                "hostname": "tower",
                "message": "hostname updated; /etc/hosts updated; mDNS ready at tower.local",
            },
        )

    def test_apply_hostname_reports_missing_mdns_verification_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            hosts_file = Path(tmp) / "hosts"
            hosts_file.write_text("127.0.0.1\tlocalhost\n", encoding="utf-8")

            with (
                patch.object(server, "HOSTS_FILE", hosts_file),
                patch.object(server.shutil, "which", return_value=None),
                patch.object(
                    server.subprocess,
                    "run",
                    side_effect=[
                        subprocess.CompletedProcess(["hostnamectl", "set-hostname", "tower"], 0, "", ""),
                        subprocess.CompletedProcess(["systemctl", "restart", "avahi-daemon"], 0, "", ""),
                    ],
                ),
            ):
                with self.assertRaises(HTTPException) as cm:
                    server.apply_hostname("tower")

        self.assertEqual(cm.exception.status_code, 500)
        self.assertIn("avahi-utils", cm.exception.detail)

    def test_apply_hostname_timeout_points_to_mdns_multicast_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            hosts_file = Path(tmp) / "hosts"
            hosts_file.write_text("127.0.0.1\tlocalhost\n", encoding="utf-8")

            with (
                patch.object(server, "HOSTS_FILE", hosts_file),
                patch.object(server.shutil, "which", return_value="/usr/bin/avahi-resolve-host-name"),
                patch.object(
                    server.subprocess,
                    "run",
                    side_effect=[
                        subprocess.CompletedProcess(["hostnamectl", "set-hostname", "tower"], 0, "", ""),
                        subprocess.CompletedProcess(["systemctl", "restart", "avahi-daemon"], 0, "", ""),
                        subprocess.TimeoutExpired(["avahi-resolve-host-name", "-4", "tower.local"], 15),
                    ],
                ),
            ):
                with self.assertRaises(HTTPException) as cm:
                    server.apply_hostname("tower")

        self.assertEqual(cm.exception.status_code, 504)
        self.assertIn("224.0.0.251", cm.exception.detail)

    def test_put_config_updates_controller_rename_and_nested_devices_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "abc"},
                            "settings": {"report_every": 10},
                            "devices": {
                                "lights": {
                                    "type": "scheduled_output",
                                    "config": {"pin": 3, "output_type": "gpio"},
                                    "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}},
                                }
                            },
                        }
                    },
                    "cameras": {},
                    "time_format": "24h",
                },
            )
            payload = {
                "controllers": {
                    "grow_box": {
                        "type": "pico_scheduler",
                        "config": {"pico_serial": "abc"},
                        "settings": {"report_every": 10},
                        "devices": {
                            "lights": {
                                "type": "scheduled_output",
                                "config": {"pin": 3, "output_type": "gpio"},
                                "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}},
                            }
                        },
                    }
                },
                "cameras": {},
            }
            with patch.object(server, "CONFIG_FILE", config_file):
                data = server.put_config(payload)

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertIn("lights", data["config"]["controllers"]["grow_box"]["settings"]["devices"])
        self.assertIn("lights", saved["controllers"]["grow_box"]["settings"]["devices"])
        self.assertEqual(saved["time_format"], "24h")

    def test_put_config_devices_endpoint_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": {
                            "type": "pico_scheduler",
                            "config": {"pico_serial": "e66038b71387a039"},
                            "settings": {"report_every": 10},
                            "devices": {},
                        }
                    },
                    "cameras": {},
                },
            )
            routes = {route.path for route in server.app.routes}

        self.assertNotIn("/api/config/devices", routes)

    def test_reduce_report_normalizes_old_pin_key(self):
        old_pin_key = "c" + "h"
        report = {
            "kind": "report",
            "content": {
                "events": [
                    {
                        "id": "pump",
                        "type": "gpio",
                        old_pin_key: 2,
                        "current_t": 0,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ]
            },
        }

        reduced = server.reduce_report(report)

        device = reduced["content"]["devices"][0]
        self.assertEqual(device["pin"], 2)
        self.assertNotIn(old_pin_key, device)
        self.assertEqual(reduced["pins"]["pump"]["pin"], 2)
        self.assertNotIn(old_pin_key, reduced["pins"]["pump"])

    def test_reduce_report_normalizes_devices_payload(self):
        old_pin_key = "c" + "h"
        report = {
            "kind": "report",
            "content": {
                "devices": [
                    {
                        "id": "pump",
                        "type": "gpio",
                        old_pin_key: 2,
                        "current_t": 0,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ]
            },
        }

        reduced = server.reduce_report(report)

        device = reduced["content"]["devices"][0]
        self.assertEqual(device["pin"], 2)
        self.assertNotIn(old_pin_key, device)
        self.assertEqual(reduced["pins"]["pump"]["pin"], 2)
        self.assertNotIn("events", reduced["content"])

    def test_reduce_report_normalizes_kind_to_type(self):
        report = {
            "kind": "report",
            "content": {
                "devices": [
                    {
                        "type": "gpio",
                        "pin": 2,
                        "elapsed_t": 5,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ]
            },
        }

        reduced = server.reduce_report(report)

        self.assertEqual(reduced["type"], "report")
        self.assertNotIn("kind", reduced)

    def test_monitor_handles_type_report_payload(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        monitor.handle_line(
            b'{"type":"report","content":{"devices":[{"type":"gpio","pin":15,"elapsed_t":1,"cycle_t":1,"reschedule":1,"pattern":[{"val":1,"dur":5}],"current_value":1}]}}'
        )

        snapshot = monitor.snapshot()

        self.assertEqual(snapshot["last_report"]["type"], "report")
        self.assertEqual(snapshot["last_report"]["content"]["devices"][0]["pin"], 15)

    def test_validate_timer_state_accepts_devices_field(self):
        state = {
            "report_every": 10,
            "devices": [
                {
                    "id": "test_pin",
                    "type": "gpio",
                    "pin": 25,
                    "current_t": 3,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                }
            ],
        }

        validated = server.validate_timer_state(state)

        self.assertEqual(validated["report_every"], 10)
        self.assertIn("devices", validated)
        self.assertEqual(validated["devices"][0]["id"], "test_pin")
        self.assertNotIn("events", validated)

    def test_timer_state_for_pico_uses_devices(self):
        state = {
            "report_every": 10,
            "devices": [
                {
                    "id": "test_pin",
                    "type": "gpio",
                    "pin": 25,
                    "current_t": 3,
                    "reschedule": 1,
                    "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                }
            ],
        }

        with patch.object(server, "timer_role", return_value={"payload": {"report_every": 7}}):
            timer_state = server.timer_state_for_pico("timer", state)

        self.assertEqual(timer_state, {"report_every": 7, "devices": state["devices"]})

    def test_latest_timer_state_reads_devices_from_last_report(self):
        monitor = DummyMonitor("abc")
        monitor.snapshot = lambda: {
            "last_report": {
                "kind": "report",
                "content": {
                    "devices": [
                        {
                            "pin": 2,
                            "type": "gpio",
                            "elapsed_t": 5,
                            "cycle_t": 5,
                            "reschedule": 1,
                            "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                            "current_value": 1,
                        }
                    ]
                },
            }
        }

        with patch.object(server, "get_or_start_monitor", return_value=monitor):
            latest = server.latest_timer_state("pump_lights")

        self.assertEqual(latest["devices"][0]["pin"], 2)
        self.assertEqual(latest["devices"][0]["current_t"], 5)

    def test_latest_timer_state_normalizes_events_from_last_report(self):
        monitor = DummyMonitor("abc")
        monitor.snapshot = lambda: {
            "last_report": {
                "kind": "report",
                "content": {
                    "devices": [
                        {
                            "type": "gpio",
                            "reschedule": 1,
                            "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                            "current_t": 5,
                            "c" + "h": 2,
                        }
                    ]
                },
            }
        }

        with patch.object(server, "get_or_start_monitor", return_value=monitor):
            latest = server.latest_timer_state("pump_lights")

        self.assertEqual(latest["devices"][0]["pin"], 2)
        self.assertNotIn("c" + "h", latest["devices"][0])
        self.assertEqual(latest["devices"][0]["elapsed_t"], 5)
        self.assertEqual(latest["devices"][0]["cycle_t"], 5)
        self.assertEqual(latest["devices"][0]["current_value"], 1)

    def test_get_controller_uses_scheduler_report_interval_from_config(self):
        with (
            patch.object(server, "controller_firmware", return_value="pico_scheduler"),
            patch.object(server, "state_for_role", return_value={"report_every": 1, "devices": []}),
            patch.object(server, "timer_role", return_value={"settings": {"report_every": 10}}),
        ):
            payload = server.controller_state_payload("pump_n_lights")

        self.assertEqual(payload["report_every"], 10)

    def test_post_timer_channel_schedule_does_not_reconstruct_from_live_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            (timers_dir / "pump_lights.json").write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "devices": [
                            {
                                "id": "pump",
                                "type": "gpio",
                                "pin": 2,
                                "current_t": 0,
                                "reschedule": 1,
                                "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            live_state = {
                "report_every": 1,
                "devices": [
                    {
                        "id": "pump",
                        "type": "gpio",
                        "pin": 2,
                        "current_t": 5,
                        "reschedule": 1,
                        "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}],
                    }
                ],
            }
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "latest_timer_state", return_value=live_state),
                patch.object(server, "live_events_for_role", side_effect=AssertionError("old helper should not be used")),
                patch.object(server, "live_devices_for_role", side_effect=AssertionError("semantic schedule must not use live devices"), create=True),
                patch.object(server, "apply_timer_state", return_value={"ok": True}),
            ):
                server.post_timer_channel_schedule("pump_lights", "pump", {"mode": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0})

    def test_post_controller_report_command_sends_r(self):
        monitor = DummyMonitor("abc")
        with (
            patch.object(server, "controller_firmware", return_value="pico_scheduler"),
            patch.object(server, "get_or_start_monitor", return_value=monitor),
        ):
            result = server.post_controller_report_command("pump_lights")

        self.assertEqual(monitor.sent_commands, ["r"])
        self.assertEqual(result["command"], "r")

    def test_post_controller_channel_pulse_sends_gpio_pin_and_duration(self):
        monitor = DummyMonitor("abc")
        config = {
            "controllers": {
                "pump_lights": self.scheduler_controller(
                    serial="abc",
                    devices={
                        "pump": self.scheduled_output(21),
                        "fan": self.scheduled_output(22, output_type="pwm"),
                        "hidden": self.scheduled_output(23, visibility="hidden"),
                    },
                )
            },
            "cameras": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.make_config(Path(tmp), config)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
            ):
                result = server.post_controller_channel_pulse("pump_lights", "pump", {"seconds": 7})

        self.assertEqual(monitor.sent_commands, ["p 21 7"])
        self.assertEqual(result["pin"], 21)
        self.assertEqual(result["seconds"], 7)

    def test_post_controller_channel_pulse_rejects_reported_on_channel(self):
        monitor = DummyMonitor(
            "abc",
            {"type": "report", "content": {"devices": [{"id": "pump", "pin": 21, "type": "gpio", "current_value": 1}]}},
        )
        config = {
            "controllers": {
                "pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(21)})
            },
            "cameras": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.make_config(Path(tmp), config)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.post_controller_channel_pulse("pump_lights", "pump", {"seconds": 7})

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("pin 21 is already on", str(raised.exception.detail))
        self.assertEqual(monitor.sent_commands, [])

    def test_post_controller_pin_pulse_sends_configured_gpio_pin_and_duration(self):
        monitor = DummyMonitor("abc")
        config = {
            "controllers": {
                "pump_lights": self.scheduler_controller(
                    serial="abc",
                    devices={
                        "pump": self.scheduled_output(21),
                        "hidden": self.scheduled_output(23, visibility="hidden"),
                    },
                )
            },
            "cameras": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.make_config(Path(tmp), config)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
            ):
                result = server.post_controller_pin_pulse("pump_lights", 23, {"seconds": 7})

        self.assertEqual(monitor.sent_commands, ["p 23 7"])
        self.assertEqual(result["pin"], 23)
        self.assertEqual(result["seconds"], 7)
        self.assertEqual(result["channel"], "hidden")

    def test_post_controller_channel_pulse_rejects_non_gpio_channel(self):
        monitor = DummyMonitor("abc")
        config = {
            "controllers": {
                "pump_lights": self.scheduler_controller(
                    serial="abc",
                    devices={
                        "fan": self.scheduled_output(22, output_type="pwm"),
                        "hidden": self.scheduled_output(23, visibility="hidden"),
                    },
                )
            },
            "cameras": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.make_config(Path(tmp), config)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
            ):
                with self.assertRaises(HTTPException):
                    server.post_controller_channel_pulse("pump_lights", "fan", {"seconds": 5})
                server.post_controller_channel_pulse("pump_lights", "hidden", {"seconds": 5})

        self.assertEqual(monitor.sent_commands, ["p 23 5"])

    def test_get_controller_serial_log_returns_monitor_ring_buffer(self):
        monitor = DummyMonitor("abc")
        monitor.serial_log_entries = [{"direction": "tx", "text": "r"}]
        with (
            patch.object(server, "controller_firmware", return_value="pico_scheduler"),
            patch.object(server, "get_or_start_monitor", return_value=monitor),
        ):
            result = server.get_controller_serial_log("pump_lights")

        self.assertEqual(result, {"controller": "pump_lights", "entries": [{"direction": "tx", "text": "r"}]})

    def test_get_timer_config_reflects_config_device_changes_immediately(self):
        state = {
            "report_every": 1,
            "devices": [
                {"id": "runtime-lamp", "type": "gpio", "pin": 2, "current_t": 1, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 50}]},
                {"id": "runtime-fan", "type": "pwm", "pin": 3, "current_t": 2, "reschedule": 1, "pattern": [{"val": 1000, "dur": 10}, {"val": 0, "dur": 50}]},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"sprouter": self.scheduler_controller(serial="abc", devices={"lamp": self.scheduled_output(2, kind="daily_window")})},
                    "cameras": {},
                },
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "state_for_role", return_value=state),
            ):
                initial = server.get_timer_config()
                server.put_config(
                    {
                        "controllers": {
                            "sprouter": self.scheduler_controller(
                                serial="abc",
                                devices={"fan": self.scheduled_output(3, output_type="pwm")},
                            )
                        },
                        "cameras": {},
                    }
                )
                updated = server.get_timer_config()

        self.assertEqual(
            initial,
            {
                "roles": ["sprouter"],
                "channels": {
                    "sprouter": [
                        {"role": "sprouter", "id": "lamp", "name": "lamp", "pin": 2, "type": "gpio", "default_editor": "clock_window", "visibility": "visible", "programming": "enabled", "display_order": 0, "editor": {"kind": "daily_window", "on_time": "06:00", "off_time": "18:00"}}
                    ]
                },
                "time_format": "12h",
            },
        )
        self.assertEqual(
            updated,
            {
                "roles": ["sprouter"],
                "channels": {
                    "sprouter": [
                        {"role": "sprouter", "id": "fan", "name": "fan", "pin": 3, "type": "pwm", "default_editor": "cycle", "visibility": "visible", "programming": "enabled", "display_order": 0, "editor": {"kind": "cycle", "on_seconds": 1, "off_seconds": 1, "start_at_seconds": 0}}
                    ]
                },
                "time_format": "12h",
            },
        )

    def test_timer_state_for_pico_excludes_disabled_and_hidden_devices(self):
        raw_state = {
            "report_every": 1,
            "devices": [
                {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}]},
                {"id": "lights", "type": "gpio", "pin": 3, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}]},
                {"id": "fan", "type": "gpio", "pin": 4, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}]},
            ],
        }
        config = {
            "controllers": {
                "sprouter": self.scheduler_controller(
                    devices={
                        "pump": self.scheduled_output(2, programming="disabled"),
                        "lights": self.scheduled_output(3, visibility="hidden"),
                        "fan": self.scheduled_output(4),
                    }
                )
            },
            "cameras": {},
        }

        with patch.object(server, "load_config", return_value=config):
            state = server.timer_state_for_pico("sprouter", raw_state)

        self.assertEqual([device["id"] for device in state["devices"]], ["fan"])

    def test_compiled_timer_state_for_controller_uses_semantic_config(self):
        config = server.config_view(
            {
                "controllers": {
                    "sprouter": self.scheduler_controller(
                        report_every=10,
                        devices={
                            "pump": {
                                "type": "scheduled_output",
                                "config": {"pin": 3},
                                "settings": {"schedule": {"kind": "cycle", "on_seconds": 300, "off_seconds": 2400, "start_at_seconds": 0, "unit": "minutes"}},
                            },
                            "lights": {
                                "type": "scheduled_output",
                                "config": {"pin": 2},
                                "settings": {"schedule": {"kind": "daily_window", "on_time": "06:00", "off_time": "23:00"}},
                            },
                        },
                    )
                },
                "cameras": {},
            }
        )

        with patch.object(server, "load_config", return_value=config):
            state = server.compiled_timer_state_for_controller("sprouter", now=time(9, 30))

        self.assertEqual(state["report_every"], 10)
        self.assertEqual(state["devices"][0]["pattern"], [{"val": 1, "dur": 300}, {"val": 0, "dur": 2400}])
        self.assertEqual(state["devices"][1]["pattern"], [{"val": 1, "dur": 61200}, {"val": 0, "dur": 25200}])
        self.assertEqual(state["devices"][1]["current_t"], 12600)

    def test_post_controller_apply_compiles_and_writes_complete_state_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"sprouter": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2, programming="disabled")})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            timer_path = timers_dir / "sprouter.json"
            timer_path.write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "devices": [
                            {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            compiled = {
                "report_every": 10,
                "devices": [
                    {"id": "lights", "type": "gpio", "pin": 2, "current_t": 12600, "reschedule": 1, "pattern": [{"val": 1, "dur": 61200}, {"val": 0, "dur": 25200}]}
                ],
            }
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "compiled_timer_state_for_controller", return_value=compiled),
                patch.object(server, "apply_timer_state", return_value={"ok": True}) as apply_timer_state,
            ):
                response = server.post_controller_apply("sprouter")

            saved = json.loads(timer_path.read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "state sent to Pico")
        self.assertEqual(saved, compiled)
        apply_timer_state.assert_called_once_with("sprouter", timer_path)

    def test_post_controller_apply_propagates_pico_failure(self):
        compiled = {"report_every": 5, "devices": []}
        with tempfile.TemporaryDirectory() as tmp:
            timers_dir = Path(tmp)
            with (
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "controller_firmware", return_value="pico_scheduler"),
                patch.object(server, "timer_state_path", return_value=timers_dir / "sprouter.json"),
                patch.object(server, "compiled_timer_state_for_controller", return_value=compiled),
                patch.object(server, "apply_timer_state", side_effect=HTTPException(status_code=409, detail="configured Pico is not connected: abc")),
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.post_controller_apply("sprouter")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("not connected", str(raised.exception.detail))

    def test_post_timer_channel_schedule_updates_semantic_config_and_applies_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": self.scheduler_controller(
                            serial="abc",
                            devices={
                                "pump": self.scheduled_output(3),
                                "lights": self.scheduled_output(2, kind="daily_window"),
                            },
                        )
                    },
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "reconcile_configured_monitors"),
                patch.object(server, "reconcile_camera_worker"),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "apply_timer_state", return_value={"serial": "abc"}) as apply_controller,
            ):
                response = server.post_timer_channel_schedule(
                    "pump_lights",
                    "lights",
                    {"mode": "clock_window", "on_time": "06:00", "off_time": "23:00"},
                )

            saved = json.loads(config_file.read_text(encoding="utf-8"))

        editor = saved["controllers"]["pump_lights"]["settings"]["devices"]["lights"]["editor"]
        self.assertEqual(editor, {"kind": "daily_window", "on_time": "06:00", "off_time": "23:00"})
        self.assertEqual(response["role"], "pump_lights")
        self.assertEqual(response["channel"], "lights")
        apply_controller.assert_called_once()

    def test_post_timer_channel_schedule_validates_before_saving_config(self):
        config = {
            "controllers": {
                "pump_lights": self.scheduler_controller(
                    devices={"lights": self.scheduled_output(2, kind="daily_window")}
                )
            },
            "cameras": {},
        }
        with (
            patch.object(server, "load_config", return_value=config),
            patch.object(server, "post_controller_schedule") as save_schedule,
        ):
            with self.assertRaises(HTTPException) as raised:
                server.post_timer_channel_schedule(
                    "pump_lights",
                    "lights",
                    {"mode": "clock_window", "on_time": "06:00", "off_time": "06:00"},
                )

        self.assertEqual(raised.exception.status_code, 422)
        save_schedule.assert_not_called()

    def test_timer_runtime_excludes_non_scheduler_controllers(self):
        config = server.config_view({
            "controllers": {
                "timer": self.scheduler_controller(serial="TIMER"),
                "future": {"type": "pico_doser", "config": {"pico_serial": "FUTURE"}, "settings": {}, "devices": {}},
            },
            "cameras": {},
        })
        with patch.object(server, "load_config", return_value=config):
            roles = server.configured_timer_roles()
            serials = server.configured_monitor_serials()
            timer_config = server.get_timer_config()

        self.assertEqual(roles, ["timer"])
        self.assertEqual(serials, {"timer": "TIMER"})
        self.assertEqual(timer_config["roles"], ["timer"])
        self.assertNotIn("future", timer_config["channels"])

    def test_configured_time_format_reads_top_level_value_from_raw_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {},
                    "cameras": {},
                    "time_format": "24h",
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                self.assertEqual(server.configured_time_format(), "24h")

    def test_api_test_page_uses_empty_payload_when_default_timer_state_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(root, {"controllers": {}, "cameras": {}})
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "configured_timer_roles", return_value=["pump_n_lights"]),
            ):
                response = server.api_test_page_response()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pump_n_lights", response.body)
        self.assertIn(b"{}", response.body)

    def test_put_config_controllers_reconciles_running_monitors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "keep": self.scheduler_controller(serial="KEEP_NEW"),
                        "drop": self.scheduler_controller(serial="DROP_OLD"),
                    },
                    "cameras": {},
                },
            )
            old_keep = DummyMonitor("KEEP_OLD")
            old_drop = DummyMonitor("DROP_OLD")
            new_keep = DummyMonitor("KEEP_NEW")
            monitor_map = {"keep": old_keep, "drop": old_drop}
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "monitors", monitor_map),
                patch.object(server, "PicoMonitor", side_effect=[new_keep]),
            ):
                server.put_config_controllers({"keep": self.scheduler_controller(serial="KEEP_NEW")})

        self.assertTrue(old_keep.stopped)
        self.assertFalse(old_keep.started)
        self.assertTrue(old_drop.stopped)
        self.assertFalse(old_drop.started)
        self.assertTrue(new_keep.started)
        self.assertIs(monitor_map["keep"], new_keep)
        self.assertEqual(monitor_map["keep"].pico_serial, "KEEP_NEW")
        self.assertNotIn("drop", monitor_map)

    def test_reconcile_wakes_retained_monitor_for_new_poll_interval(self):
        monitor = DummyMonitor("KEEP")
        with (
            patch.object(server, "configured_monitor_serials", return_value={"keep": "KEEP"}),
            patch.object(server, "pico_serial_for_role", return_value="KEEP"),
            patch.object(server, "monitors", {"keep": monitor}),
        ):
            server.reconcile_configured_monitors()

        self.assertTrue(monitor.woken)

    def test_post_timer_channel_schedule_uses_saved_state_not_stale_live_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {
                        "pump_lights": self.scheduler_controller(
                            serial="abc",
                            devices={
                                "pump": self.scheduled_output(2),
                                "lights": self.scheduled_output(3, kind="daily_window"),
                            },
                        )
                    },
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            (timers_dir / "pump_lights.json").write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "devices": [
                            {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stale_live = {
                "report_every": 1,
                "devices": [
                    {"id": "test_pin", "type": "gpio", "pin": 25, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 12}, {"val": 0, "dur": 5}]}
                ],
            }
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "latest_timer_state", return_value=stale_live),
                patch.object(server, "apply_timer_state", return_value={"ok": True}),
            ):
                server.post_timer_channel_schedule("pump_lights", "lights", {"mode": "clock_window", "on_time": "06:00", "off_time": "18:00"})

            saved = json.loads((timers_dir / "pump_lights.json").read_text(encoding="utf-8"))

        self.assertEqual([device["id"] for device in saved["devices"]], ["pump", "lights"])
        self.assertEqual(saved["devices"][0]["pin"], 2)
        self.assertEqual(saved["devices"][1]["pin"], 3)

    def test_post_controller_schedule_rejects_offline_without_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            timer_file = timers_dir / "pump_lights.json"
            timer_file.write_text(json.dumps({"report_every": 1, "devices": []}), encoding="utf-8")
            original_config = config_file.read_bytes()
            original_state = timer_file.read_bytes()
            with patch.object(server, "CONFIG_FILE", config_file):
                proposed = copy.deepcopy(server.load_config()["controllers"]["pump_lights"])
            proposed["settings"]["devices"]["pump"]["editor"] = {
                "kind": "cycle",
                "on_seconds": 10,
                "off_seconds": 20,
                "start_at_seconds": 0,
            }
            monitor = SimpleNamespace(
                require_fresh_report=Mock(side_effect=HTTPException(status_code=409, detail="configured Pico is not connected: abc"))
            )
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
                patch.object(server, "apply_timer_state") as apply_timer_state,
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.post_controller_schedule("pump_lights", proposed)

            self.assertEqual(config_file.read_bytes(), original_config)
            self.assertEqual(timer_file.read_bytes(), original_state)

        self.assertEqual(raised.exception.status_code, 409)
        apply_timer_state.assert_not_called()

    def test_post_controller_schedule_commits_after_verified_flash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            timer_file = timers_dir / "pump_lights.json"
            timer_file.write_text(json.dumps({"report_every": 1, "devices": []}), encoding="utf-8")
            with patch.object(server, "CONFIG_FILE", config_file):
                proposed = copy.deepcopy(server.load_config()["controllers"]["pump_lights"])
            proposed["settings"]["devices"]["pump"]["editor"] = {
                "kind": "cycle",
                "on_seconds": 10,
                "off_seconds": 20,
                "start_at_seconds": 0,
            }
            monitor = SimpleNamespace(require_fresh_report=Mock(return_value={"type": "report", "content": {"devices": []}}))
            staged_states = []

            def verified_apply(role, path):
                self.assertEqual(role, "pump_lights")
                self.assertNotEqual(Path(path), timer_file)
                staged_states.append(json.loads(Path(path).read_text(encoding="utf-8")))
                return {"serial": "abc", "port": "/dev/ttyACM0"}

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=monitor),
                patch.object(server, "apply_timer_state", side_effect=verified_apply),
            ):
                response = server.post_controller_schedule("pump_lights", proposed)

            saved_config = json.loads(config_file.read_text(encoding="utf-8"))
            saved_state = json.loads(timer_file.read_text(encoding="utf-8"))

        monitor.require_fresh_report.assert_called_once_with(timeout=3.0)
        self.assertTrue(response["success"])
        self.assertEqual(saved_config["controllers"]["pump_lights"]["settings"]["devices"]["pump"]["editor"]["on_seconds"], 10)
        self.assertEqual(saved_state, staged_states[0])

    def test_post_controller_schedule_leaves_files_unchanged_when_flash_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            timer_file = timers_dir / "pump_lights.json"
            timer_file.write_text(json.dumps({"report_every": 1, "devices": []}), encoding="utf-8")
            original_config = config_file.read_bytes()
            original_state = timer_file.read_bytes()
            with patch.object(server, "CONFIG_FILE", config_file):
                proposed = copy.deepcopy(server.load_config()["controllers"]["pump_lights"])
            proposed["settings"]["devices"]["pump"]["editor"] = {
                "kind": "cycle",
                "on_seconds": 10,
                "off_seconds": 20,
                "start_at_seconds": 0,
            }

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "apply_timer_state", side_effect=HTTPException(status_code=502, detail="no valid report after flash")),
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.post_controller_schedule("pump_lights", proposed)

            self.assertEqual(config_file.read_bytes(), original_config)
            self.assertEqual(timer_file.read_bytes(), original_state)

        self.assertEqual(raised.exception.status_code, 502)

    def test_post_controller_schedule_rejects_pico_serial_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="old", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            with patch.object(server, "CONFIG_FILE", config_file):
                proposed = copy.deepcopy(server.load_config()["controllers"]["pump_lights"])
            proposed["payload"]["pico_serial"] = "new"

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", root / "data" / "timers"),
                patch.object(server, "get_or_start_monitor") as get_monitor,
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.post_controller_schedule("pump_lights", proposed)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("pico_serial", str(raised.exception.detail))
        get_monitor.assert_not_called()

    def test_post_timer_channel_schedule_creates_state_when_timer_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "latest_timer_state", return_value=None),
                patch.object(server, "apply_timer_state", return_value={"ok": True}),
            ):
                response = server.post_timer_channel_schedule("pump_lights", "pump", {"mode": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0})

            saved = json.loads((timers_dir / "pump_lights.json").read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertEqual(saved["report_every"], 10)
        self.assertEqual(saved["devices"][0]["id"], "pump")
        self.assertEqual(saved["devices"][0]["pin"], 2)

    def test_post_timer_channel_schedule_replaces_invalid_timer_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timers_dir = root / "data" / "timers"
            timers_dir.mkdir(parents=True)
            (timers_dir / "pump_lights.json").write_text("{not json", encoding="utf-8")
            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "DATA_DIR", root / "data"),
                patch.object(server, "TIMERS_DIR", timers_dir),
                patch.object(server, "get_or_start_monitor", return_value=self.healthy_monitor()),
                patch.object(server, "latest_timer_state", return_value=None),
                patch.object(server, "apply_timer_state", return_value={"ok": True}),
            ):
                response = server.post_timer_channel_schedule("pump_lights", "pump", {"mode": "cycle", "on_seconds": 10, "off_seconds": 20, "start_at_seconds": 0})

            saved = json.loads((timers_dir / "pump_lights.json").read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertEqual(saved["report_every"], 10)
        self.assertEqual(saved["devices"][0]["id"], "pump")
        self.assertEqual(saved["devices"][0]["pattern"], [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}])

    def test_pico_monitor_apply_holds_operation_through_reset_and_valid_report(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        exchange = SimpleNamespace(
            port="/dev/ttyACM1",
            raw_lines=(b'{"type":"report","content":{"devices":[]}}\n',),
            message={"type": "report", "content": {"devices": []}},
        )

        with (
            patch.object(monitor.client, "flash_main", return_value=exchange) as flash_main,
            patch.object(server.shutil, "which", return_value="/usr/bin/mpremote"),
        ):
            result = monitor.apply(Path("/tmp/main.py"))

        self.assertEqual(flash_main.call_args.args, (Path("/tmp/main.py"),))
        self.assertEqual(flash_main.call_args.kwargs["timeout"], 60.0)
        self.assertEqual(flash_main.call_args.kwargs["mpremote"], "/usr/bin/mpremote")
        self.assertEqual(result["port"], "/dev/ttyACM1")
        self.assertEqual(result["report_sequence"], 1)
        self.assertTrue(monitor.snapshot()["ok"])

    def test_pico_monitor_command_waits_for_and_publishes_response(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        exchange = SimpleNamespace(
            port="/dev/ttyACM0",
            raw_lines=(b'{"type":"report","content":{"devices":[]}}\n',),
            message={"type": "report", "content": {"devices": []}},
        )

        with patch.object(monitor.client, "command", return_value=exchange) as command:
            returned = monitor.send_serial_command("p 21 5")

        command.assert_called_once_with("p 21 5", timeout=5.0)
        self.assertEqual(returned["command"], "p 21 5")
        self.assertEqual(monitor.report_sequence, 1)
        self.assertEqual([entry["direction"] for entry in monitor.serial_log()], ["tx", "rx"])
        self.assertTrue(monitor.snapshot()["ok"])

    def test_pico_monitor_only_sequences_valid_reports(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        subscriber = monitor.subscribe()

        monitor.handle_line(b"not json\n")
        self.assertEqual(monitor.report_sequence, 0)

        monitor.handle_line(b'{"type":"report","content":{"devices":[]}}\n')
        events = []
        while not subscriber.empty():
            events.append(subscriber.get_nowait())
        report_event = next(event for event in events if event["event"] == "report")

        self.assertEqual(monitor.report_sequence, 1)
        self.assertEqual(report_event["data"]["report_sequence"], 1)

    def test_pico_monitor_publishes_binary_health(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        subscriber = monitor.subscribe()
        health = PicoHealth(
            ok=True,
            status="OK",
            checked_at="2026-07-16T12:00:00+00:00",
            serial="abc",
            port="/dev/ttyACM0",
            report={"type": "report", "content": {"devices": []}},
            raw_lines=('{"type":"report"}',),
            error=None,
        )

        with patch.object(server, "probe_pico", return_value=health):
            monitor.collect_report()

        snapshot = monitor.snapshot()
        events = []
        while not subscriber.empty():
            events.append(subscriber.get_nowait())
        status = next(event for event in events if event["event"] == "status")
        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "OK")
        self.assertEqual(snapshot["last_verified_at"], health.checked_at)
        self.assertEqual(status["data"]["port"], "/dev/ttyACM0")

    def test_pico_monitor_handles_usb_events(self):
        monitor = server.PicoMonitor("pump_lights", "abc")

        monitor.handle_usb_event(UsbSerialEvent("remove", "abc", "/dev/ttyACM0"))
        disconnected = monitor.snapshot()
        self.assertFalse(disconnected["ok"])
        self.assertEqual(disconnected["status"], "ERROR")
        self.assertEqual(disconnected["error"]["kind"], "unavailable")
        self.assertEqual(disconnected["error"]["step"], "discover")

        monitor.handle_usb_event(UsbSerialEvent("add", "abc", "/dev/ttyACM1"))
        self.assertTrue(monitor.wake_event.is_set())

    def test_pico_monitor_ignores_other_usb_serials(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        before = monitor.snapshot()

        monitor.handle_usb_event(UsbSerialEvent("remove", "other", "/dev/ttyACM0"))

        self.assertEqual(monitor.snapshot(), before)

    def test_pico_monitor_uses_fixed_health_interval(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        monitor.collect_report = Mock()
        monitor.update_status = Mock()
        monitor.stop_event = Mock()
        monitor.stop_event.is_set.side_effect = [False, True]
        monitor.wake_event = Mock()

        with patch.object(server.time, "monotonic", side_effect=[10.0, 10.0]):
            monitor.run()

        monitor.wake_event.wait.assert_called_once_with(5.0)

    def test_require_fresh_report_raises_structured_http_error(self):
        monitor = server.PicoMonitor("pump_lights", "abc")
        health = failed_health(
            "abc",
            kind="unavailable",
            step="discover",
            message="configured Pico is not connected: abc",
        )

        with patch.object(server, "probe_pico", return_value=health):
            with self.assertRaises(HTTPException) as raised:
                monitor.require_fresh_report(timeout=1.5)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["health"]["error"]["kind"], "unavailable")

    def test_apply_timer_state_keeps_report_period_out_of_firmware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", report_every=42, devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timer_path = root / "data" / "timers" / "pump_lights.json"
            timer_path.parent.mkdir(parents=True)
            timer_path.write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "devices": [
                            {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            applied_payloads = []

            class FakeMonitor:
                def apply(self, path):
                    applied_payloads.append(Path(path).read_text(encoding="utf-8"))
                    return {"ok": True}

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=FakeMonitor()),
            ):
                response = server.apply_timer_state("pump_lights", timer_path)

        self.assertEqual(response, {"ok": True})
        self.assertNotIn("REPORT_EVERY", applied_payloads[0])
        self.assertNotIn("report_every", applied_payloads[0])
        self.assertIn('"id": "pump"', applied_payloads[0])

    def test_apply_timer_state_writes_generated_main_py_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = self.make_config(
                root,
                {
                    "controllers": {"pump_lights": self.scheduler_controller(serial="abc", report_every=42, devices={"pump": self.scheduled_output(2)})},
                    "cameras": {},
                },
            )
            timer_path = root / "data" / "timers" / "pump_lights.json"
            timer_path.parent.mkdir(parents=True)
            timer_path.write_text(
                json.dumps(
                    {
                        "report_every": 1,
                        "devices": [
                            {"id": "pump", "type": "gpio", "pin": 2, "current_t": 0, "reschedule": 1, "pattern": [{"val": 1, "dur": 10}, {"val": 0, "dur": 20}]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            generated_files = []

            class FakeMonitor:
                def apply(self, path):
                    generated_files.append(Path(path))
                    return {"ok": True}

            with (
                patch.object(server, "CONFIG_FILE", config_file),
                patch.object(server, "get_or_start_monitor", return_value=FakeMonitor()),
            ):
                response = server.apply_timer_state("pump_lights", timer_path)

        self.assertEqual(response, {"ok": True})
        self.assertEqual(generated_files[0].suffix, ".py")
