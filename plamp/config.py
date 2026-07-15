from __future__ import annotations

import json
from pathlib import Path


class ConfigError(ValueError):
    pass


def controller_pico_serial(config_file: Path, controller: str) -> str:
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {config_file}: {exc}") from exc
    controllers = config.get("controllers") if isinstance(config, dict) else None
    item = controllers.get(controller) if isinstance(controllers, dict) else None
    payload = item.get("payload") if isinstance(item, dict) else None
    serial = payload.get("pico_serial") if isinstance(payload, dict) else None
    if not isinstance(serial, str) or not serial:
        raise ConfigError(f"controller has no configured Pico serial: {controller}")
    return serial
