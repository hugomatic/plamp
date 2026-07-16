from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from pathlib import Path

from plamp.hardware_config import config_view


class ConfigError(ValueError):
    pass


def load_config(config_file: Path) -> dict[str, Any]:
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {config_file}: {exc}") from exc
    try:
        return config_view(config)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def save_config(config_file: Path, config: Any) -> dict[str, Any]:
    try:
        validated = config_view(config)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    config_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=config_file.parent,
        prefix=f".{config_file.name}.",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(validated, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, config_file)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return validated


def controller_pico_serial(config_file: Path, controller: str) -> str:
    config = load_config(config_file)
    controllers = config.get("controllers") if isinstance(config, dict) else None
    item = controllers.get(controller) if isinstance(controllers, dict) else None
    payload = item.get("payload") if isinstance(item, dict) else None
    serial = payload.get("pico_serial") if isinstance(payload, dict) else None
    if not isinstance(serial, str) or not serial:
        raise ConfigError(f"controller has no configured Pico serial: {controller}")
    return serial
