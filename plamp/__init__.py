from importlib import import_module

__all__ = ["CameraError", "EXPECTED_FIRMWARE_PROTOCOL", "FirmwareIdentity", "LockTimeout", "PicoClient", "PicoCommandError", "PicoExchange", "PicoFlashError", "PicoHealth", "PicoHealthError", "PicoOperation", "PicoReportTimeout", "PicoUnavailable", "SchedulerApplyResult", "apply_scheduler_state", "capture_camera", "failed_health", "firmware_identity", "firmware_revision", "normalize_scheduler_state", "probe_pico", "pulse_gpio", "render_scheduler_firmware", "report_matches_state", "request_report"]

_EXPORT_MODULES = {
    "CameraError": "plamp.camera",
    "capture_camera": "plamp.camera",
    "LockTimeout": "plamp.locks",
    "firmware_revision": "plamp.pico_firmware",
    "render_scheduler_firmware": "plamp.pico_firmware",
    "PicoHealth": "plamp.pico_health",
    "PicoHealthError": "plamp.pico_health",
    "failed_health": "plamp.pico_health",
    "probe_pico": "plamp.pico_health",
    "SchedulerApplyResult": "plamp.pico_scheduler",
    "apply_scheduler_state": "plamp.pico_scheduler",
    "PicoClient": "plamp.pico_transport",
    "PicoCommandError": "plamp.pico_transport",
    "PicoExchange": "plamp.pico_transport",
    "PicoFlashError": "plamp.pico_transport",
    "PicoOperation": "plamp.pico_transport",
    "PicoReportTimeout": "plamp.pico_transport",
    "PicoUnavailable": "plamp.pico_transport",
    "pulse_gpio": "plamp.pico_transport",
    "request_report": "plamp.pico_transport",
    "EXPECTED_FIRMWARE_PROTOCOL": "plamp.scheduler_state",
    "FirmwareIdentity": "plamp.scheduler_state",
    "firmware_identity": "plamp.scheduler_state",
    "normalize_scheduler_state": "plamp.scheduler_state",
    "report_matches_state": "plamp.scheduler_state",
}


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
