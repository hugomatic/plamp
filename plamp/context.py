from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuntimeContext:
    root: Path
    data_dir: Path
    lock_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "state" / "plamp" / "locks")

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"


def resolve_context(
    *,
    env: Mapping[str, str] | None = None,
    package_root: Path | None = None,
) -> RuntimeContext:
    values = os.environ if env is None else env
    default_root = Path(__file__).resolve().parents[1] if package_root is None else Path(package_root)
    root = Path(values.get("PLAMP_ROOT", default_root)).expanduser().resolve()
    data_dir = Path(values.get("PLAMP_DATA_DIR", root / "data")).expanduser().resolve()
    home = Path(values.get("HOME", Path.home())).expanduser().resolve()
    return RuntimeContext(root=root, data_dir=data_dir, lock_dir=home / ".local" / "state" / "plamp" / "locks")
