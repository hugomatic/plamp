"""Parse embedded generation metadata from OpenSCAD documents."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from difflib import get_close_matches
import json
from pathlib import Path
import re


_METADATA_SENTINEL = "/* generate.json"
_VIEW_ASSIGNMENT = re.compile(
    r'^\s*view\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;(?P<trailing>[^\n]*)',
    re.MULTILINE,
)
_CUSTOMIZER_CHOICES = re.compile(r"//\s*\[([^]]*)\]")


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
class ViewMetadata:
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PresetMetadata:
    description: str = ""
    items: tuple[str, ...] = ()
    variables: Mapping[str, object] = field(default_factory=dict)
    view_variables: Mapping[str, Mapping[str, object]] = field(default_factory=dict)


@dataclass(frozen=True)
class CadDocument:
    path: Path
    default_view: str | None
    views: tuple[str, ...]
    global_variables: Mapping[str, object]
    view_metadata: Mapping[str, ViewMetadata]
    presets: Mapping[str, PresetMetadata]
    default_preset: str | None
    metadata_snapshot: Mapping[str, object]


def diagnostics_json(diagnostics: Iterable[CadDiagnostic]) -> str:
    """Return stable JSON for diagnostics at machine-readable command boundaries."""

    return json.dumps([asdict(diagnostic) for diagnostic in diagnostics], sort_keys=True)


def _suggest(value: object, choices: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    matches = get_close_matches(value, choices, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _diagnostic(
    path: Path,
    code: str,
    kind: str,
    message: str,
    *,
    json_path: str | None = None,
    line: int | None = None,
    column: int | None = None,
    value: object | None = None,
    choices: tuple[str, ...] = (),
    suggestion: str | None = None,
    fix: str | None = None,
) -> CadDiagnostic:
    return CadDiagnostic(
        code=code,
        kind=kind,
        message=message,
        source=str(path),
        json_path=json_path,
        line=line,
        column=column,
        value=value,
        choices=choices,
        suggestion=suggestion,
        fix=fix,
    )


def _parse_view_declaration(source: str) -> tuple[str | None, tuple[str, ...]]:
    match = _VIEW_ASSIGNMENT.search(source)
    if match is None:
        return None, ()

    try:
        default_view = json.loads(f'"{match.group("value")}"')
    except json.JSONDecodeError:
        default_view = match.group("value")

    choices_match = _CUSTOMIZER_CHOICES.search(match.group("trailing"))
    if choices_match is None:
        return default_view, ()
    choices = tuple(
        choice.strip()
        for choice in choices_match.group(1).split(",")
        if choice.strip()
    )
    return default_view, choices


def _parse_metadata(source: str, path: Path) -> dict[str, object]:
    sentinel_offset = source.find(_METADATA_SENTINEL)
    if sentinel_offset < 0:
        return {}
    json_offset = sentinel_offset + len(_METADATA_SENTINEL)
    end_offset = source.find("*/", json_offset)
    if end_offset < 0:
        raise CadMetadataError(
            (
                _diagnostic(
                    path,
                    "CAD100",
                    "invalid_json",
                    "The generate.json comment is missing its closing */",
                    line=1,
                    column=1,
                ),
            )
        )

    metadata_source = source[json_offset:end_offset]
    try:
        metadata = json.loads(metadata_source)
    except json.JSONDecodeError as error:
        raise CadMetadataError(
            (
                _diagnostic(
                    path,
                    "CAD100",
                    "invalid_json",
                    f"Invalid generate.json metadata: {error.msg}",
                    line=error.lineno,
                    column=error.colno,
                ),
            )
        ) from None
    if not isinstance(metadata, dict):
        raise CadMetadataError(
            (
                _diagnostic(
                    path,
                    "CAD105",
                    "invalid_metadata",
                    "generate.json metadata must be a JSON object",
                    json_path="$",
                    value=metadata,
                ),
            )
        )
    return metadata


def _mapping_value(
    container: Mapping[str, object],
    key: str,
    path: Path,
    json_path: str,
    diagnostics: list[CadDiagnostic],
) -> dict[str, object]:
    value = container.get(key, {})
    if isinstance(value, dict):
        return value
    diagnostics.append(
        _diagnostic(
            path,
            "CAD105",
            "invalid_metadata",
            f"{json_path} must be a JSON object",
            json_path=json_path,
            value=value,
        )
    )
    return {}


def _string_value(
    container: Mapping[str, object],
    key: str,
    path: Path,
    json_path: str,
    diagnostics: list[CadDiagnostic],
    default: str = "",
) -> str:
    value = container.get(key, default)
    if isinstance(value, str):
        return value
    diagnostics.append(
        _diagnostic(
            path,
            "CAD105",
            "invalid_metadata",
            f"{json_path} must be a string",
            json_path=json_path,
            value=value,
        )
    )
    return default


def _build_view_metadata(
    raw_views: Mapping[str, object],
    path: Path,
    diagnostics: list[CadDiagnostic],
) -> dict[str, ViewMetadata]:
    result = {}
    for name, raw_view in raw_views.items():
        json_path = f"$.views.{name}"
        if not isinstance(raw_view, dict):
            diagnostics.append(
                _diagnostic(
                    path,
                    "CAD105",
                    "invalid_metadata",
                    f"{json_path} must be a JSON object",
                    json_path=json_path,
                    value=raw_view,
                )
            )
            raw_view = {}
        result[name] = ViewMetadata(
            description=_string_value(
                raw_view, "description", path, f"{json_path}.description", diagnostics
            ),
            variables=_mapping_value(
                raw_view, "variables", path, f"{json_path}.variables", diagnostics
            ),
        )
    return result


def _build_presets(
    raw_presets: Mapping[str, object],
    path: Path,
    diagnostics: list[CadDiagnostic],
) -> dict[str, PresetMetadata]:
    result = {}
    for name, raw_preset in raw_presets.items():
        json_path = f"$.presets.{name}"
        if not isinstance(raw_preset, dict):
            diagnostics.append(
                _diagnostic(
                    path,
                    "CAD105",
                    "invalid_metadata",
                    f"{json_path} must be a JSON object",
                    json_path=json_path,
                    value=raw_preset,
                )
            )
            raw_preset = {}

        raw_items = raw_preset.get("items", [])
        if not isinstance(raw_items, list):
            diagnostics.append(
                _diagnostic(
                    path,
                    "CAD105",
                    "invalid_metadata",
                    f"{json_path}.items must be a JSON array",
                    json_path=f"{json_path}.items",
                    value=raw_items,
                )
            )
            raw_items = []

        raw_view_variables = _mapping_value(
            raw_preset,
            "view_variables",
            path,
            f"{json_path}.view_variables",
            diagnostics,
        )
        view_variables = {}
        for view_name, variables in raw_view_variables.items():
            view_path = f"{json_path}.view_variables.{view_name}"
            if not isinstance(variables, dict):
                diagnostics.append(
                    _diagnostic(
                        path,
                        "CAD104",
                        "invalid_view_variables",
                        f"{view_path} must be a JSON object",
                        json_path=view_path,
                        value=variables,
                    )
                )
                continue
            view_variables[view_name] = variables

        result[name] = PresetMetadata(
            description=_string_value(
                raw_preset,
                "description",
                path,
                f"{json_path}.description",
                diagnostics,
            ),
            items=tuple(raw_items),
            variables=_mapping_value(
                raw_preset,
                "variables",
                path,
                f"{json_path}.variables",
                diagnostics,
            ),
            view_variables=view_variables,
        )
    return result


def _validate_references(
    document: CadDocument, diagnostics: list[CadDiagnostic]
) -> None:
    view_choices = document.views
    preset_choices = tuple(document.presets)

    for view_name in document.view_metadata:
        if view_name not in view_choices:
            diagnostics.append(
                _diagnostic(
                    document.path,
                    "CAD101",
                    "unknown_view",
                    f"Unknown view {view_name!r}",
                    json_path=f"$.views.{view_name}",
                    value=view_name,
                    choices=view_choices,
                    suggestion=_suggest(view_name, view_choices),
                )
            )

    for preset_name, preset in document.presets.items():
        for item_index, item in enumerate(preset.items):
            item_path = f"$.presets.{preset_name}.items[{item_index}]"
            if not isinstance(item, str) or ":" not in item:
                diagnostics.append(
                    _diagnostic(
                        document.path,
                        "CAD103",
                        "invalid_item_prefix",
                        "Preset items must use a view: or preset: prefix",
                        json_path=item_path,
                        value=item,
                        choices=("view", "preset"),
                        fix="Use view:<name> or preset:<name>",
                    )
                )
                continue
            namespace, name = item.split(":", 1)
            if namespace not in ("view", "preset"):
                diagnostics.append(
                    _diagnostic(
                        document.path,
                        "CAD103",
                        "invalid_item_prefix",
                        f"Unknown preset item prefix {namespace!r}",
                        json_path=item_path,
                        value=namespace,
                        choices=("view", "preset"),
                        fix=f"Use view:{name} or preset:{name}",
                    )
                )
            elif namespace == "view" and name not in view_choices:
                diagnostics.append(
                    _diagnostic(
                        document.path,
                        "CAD101",
                        "unknown_view",
                        f"Unknown view {name!r}",
                        json_path=item_path,
                        value=name,
                        choices=view_choices,
                        suggestion=_suggest(name, view_choices),
                    )
                )
            elif namespace == "preset" and name not in preset_choices:
                diagnostics.append(
                    _diagnostic(
                        document.path,
                        "CAD102",
                        "unknown_preset",
                        f"Unknown preset {name!r}",
                        json_path=item_path,
                        value=name,
                        choices=preset_choices,
                        suggestion=_suggest(name, preset_choices),
                    )
                )

        for view_name in preset.view_variables:
            if view_name not in view_choices:
                diagnostics.append(
                    _diagnostic(
                        document.path,
                        "CAD101",
                        "unknown_view",
                        f"Unknown view {view_name!r}",
                        json_path=(
                            f"$.presets.{preset_name}.view_variables.{view_name}"
                        ),
                        value=view_name,
                        choices=view_choices,
                        suggestion=_suggest(view_name, view_choices),
                    )
                )

    if (
        document.default_preset is not None
        and document.default_preset not in preset_choices
    ):
        diagnostics.append(
            _diagnostic(
                document.path,
                "CAD102",
                "unknown_preset",
                f"Unknown preset {document.default_preset!r}",
                json_path="$.default_preset",
                value=document.default_preset,
                choices=preset_choices,
                suggestion=_suggest(document.default_preset, preset_choices),
            )
        )


def parse_cad_document(path: str | Path) -> CadDocument:
    """Parse one SCAD document and validate all embedded metadata references."""

    document_path = Path(path)
    source = document_path.read_text(encoding="utf-8")
    default_view, views = _parse_view_declaration(source)
    metadata = _parse_metadata(source, document_path)
    diagnostics: list[CadDiagnostic] = []

    raw_views = _mapping_value(
        metadata, "views", document_path, "$.views", diagnostics
    )
    raw_presets = _mapping_value(
        metadata, "presets", document_path, "$.presets", diagnostics
    )
    default_preset_value = metadata.get("default_preset")
    if default_preset_value is not None and not isinstance(default_preset_value, str):
        diagnostics.append(
            _diagnostic(
                document_path,
                "CAD105",
                "invalid_metadata",
                "$.default_preset must be a string",
                json_path="$.default_preset",
                value=default_preset_value,
            )
        )
        default_preset_value = None

    document = CadDocument(
        path=document_path,
        default_view=default_view,
        views=views,
        global_variables=_mapping_value(
            metadata,
            "global_variables",
            document_path,
            "$.global_variables",
            diagnostics,
        ),
        view_metadata=_build_view_metadata(raw_views, document_path, diagnostics),
        presets=_build_presets(raw_presets, document_path, diagnostics),
        default_preset=default_preset_value,
        metadata_snapshot=metadata,
    )
    _validate_references(document, diagnostics)
    if diagnostics:
        raise CadMetadataError(diagnostics)
    return document
