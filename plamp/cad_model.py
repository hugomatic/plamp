"""Parse authoritative OpenSCAD set declarations and adjacent model sidecars."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from difflib import get_close_matches
import json
from pathlib import Path
import re
from types import MappingProxyType


SET_ASSIGNMENT = re.compile(
    r'^\s*set\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;'
    r'[^\n]*//\s*\[(?P<choices>[^]]*)\]',
    re.MULTILINE,
)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SIDECAR_KEYS = frozenset(
    {"schema", "name", "source", "description", "sets", "variables"}
)
_SET_KEYS = frozenset(
    {"description", "variables", "printable", "slicing"}
)


@dataclass(frozen=True)
class CadDiagnostic:
    code: str
    kind: str
    message: str
    source: str
    json_path: str | None = None
    line: int | None = None
    column: int | None = None
    value: object | None = None
    choices: tuple[str, ...] = ()
    suggestion: str | None = None
    fix: str | None = None


class CadMetadataError(ValueError):
    """One or more ordered diagnostics produced while parsing CAD metadata."""

    def __init__(self, diagnostics: Iterable[CadDiagnostic]):
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("CadMetadataError requires at least one diagnostic")
        super().__init__(self._format_diagnostics())

    def _format_diagnostics(self) -> str:
        lines = []
        for diagnostic in self.diagnostics:
            location = diagnostic.source
            if diagnostic.line is not None:
                location += f":{diagnostic.line}"
                if diagnostic.column is not None:
                    location += f":{diagnostic.column}"
            if diagnostic.json_path is not None:
                location += f": {diagnostic.json_path}"
            line = f"{location}: {diagnostic.code}: {diagnostic.message}"
            if diagnostic.suggestion:
                line += f" (did you mean {diagnostic.suggestion!r}?)"
            if diagnostic.fix:
                line += f"; {diagnostic.fix}"
            lines.append(line)
        return "\n".join(lines)


@dataclass(frozen=True)
class CadSet:
    name: str
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)
    printable: bool = True
    slicing: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CadModel:
    model_id: str
    name: str
    description: str
    source_path: Path
    sidecar_path: Path | None
    default_set: str
    sets: Mapping[str, CadSet]
    variables: Mapping[str, object]
    metadata_snapshot: Mapping[str, object]
    advisories: tuple[CadDiagnostic, ...] = ()


def diagnostics_json(diagnostics: Iterable[CadDiagnostic]) -> str:
    """Return stable JSON for diagnostics at machine-readable boundaries."""

    return json.dumps([asdict(diagnostic) for diagnostic in diagnostics], sort_keys=True)


def _diagnostic(
    path: Path,
    code: str,
    kind: str,
    message: str,
    **fields: object,
) -> CadDiagnostic:
    return CadDiagnostic(
        code=code, kind=kind, message=message, source=str(path), **fields
    )


def _fail(
    path: Path,
    message: str,
    *,
    code: str = "CAD110",
    kind: str = "invalid_model_metadata",
    **fields: object,
) -> None:
    raise CadMetadataError((_diagnostic(path, code, kind, message, **fields),))


def _suggest(value: str, choices: tuple[str, ...]) -> str | None:
    matches = get_close_matches(value, choices, n=1, cutoff=0.6)
    return matches[0] if matches else None


def parse_set_declaration(source: str, path: Path) -> tuple[str, tuple[str, ...]]:
    """Return the assigned set and Customizer choices from the first declaration."""

    match = SET_ASSIGNMENT.search(source)
    if match is None:
        return "", ()
    try:
        default = json.loads(f'"{match.group("value")}"')
    except json.JSONDecodeError as error:
        _fail(
            path,
            f"Invalid set assignment string: {error.msg}",
            code="CAD100",
            kind="invalid_json",
            line=source.count("\n", 0, match.start()) + 1,
        )
    choices = tuple(
        item.strip() for item in match.group("choices").split(",") if item.strip()
    )
    return default, choices


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_reference(reference: Path, repo_root: Path) -> Path:
    candidate = reference if reference.is_absolute() else repo_root / reference
    resolved = candidate.resolve()
    if not _inside(resolved, repo_root):
        _fail(
            candidate,
            "Model reference must remain inside the repository",
            code="CAD109",
            kind="unsafe_path",
            value=str(reference),
        )
    return resolved


def _read_json(path: Path) -> dict[str, object]:
    non_finite: str | None = None

    def reject_non_finite(value: str) -> None:
        nonlocal non_finite
        non_finite = value
        raise ValueError(value)

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_non_finite)
    except json.JSONDecodeError as error:
        _fail(
            path,
            f"Invalid model sidecar JSON: {error.msg}",
            code="CAD100",
            kind="invalid_json",
            line=error.lineno,
            column=error.colno,
        )
    except ValueError:
        assert non_finite is not None
        _fail(
            path,
            "Model sidecar numbers must be finite JSON numbers",
            code="CAD105",
            value=non_finite,
            json_path="$",
        )
    if not isinstance(value, dict):
        _fail(path, "Model sidecar must be a JSON object", json_path="$", value=value)
    return value


def _unknown_keys(
    value: Mapping[str, object], allowed: frozenset[str], path: Path, json_path: str
) -> None:
    for key in value:
        if key not in allowed:
            _fail(
                path,
                f"Unknown metadata key {key!r}",
                json_path=f"{json_path}.{key}",
                value=key,
            )


def _string(
    value: Mapping[str, object], key: str, path: Path, *, default: str | None = None
) -> str:
    result = value.get(key, default)
    if not isinstance(result, str):
        _fail(
            path,
            f"$.{key} must be a string",
            json_path=f"$.{key}",
            value=result,
        )
    return result


def _mapping(
    value: Mapping[str, object], key: str, path: Path, json_path: str
) -> Mapping[str, object]:
    result = value.get(key, {})
    if not isinstance(result, dict):
        _fail(path, f"{json_path} must be a JSON object", json_path=json_path, value=result)
    return MappingProxyType(result.copy())


def _declared_sets(
    source: str, source_path: Path, *, require_declaration: bool
) -> tuple[str, tuple[str, ...]]:
    has_declaration = SET_ASSIGNMENT.search(source) is not None
    default, choices = parse_set_declaration(source, source_path)
    if not has_declaration:
        if require_declaration:
            _fail(
                source_path,
                "The SCAD source requires a set declaration with Customizer choices",
                code="CAD108",
                kind="missing_set_declaration",
            )
        return "", ("",)
    for name in choices:
        if not _SAFE_NAME.fullmatch(name):
            _fail(source_path, f"Unsafe set name {name!r}", value=name)
    if len(set(choices)) != len(choices):
        _fail(source_path, "Set choices must not contain duplicates", value=choices)
    if default and default not in choices:
        _fail(
            source_path,
            f"Assigned default set {default!r} is not a declared choice",
            code="CAD111",
            kind="unknown_set",
            value=default,
            choices=choices,
            suggestion=_suggest(default, choices),
        )
    ordered = (("",) + choices) if not default else choices
    return default, ordered


def _advisory(path: Path, name: str, json_path: str | None = None) -> CadDiagnostic:
    label = name or "(default)"
    return _diagnostic(
        path,
        "CAD112",
        "missing_description",
        f"Set {label!r} has no description",
        json_path=json_path,
        value=name,
        fix="Add a canonical description to the model sidecar",
    )


def load_model(model_id: str, reference: Path, repo_root: Path) -> CadModel:
    """Load a direct SCAD model or a SCAD model described by an adjacent sidecar."""

    repo_root = repo_root.resolve()
    reference_path = _resolve_reference(Path(reference), repo_root)
    if not _SAFE_NAME.fullmatch(model_id):
        _fail(reference_path, f"Unsafe model ID {model_id!r}", value=model_id)

    if reference_path.suffix == ".scad":
        source = reference_path.read_text(encoding="utf-8")
        default, names = _declared_sets(source, reference_path, require_declaration=False)
        sets = {name: CadSet(name=name, variables=MappingProxyType({}), slicing=MappingProxyType({})) for name in names}
        advisories = tuple(_advisory(reference_path, name) for name in names)
        return CadModel(
            model_id=model_id,
            name=model_id,
            description="",
            source_path=reference_path,
            sidecar_path=None,
            default_set=default,
            sets=MappingProxyType(sets),
            variables=MappingProxyType({}),
            metadata_snapshot=MappingProxyType({}),
            advisories=advisories,
        )
    if not reference_path.name.endswith(".cad.json"):
        _fail(reference_path, "Model reference must end in .scad or .cad.json")

    metadata = _read_json(reference_path)
    _unknown_keys(metadata, _SIDECAR_KEYS, reference_path, "$")
    schema = _string(metadata, "schema", reference_path)
    if schema != "plamp-cad-model/1":
        _fail(
            reference_path,
            "$.schema must equal 'plamp-cad-model/1'",
            json_path="$.schema",
            value=schema,
        )
    name = _string(metadata, "name", reference_path)
    if not _SAFE_NAME.fullmatch(name):
        _fail(reference_path, f"Unsafe model name {name!r}", json_path="$.name", value=name)
    source_reference = _string(metadata, "source", reference_path)
    description = _string(metadata, "description", reference_path, default="")

    source_candidate = reference_path.parent / source_reference
    source_path = source_candidate.resolve()
    if Path(source_reference).is_absolute() or not _inside(source_path, reference_path.parent):
        _fail(
            reference_path,
            "$.source must remain inside the model folder",
            code="CAD109",
            kind="unsafe_path",
            json_path="$.source",
            value=source_reference,
        )
    source = source_path.read_text(encoding="utf-8")
    default, names = _declared_sets(source, source_path, require_declaration=True)

    raw_sets = metadata.get("sets", {})
    if not isinstance(raw_sets, dict):
        _fail(reference_path, "$.sets must be a JSON object", json_path="$.sets", value=raw_sets)
    for set_name in raw_sets:
        if set_name not in names:
            _fail(
                reference_path,
                f"Sidecar references unknown set {set_name!r}",
                code="CAD111",
                kind="unknown_set",
                json_path=f"$.sets.{set_name}",
                value=set_name,
                choices=names,
                suggestion=_suggest(set_name, names),
            )

    sets: dict[str, CadSet] = {}
    advisories = []
    for set_name in names:
        raw = raw_sets.get(set_name, {})
        json_path = f"$.sets.{set_name}"
        if not isinstance(raw, dict):
            _fail(reference_path, f"{json_path} must be a JSON object", json_path=json_path, value=raw)
        _unknown_keys(raw, _SET_KEYS, reference_path, json_path)
        set_description = raw.get("description", "")
        if not isinstance(set_description, str):
            _fail(reference_path, f"{json_path}.description must be a string", json_path=f"{json_path}.description", value=set_description)
        printable = raw.get("printable", True)
        if not isinstance(printable, bool):
            _fail(reference_path, f"{json_path}.printable must be a boolean", json_path=f"{json_path}.printable", value=printable)
        sets[set_name] = CadSet(
            name=set_name,
            description=set_description,
            variables=_mapping(raw, "variables", reference_path, f"{json_path}.variables"),
            printable=printable,
            slicing=_mapping(raw, "slicing", reference_path, f"{json_path}.slicing"),
        )
        if not set_description:
            advisories.append(_advisory(reference_path, set_name, json_path))

    return CadModel(
        model_id=model_id,
        name=name,
        description=description,
        source_path=source_path,
        sidecar_path=reference_path,
        default_set=default,
        sets=MappingProxyType(sets),
        variables=_mapping(metadata, "variables", reference_path, "$.variables"),
        metadata_snapshot=MappingProxyType(metadata.copy()),
        advisories=tuple(advisories),
    )
