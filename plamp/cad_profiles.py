"""Typed CAD manufacturing profiles and instance-local defaults."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from difflib import get_close_matches
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

from plamp.cad_model import CadDiagnostic, CadMetadataError


_PROFILE_SCHEMA = "plamp-cad-profile/1"
_PREFERENCES_SCHEMA = "plamp-cad-preferences/1"
_PROFILE_KEYS = frozenset({"schema", "name", "kind", "cad", "slicing", "machine"})
_PREFERENCE_KEYS = frozenset({"schema", "default_system", "default_profiles"})
_PROFILE_KINDS = frozenset({"printer", "nozzle", "material", "quality"})
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class CadProfileError(CadMetadataError):
    """One or more diagnostics from profile or preference metadata."""


@dataclass(frozen=True)
class CadProfile:
    name: str
    qualified_id: str
    kind: str
    path: Path
    cad: Mapping[str, object]
    slicing: Mapping[str, object]
    machine: Mapping[str, object]
    content_hash: str


@dataclass(frozen=True)
class CadPreferences:
    default_system: str | None = None
    default_profiles: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )


def _diagnostic(path: Path | str, message: str, *, json_path: str | None = None,
                code: str = "CAD130", kind: str = "invalid_profile_metadata",
                value: object | None = None, choices: tuple[str, ...] = (),
                suggestion: str | None = None) -> CadDiagnostic:
    return CadDiagnostic(code, kind, message, str(path), json_path=json_path,
                         value=value, choices=choices, suggestion=suggestion)


def _fail(path: Path | str, message: str, **fields: object) -> None:
    raise CadProfileError((_diagnostic(path, message, **fields),))


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        detail = (f"non-finite number {error}" if isinstance(error, ValueError)
                  and not isinstance(error, json.JSONDecodeError) else str(error))
        _fail(path, f"Invalid {label} JSON: {detail}", code="CAD100",
              kind=f"invalid_{label}_json")
    if not isinstance(value, dict):
        _fail(path, f"{label.title()} must be a JSON object", json_path="$", value=value)
    return value


def _unknown_keys(value: Mapping[str, object], allowed: frozenset[str], path: Path) -> None:
    for key in value:
        if key not in allowed:
            _fail(path, f"Unknown metadata key {key!r}", json_path=f"$.{key}", value=key)


def _json_value(value: object, path: Path, json_path: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(path, f"{json_path} must contain only finite numbers",
                  json_path=json_path, value=value)
        return value
    if isinstance(value, list):
        return tuple(_json_value(item, path, f"{json_path}[{index}]")
                     for index, item in enumerate(value))
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            _fail(path, f"{json_path} object keys must be strings", json_path=json_path)
        return MappingProxyType({
            key: _json_value(item, path, f"{json_path}.{key}")
            for key, item in value.items()
        })
    _fail(path, f"{json_path} contains an unsupported value", json_path=json_path,
          value=value)


def _namespace(value: Mapping[str, object], key: str, path: Path) -> Mapping[str, object]:
    raw = value.get(key, {})
    if not isinstance(raw, dict):
        _fail(path, f"$.{key} must be a JSON object", json_path=f"$.{key}", value=raw)
    return _json_value(raw, path, f"$.{key}")  # type: ignore[return-value]


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _valid_profile_id(profile_id: str) -> bool:
    if _SAFE_NAME.fullmatch(profile_id):
        return True
    namespace, separator, name = profile_id.partition(":")
    return (
        separator == ":"
        and namespace in {"system", "local"}
        and _SAFE_NAME.fullmatch(name) is not None
    )


def profile_content_hash(content: Mapping[str, object]) -> str:
    """Return the SHA-256 of canonical profile JSON content."""
    canonical = json.dumps(
        _plain(content), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_profile(path: Path, declared_name: str, namespace: str) -> CadProfile:
    value = _read_json(path, "profile")
    _unknown_keys(value, _PROFILE_KEYS, path)
    if value.get("schema") != _PROFILE_SCHEMA:
        _fail(path, f"$.schema must equal {_PROFILE_SCHEMA!r}", json_path="$.schema",
              value=value.get("schema"))
    name = value.get("name")
    if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
        _fail(path, "$.name must be a safe name", json_path="$.name", value=name)
    if name != declared_name:
        _fail(path, f"Profile name {name!r} must match declared name {declared_name!r}",
              json_path="$.name", value=name)
    kind = value.get("kind")
    if kind not in _PROFILE_KINDS:
        _fail(path, f"$.kind must be one of {', '.join(sorted(_PROFILE_KINDS))}",
              json_path="$.kind", value=kind, choices=tuple(sorted(_PROFILE_KINDS)))
    cad = _namespace(value, "cad", path)
    slicing = _namespace(value, "slicing", path)
    machine = _namespace(value, "machine", path)
    return CadProfile(name, f"{namespace}:{name}", kind, path, cad, slicing,
                      machine, profile_content_hash(value))


def load_system_profiles(references: Mapping[str, Path]) -> Mapping[str, CadProfile]:
    """Load repository-versioned profiles from resolved manifest references."""
    loaded = {
        name: _load_profile(Path(path), name, "system")
        for name, path in references.items()
    }
    return MappingProxyType(loaded)


def discover_local_profiles(data_dir: Path) -> Mapping[str, CadProfile]:
    """Load every instance-local profile in deterministic filename order."""
    data_root = Path(data_dir).resolve()
    directory = Path(data_dir) / "cad" / "profiles"
    if directory.is_symlink():
        _fail(directory, "Local profile directory cannot be a symbolic link",
              code="CAD109", kind="unsafe_profile_path")
    if not directory.exists():
        return MappingProxyType({})
    if not directory.is_dir():
        _fail(directory, "Local profile path must be a directory",
              kind="invalid_profile_directory")
    if not _inside(directory.resolve(), data_root):
        _fail(directory, "Local profile directory must remain inside the data directory",
              code="CAD109", kind="unsafe_profile_path")
    loaded: dict[str, CadProfile] = {}
    diagnostics: list[CadDiagnostic] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        name = path.stem
        try:
            if not _inside(path.resolve(), data_root):
                _fail(path, "Local profile must remain inside the data directory",
                      code="CAD109", kind="unsafe_profile_path")
            if not _SAFE_NAME.fullmatch(name):
                _fail(path, f"Local profile filename {name!r} is not a safe name",
                      json_path="$.name", value=name)
            loaded[name] = _load_profile(path, name, "local")
        except CadProfileError as error:
            diagnostics.extend(error.diagnostics)
    if diagnostics:
        raise CadProfileError(diagnostics)
    return MappingProxyType(loaded)


def load_preferences(data_dir: Path) -> CadPreferences:
    """Load instance preferences, returning empty defaults when absent."""
    path = Path(data_dir) / "cad" / "preferences.json"
    if not path.exists():
        return CadPreferences()
    value = _read_json(path, "preferences")
    _unknown_keys(value, _PREFERENCE_KEYS, path)
    if value.get("schema") != _PREFERENCES_SCHEMA:
        _fail(path, f"$.schema must equal {_PREFERENCES_SCHEMA!r}",
              json_path="$.schema", value=value.get("schema"))
    default_system = value.get("default_system")
    if default_system is not None and (
        not isinstance(default_system, str) or not _SAFE_NAME.fullmatch(default_system)
    ):
        _fail(path, "$.default_system must be a safe string or null",
              json_path="$.default_system", value=default_system)
    raw_defaults = value.get("default_profiles", {})
    if not isinstance(raw_defaults, dict):
        _fail(path, "$.default_profiles must be a JSON object",
              json_path="$.default_profiles", value=raw_defaults)
    defaults: dict[str, tuple[str, ...]] = {}
    for system, raw_ids in raw_defaults.items():
        item_path = f"$.default_profiles.{system}"
        if not _SAFE_NAME.fullmatch(system):
            _fail(path, f"{item_path} uses an unsafe system name", json_path=item_path)
        if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
            _fail(path, f"{item_path} must be an array of strings",
                  json_path=item_path, value=raw_ids)
        for index, profile_id in enumerate(raw_ids):
            if not _valid_profile_id(profile_id):
                profile_path = f"{item_path}[{index}]"
                _fail(
                    path,
                    f"{profile_path} must be a safe short profile ID or exactly "
                    "system:NAME/local:NAME",
                    json_path=profile_path,
                    kind="invalid_profile_id",
                    value=profile_id,
                )
        defaults[system] = tuple(raw_ids)
    return CadPreferences(default_system, MappingProxyType(defaults))


def resolve_profile_ids(system_profiles: Mapping[str, CadProfile],
                        local_profiles: Mapping[str, CadProfile], *,
                        defaults: Sequence[str], requested: Sequence[str],
                        use_defaults: bool) -> tuple[CadProfile, ...]:
    """Resolve ordered profile IDs without allowing namespace shadowing."""
    choices = tuple(
        [f"system:{name}" for name in system_profiles]
        + [f"local:{name}" for name in local_profiles]
    )
    resolved = []
    selected_ids = (tuple(defaults) if use_defaults else ()) + tuple(requested)
    for profile_id in selected_ids:
        profile: CadProfile | None = None
        if profile_id.startswith("system:"):
            profile = system_profiles.get(profile_id.removeprefix("system:"))
        elif profile_id.startswith("local:"):
            profile = local_profiles.get(profile_id.removeprefix("local:"))
        elif ":" in profile_id:
            profile = None
        else:
            system_profile = system_profiles.get(profile_id)
            local_profile = local_profiles.get(profile_id)
            if system_profile is not None and local_profile is not None:
                _fail("<profiles>",
                      f"Ambiguous profile {profile_id!r}; use system:{profile_id} or local:{profile_id}",
                      code="CAD131", kind="ambiguous_profile", value=profile_id,
                      choices=(f"system:{profile_id}", f"local:{profile_id}"))
            profile = system_profile or local_profile
        if profile is None:
            suggestion = (get_close_matches(profile_id, choices, n=1, cutoff=0.6)
                          or [None])[0]
            _fail("<profiles>", f"Unknown profile {profile_id!r}", code="CAD127",
                  kind="unknown_profile", value=profile_id, choices=choices,
                  suggestion=suggestion)
        resolved.append(profile)
    return tuple(resolved)
