from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


TEMPLATES_DIR = Path(__file__).with_name("templates")


@dataclass(frozen=True)
class GeneratorOptions:
    loop_sleep_ms: int = 20
    pwm_freq: int = 1000


def _template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def generate_main_py(
    *, firmware_revision: str, options: GeneratorOptions
) -> str:
    return _template("base.py.tmpl").format(
        firmware_revision=json.dumps(firmware_revision),
        firmware_protocol=2,
        loop_sleep_ms=options.loop_sleep_ms,
        pwm_freq=options.pwm_freq,
    ).rstrip() + "\n"
