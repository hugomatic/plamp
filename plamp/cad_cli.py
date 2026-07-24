"""Human-facing command boundary for the local CAD engine."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
from statistics import median
import subprocess
from collections.abc import Callable, Mapping
from typing import Any, TextIO

from plamp.cad_generation import (
    CadRunExistsError,
    GENERATOR_VERSION,
    GenerationResult,
    generate_plan,
    list_runs,
    load_job_log,
    load_run,
    prepare_source,
    resolve_openscad,
    resolve_part,
)
from plamp.cad_metadata import CadDiagnostic, CadMetadataError
from plamp.cad_model import CadMetadataError as CadCatalogMetadataError
from plamp.cad_system import (
    CadSystem,
    SystemCandidate,
    discover_systems,
    load_system,
    select_system,
)
from plamp.cad_planning import CadSelection, build_render_plan, plan_as_dict
from plamp.cad_scaffold import (
    CadDestinationExistsError,
    CadSelectionError,
    create_model,
    discover_templates,
)
from plamp.context import RuntimeContext


CadFunction = Callable[..., Any]


class _RemovedOption(argparse.Action):
    def __init__(self, option_strings: list[str], dest: str, **kwargs: object) -> None:
        kwargs.setdefault("nargs", 1)
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace,
                 values: object, option_string: str | None = None) -> None:
        replacements = {
            "--view": "--set", "--view-define": "--set-define",
            "--preset": "--product (or MODEL --set SET)",
        }
        parser.error(
            f"{option_string} was removed; use {replacements[option_string or '']}"
        )


class CadOperationError(RuntimeError):
    """An expected failure after CAD generation or archive access began."""


class CadSelectionCancelled(ValueError):
    """Interactive CAD selection ended without a choice."""


def _selection_arguments(parser: argparse.ArgumentParser) -> None:
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--product", metavar="NAME")
    choices.add_argument("--all-sets", action="store_true")
    parser.add_argument("--set", action="append", default=[], metavar="NAME")
    parser.add_argument(
        "--define", "-D", action="append", default=[], metavar="NAME=EXPR"
    )
    parser.add_argument(
        "--set-define", action="append", default=[], metavar="SET:NAME=VALUE"
    )
    parser.add_argument(
        "--revision", metavar="LABEL", help="literal revision engraving label"
    )
    for obsolete in ("--view", "--view-define", "--preset"):
        parser.add_argument(obsolete, action=_RemovedOption, help=argparse.SUPPRESS)


def add_cad_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the local ``cad`` command group to an argparse subparser set."""

    cad = subparsers.add_parser("cad", help="inspect and generate local CAD parts")
    actions = cad.add_subparsers(dest="action", required=True)

    new = actions.add_parser("new")
    new.add_argument("model", nargs="?")
    new.add_argument("--system", metavar="NAME_OR_PATH")
    new.add_argument("--template")
    new.add_argument("--json", action="store_true")

    systems = actions.add_parser("systems", help="list discoverable CAD systems")
    systems.add_argument("--json", action="store_true")

    for action in ("models", "products", "profiles", "libraries"):
        command = actions.add_parser(action, help=f"list CAD {action}")
        command.add_argument("--system", metavar="NAME_OR_PATH")
        command.add_argument("--json", action="store_true")

    sets = actions.add_parser("sets", help="list authoritative model sets")
    sets.add_argument("model")
    sets.add_argument("--system", metavar="NAME_OR_PATH")
    sets.add_argument("--json", action="store_true")

    templates = actions.add_parser("templates", help="list CAD model templates")
    templates.add_argument("--json", action="store_true")

    obsolete = actions.add_parser("views", help=argparse.SUPPRESS)
    obsolete.add_argument("model", nargs="?")
    obsolete.add_argument("--json", action="store_true")
    # Keep a parser solely to emit the migration diagnostic without advertising
    # the removed command in normal navigation/help.
    actions._choices_actions.pop()  # type: ignore[attr-defined]
    validate = actions.add_parser("validate")
    validate.add_argument("model", nargs="?")
    validate.add_argument("--system", metavar="NAME_OR_PATH")
    validate.add_argument("--json", action="store_true")

    plan = actions.add_parser("plan")
    plan.add_argument("model", nargs="?")
    plan.add_argument("--system", metavar="NAME_OR_PATH")
    _selection_arguments(plan)
    plan.add_argument("--json", action="store_true")

    menu = actions.add_parser("menu")
    menu.add_argument("model", nargs="?")
    menu.add_argument("--system", metavar="NAME_OR_PATH")
    _selection_arguments(menu)
    menu.add_argument("--output", type=Path)
    menu.add_argument("--openscad", default=None)
    menu.add_argument(
        "--regenerate",
        action="store_true",
        help="replace a matching managed run after rendering succeeds",
    )
    menu.add_argument("--json", action="store_true")

    generate = actions.add_parser(
        "generate",
        description=(
            "Generate STL artifacts directly. Choose --product, or a model with "
            "repeatable --set/--all-sets."
        ),
        epilog=(
            "Source and revision: use --revision LABEL for a literal engraving; "
            "dirty source is archived from the working tree. Output: the default "
            "is a managed archive; --output DIR "
            "selects a directory. Preview: --preview inserts render_fn=24 and "
            "render_text=false before explicit definitions, so explicit values "
            "override them. OpenSCAD resolution order is --openscad, OPENSCAD_BIN, "
            "PATH, then platform fallback paths."
        ),
    )
    generate.add_argument("model", nargs="?")
    generate.add_argument("--system", metavar="NAME_OR_PATH")
    _selection_arguments(generate)
    generate.add_argument(
        "--preview",
        action="store_true",
        help="disable rendered text and use render_fn=24",
    )
    generate.add_argument("--output", type=Path, metavar="DIR")
    generate.add_argument("--openscad", default=None)
    generate.add_argument(
        "--regenerate",
        action="store_true",
        help="replace a matching managed run after rendering succeeds",
    )
    generate.add_argument("--json", action="store_true")

    runs = actions.add_parser("runs")
    runs.add_argument("part", nargs="?")
    runs.add_argument("--json", action="store_true")

    show = actions.add_parser("show")
    show.add_argument("run")
    show.add_argument("--json", action="store_true")

    log = actions.add_parser("log")
    log.add_argument("run")
    log.add_argument("artifact")
    log.add_argument("--json", action="store_true")

    actions.metavar = (
        "{new,systems,models,products,profiles,libraries,sets,templates,"
        "validate,plan,menu,generate,runs,show,log}"
    )


def _dependencies(overrides: Mapping[str, CadFunction] | None) -> dict[str, CadFunction]:
    values: dict[str, CadFunction] = {
        "resolve_part": resolve_part,
        "prepare_source": prepare_source,
        "resolve_openscad": resolve_openscad,
        "build_plan": build_render_plan,
        "generate": generate_plan,
        "list_runs": list_runs,
        "load_run": load_run,
        "load_job_log": load_job_log,
        "discover_templates": discover_templates,
        "create_model": create_model,
        "discover_systems": discover_systems,
        "select_system": select_system,
        "load_system": load_system,
    }
    if overrides:
        values.update(overrides)
    return values


def _json_line(stream: TextIO, value: object) -> None:
    stream.write(json.dumps(value, sort_keys=True) + "\n")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _described(value: str) -> str:
    return value or "(no description)"


def _diagnostics_value(diagnostics: tuple[CadDiagnostic, ...]) -> list[dict[str, object]]:
    return [asdict(item) for item in diagnostics]


def _interactive(stdin: TextIO, args: argparse.Namespace) -> bool:
    return not bool(getattr(args, "json", False)) and bool(
        getattr(stdin, "isatty", lambda: False)()
    )


def _choose_system(
    candidates: tuple[SystemCandidate, ...], stdin: TextIO, stdout: TextIO
) -> SystemCandidate:
    selectable = tuple(item for item in candidates if item.status == "valid")
    if not selectable:
        raise ValueError("no valid CAD systems are available")
    stdout.write("Systems:\n")
    for index, item in enumerate(selectable, 1):
        stdout.write(f"{index}. {item.name} - {_described(item.description)}\n")
    stdout.write("Select System (or b to go back): ")
    stdout.flush()
    value = stdin.readline().strip()
    if value.lower() in {"b", "back"}:
        raise CadSelectionCancelled("CAD system selection cancelled")
    try:
        choice = int(value)
    except ValueError:
        choice = 0
    if not 1 <= choice <= len(selectable):
        raise ValueError("invalid system selection")
    return selectable[choice - 1]


def _choose_template(templates: tuple[object, ...], stdin: TextIO,
                     stdout: TextIO) -> str:
    if not templates:
        raise ValueError("no CAD templates are available")
    stdout.write("Templates:\n")
    for index, item in enumerate(templates, 1):
        stdout.write(f"{index}. {item.name} - {_described(item.description)}\n")
    stdout.write("Select Template: ")
    stdout.flush()
    value = stdin.readline().strip()
    try:
        choice = int(value)
    except ValueError:
        choice = 0
    if not 1 <= choice <= len(templates):
        raise ValueError("invalid template selection")
    return templates[choice - 1].name


def _selected_system(
    args: argparse.Namespace,
    context: RuntimeContext,
    stdin: TextIO,
    stdout: TextIO,
    deps: Mapping[str, CadFunction],
) -> CadSystem:
    candidates = tuple(deps["discover_systems"](context.root))
    selector = getattr(args, "system", None)
    if selector is not None:
        candidate = deps["select_system"](candidates, selector)
    elif len(candidates) == 1:
        candidate = candidates[0]
    elif not candidates:
        raise ValueError(
            "no CAD systems are available; add a *.system.cad.json manifest "
            "under cad/ or select an explicit manifest with --system NAME_OR_PATH"
        )
    elif not _interactive(stdin, args):
        choices = ", ".join(item.name or str(item.path) for item in candidates)
        raise ValueError(
            "multiple CAD systems are available; select one with "
            f"--system NAME_OR_PATH (available: {choices or '(none)'})"
        )
    else:
        candidate = _choose_system(candidates, stdin, stdout)
    if candidate.status != "valid":
        if candidate.diagnostics:
            raise CadMetadataError(candidate.diagnostics)
        raise ValueError(f"CAD system is invalid: {candidate.path}")
    return deps["load_system"](candidate.path, context.root)


def _read_catalog_choice(stdin: TextIO, prompt: str, stdout: TextIO) -> str:
    stdout.write(prompt)
    stdout.flush()
    try:
        value = stdin.readline()
    except KeyboardInterrupt:
        raise CadSelectionCancelled("CAD catalog browsing cancelled") from None
    return "q" if value == "" else value.strip().lower()


def _catalog_browser(
    context: RuntimeContext,
    stdin: TextIO,
    stdout: TextIO,
    deps: Mapping[str, CadFunction],
) -> int:
    """Browse system -> model -> set while retaining parent selection on back."""

    candidates = tuple(
        candidate for candidate in deps["discover_systems"](context.root)
        if candidate.status == "valid"
    )
    if not candidates:
        raise ValueError("no valid CAD systems are available")
    selected: SystemCandidate | None = candidates[0] if len(candidates) == 1 else None
    while True:
        if selected is None:
            stdout.write("Systems:\n")
            for index, candidate in enumerate(candidates, 1):
                stdout.write(
                    f"{index}. {candidate.name} - {_described(candidate.description)}\n"
                )
            choice = _read_catalog_choice(
                stdin, "Select System (q to quit): ", stdout
            )
            if choice in {"q", "quit"}:
                return 0
            if not choice.isdigit() or not 1 <= int(choice) <= len(candidates):
                stdout.write("Invalid selection.\n")
                continue
            selected = candidates[int(choice) - 1]

        system = deps["load_system"](selected.path, context.root)
        while selected is not None:
            models = tuple(system.models.items())
            stdout.write(
                f"System {system.name}: {_described(system.description)}\nModels:\n"
            )
            for index, (model_id, model) in enumerate(models, 1):
                stdout.write(
                    f"{index}. model {model_id} - {_described(model.description)}\n"
                )
            stdout.write("Products:\n")
            for product_id, product in system.products.items():
                stdout.write(
                    f"- product {product_id} - {_described(product.description)}\n"
                )
            choice = _read_catalog_choice(
                stdin, "Select model (b for systems, q to quit): ", stdout
            )
            if choice in {"q", "quit"}:
                return 0
            if choice in {"b", "back"}:
                selected = None
                break
            if not choice.isdigit() or not 1 <= int(choice) <= len(models):
                stdout.write("Invalid selection.\n")
                continue
            model_id, model = models[int(choice) - 1]
            while True:
                stdout.write(f"Sets for {model_id}:\n")
                for cad_set in model.sets.values():
                    stdout.write(
                        f"set {cad_set.name or '(default)'} - "
                        f"{_described(cad_set.description)}\n"
                    )
                choice = _read_catalog_choice(
                    stdin, "b for models, q to quit: ", stdout
                )
                if choice in {"q", "quit"}:
                    return 0
                if choice in {"b", "back"}:
                    break
                stdout.write("Choose b or q.\n")


def _emit_rows(rows: list[dict[str, object]], json_output: bool, stdout: TextIO) -> None:
    if json_output:
        _json_line(stdout, rows)
        return
    if not rows:
        stdout.write("(none)\n")
        return
    for row in rows:
        status = "" if row.get("status") == "valid" else f" [{row.get('status')}]"
        stdout.write(
            f"{row['kind']} {row['id'] or '(default)'}{status} - "
            f"{row['description']} - {row['path']}\n"
        )


def _system_rows(context: RuntimeContext, deps: Mapping[str, CadFunction]) -> list[dict[str, object]]:
    rows = []
    for item in deps["discover_systems"](context.root):
        rows.append({
            "kind": "system", "id": item.name, "system": item.name,
            "description": _described(item.description),
            "default_product": item.default_product, "status": item.status,
            "diagnostics": _diagnostics_value(item.diagnostics),
            "path": _relative(item.path, context.root),
        })
    return rows


def _catalog_rows(action: str, system: CadSystem, context: RuntimeContext,
                  model_id: str | None = None) -> list[dict[str, object]]:
    base = {"system": system.name, "status": "valid", "diagnostics": []}
    rows: list[dict[str, object]] = []
    if action == "models":
        for name, model in system.models.items():
            rows.append({"kind": "model", "id": name, **base,
                         "description": _described(model.description),
                         "path": _relative(model.sidecar_path or model.source_path, context.root),
                         "source": _relative(model.source_path, context.root)})
    elif action == "sets":
        if model_id not in system.models:
            raise ValueError(f"unknown CAD model {model_id!r}")
        model = system.models[model_id]
        for name, cad_set in model.sets.items():
            rows.append({"kind": "set", "id": name, **base, "model": model_id,
                         "description": _described(cad_set.description),
                         "printable": cad_set.printable,
                         "source": _relative(model.source_path, context.root),
                         "path": _relative(model.source_path, context.root)})
    elif action == "products":
        for name, product in system.products.items():
            rows.append({"kind": "product", "id": name, **base,
                         "description": _described(product.description),
                         "path": _relative(system.path, context.root)})
    elif action == "profiles":
        for name, path in system.profiles.items():
            rows.append({"kind": "profile", "id": name, **base,
                         "description": "(no description)",
                         "path": _relative(path, context.root)})
    elif action == "libraries":
        for name, declaration in system.libraries.items():
            if isinstance(declaration, str):
                path, description = declaration, ""
            else:
                path = str(declaration.get("path", ""))
                description = str(declaration.get("description", ""))
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = context.root / resolved
            rows.append({"kind": "library", "id": name, **base,
                         "description": _described(description),
                         "path": _relative(resolved, context.root)})
    return rows


def _typed_json(value: object) -> str:
    """Canonical JSON that preserves scalar types for exact comparisons."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _diagnostic(
    error: BaseException, source: str, *, code: str, kind: str
) -> CadDiagnostic:
    return CadDiagnostic(code=code, kind=kind, message=str(error), source=source)


def _emit_diagnostics(
    diagnostics: tuple[CadDiagnostic, ...],
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
) -> None:
    if json_output:
        _json_line(stdout, [asdict(item) for item in diagnostics])
        return
    for item in diagnostics:
        location = item.source
        if item.line is not None:
            location += f":{item.line}"
            if item.column is not None:
                location += f":{item.column}"
        if item.json_path:
            location += f": {item.json_path}"
        message = f"{location}: {item.code}: {item.message}"
        if item.suggestion:
            message += f" (did you mean {item.suggestion!r}?)"
        if item.fix:
            message += f"; {item.fix}"
        stderr.write(message + "\n")


def _ordered_views(document: Any) -> list[dict[str, str]]:
    names = [name for name in document.views if name != "assembly"]
    names.extend(name for name in document.views if name == "assembly")
    return [
        {
            "name": name,
            "description": document.view_metadata.get(name).description
            if name in document.view_metadata
            else "",
        }
        for name in names
    ]


def _catalog(document: Any, source: Path) -> dict[str, object]:
    return {
        "part": source.parent.name,
        "source": str(source),
        "default_view": document.default_view,
        "default_preset": document.default_preset,
        "presets": [
            {"name": name, "description": preset.description}
            for name, preset in document.presets.items()
        ],
        "views": _ordered_views(document),
    }


def _set_defines(values: list[str]) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for value in values:
        if ":" not in value:
            raise ValueError("--set-define requires SET:NAME=VALUE")
        set_name, expression = value.split(":", 1)
        if "=" not in expression or not expression.split("=", 1)[0]:
            raise ValueError("--set-define requires SET:NAME=VALUE")
        name, raw = expression.split("=", 1)
        try:
            parsed: object = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        grouped.setdefault(set_name, {})[name] = parsed
    return grouped


def _selection(args: argparse.Namespace, *, menu: CadSelection | None = None) -> CadSelection:
    base = menu or CadSelection(
        product=getattr(args, "product", None), model=getattr(args, "model", None),
        sets=tuple(getattr(args, "set", []) or []),
        all_sets=bool(getattr(args, "all_sets", False)),
    )
    if base.product and (base.model is not None or base.sets or base.all_sets):
        raise ValueError("--product cannot be combined with MODEL, --set, or --all-sets")
    raw_defines = []
    if getattr(args, "preview", False):
        raw_defines.extend(("render_fn=24", "render_text=false"))
    raw_defines.extend(getattr(args, "define", []) or [])
    return CadSelection(
        product=base.product, model=base.model, sets=base.sets,
        all_sets=base.all_sets, raw_defines=tuple(raw_defines),
        set_defines=_set_defines(list(getattr(args, "set_define", []) or [])),
    )


def _generation_revision(args: argparse.Namespace) -> str | None:
    return getattr(args, "revision", None)


def _generation_output(args: argparse.Namespace) -> Path | None:
    return getattr(args, "output", None)


def _with_plan(
    args: argparse.Namespace,
    context: RuntimeContext,
    deps: Mapping[str, CadFunction],
    selection: Selection | None = None,
    *,
    allow_dirty: bool = False,
    retain_snapshot: bool = False,
) -> tuple[Path, Any, Any, Any]:
    source = deps["resolve_part"](args.part, context.root)
    revision = (
        _generation_revision(args)
        if getattr(args, "action", None) == "generate"
        else getattr(args, "revision", None)
    )
    if allow_dirty and revision is None:
        revision = "working-tree-plan"
    snapshot = deps["prepare_source"](
        context.root,
        source,
        revision,
        revision_is_commit=(
            False
        ),
    )
    snapshot_returned = False
    try:
        document = deps["parse_document"](snapshot.scad_path)
        selected = _selection(args, document, menu=selection)
        plan = deps["build_plan"](document, selected, snapshot.source_identity)
        snapshot_returned = retain_snapshot
        return source, document, plan, snapshot
    finally:
        if not snapshot_returned and snapshot.cleanup_root is not None:
            shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)


def _plan_object(
    plan: Any,
    document: Any,
    archived_runs: list[Mapping[str, object]],
    source_path: str,
) -> dict[str, object]:
    value = plan_as_dict(plan)
    value["job_count"] = len(plan.jobs)
    value["shared_job_count"] = sum(1 for job in plan.jobs if len(job.preset_paths) > 1)
    for job in value["jobs"]:  # type: ignore[assignment]
        view = job["view"]
        job["description"] = (
            document.view_metadata[view].description
            if view in document.view_metadata
            else ""
        )
        elapsed_samples: list[float] = []
        size_samples: list[int] = []
        for run in archived_runs:
            source = run.get("source")
            generator_version = run.get("generator_version")
            if (
                not isinstance(source, Mapping)
                or source.get("scad_path") != source_path
                or type(generator_version) is not int
                or generator_version != GENERATOR_VERSION
            ):
                continue
            archived_jobs = run.get("jobs", [])
            if not isinstance(archived_jobs, list):
                continue
            for archived_job in archived_jobs:
                if (
                    not isinstance(archived_job, Mapping)
                    or archived_job.get("status") != "complete"
                    or archived_job.get("view") != job["view"]
                    or _typed_json(archived_job.get("variables"))
                    != _typed_json(job["variables"])
                    or _typed_json(archived_job.get("raw_defines", {}))
                    != _typed_json(job["raw_defines"])
                ):
                    continue
                elapsed = archived_job.get("elapsed_seconds")
                artifact_bytes = archived_job.get("artifact_bytes")
                if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
                    elapsed_samples.append(float(elapsed))
                if isinstance(artifact_bytes, int) and not isinstance(artifact_bytes, bool):
                    size_samples.append(artifact_bytes)
        estimate: dict[str, object] = {}
        if elapsed_samples:
            estimate["elapsed_seconds"] = median(elapsed_samples)
        if size_samples:
            estimate["artifact_bytes"] = median(size_samples)
        job["estimate"] = estimate or None
    estimated = [job["estimate"] for job in value["jobs"] if job["estimate"]]  # type: ignore[index]
    value["estimated_job_count"] = len(estimated)
    value["estimated_elapsed_seconds"] = sum(
        float(estimate.get("elapsed_seconds", 0)) for estimate in estimated
    )
    value["estimated_artifact_bytes"] = sum(
        int(estimate.get("artifact_bytes", 0)) for estimate in estimated
    )
    return value


def _print_plan(value: Mapping[str, object], stdout: TextIO) -> None:
    stdout.write(f"{value['job_count']} render job(s)\n")
    tree = value["preset_tree"]
    if tree:
        stdout.write("Preset tree:\n")

        def print_item(item: Mapping[str, object], indent: str) -> None:
            description = f" - {item['description']}" if item.get("description") else ""
            stdout.write(
                f"{indent}{item['kind']} {item.get('name') or 'default'}"
                f"{description}\n"
            )
            for child in item.get("items", []):
                print_item(child, indent + "  ")

        for node in tree:  # type: ignore[assignment]
            print_item({"kind": "preset", **node}, "- ")
    stdout.write("Jobs:\n")
    for job in value["jobs"]:  # type: ignore[assignment]
        description = f" - {job['description']}" if job["description"] else ""
        stdout.write(
            f"- {job['variant_name']} ({job['view'] or 'default'}){description}\n"
        )
        stdout.write(f"  artifact: {job['artifact_id']}\n")
        stdout.write(f"  fingerprint: {job['fingerprint']}\n")
        stdout.write(f"  variables: {json.dumps(job['variables'], sort_keys=True)}\n")
        if job["raw_defines"]:
            stdout.write(f"  raw defines: {json.dumps(job['raw_defines'], sort_keys=True)}\n")
        if len(job["preset_paths"]) > 1:
            stdout.write(f"  shared by: {json.dumps(job['preset_paths'])}\n")
        if job["estimate"]:
            stdout.write(f"  estimate: {json.dumps(job['estimate'], sort_keys=True)}\n")


def _load_exact_run(
    value: str, data_dir: Path, deps: Mapping[str, CadFunction]
) -> tuple[Path, Mapping[str, object]]:
    supplied = Path(value)
    if supplied.name != value or value in {"", ".", ".."}:
        raise FileNotFoundError(f"CAD run ID not found: {value}")
    archive_root = (data_dir / "cad" / "prints").resolve()
    matches: list[Path] = []
    if archive_root.is_dir():
        for part_dir in archive_root.iterdir():
            candidate = part_dir / value
            if not part_dir.is_dir() or not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            try:
                relative = resolved.relative_to(archive_root)
            except ValueError:
                continue
            if len(relative.parts) == 2:
                matches.append(resolved)
    if len(matches) != 1:
        raise FileNotFoundError(f"CAD run ID not found: {value}")
    manifest = deps["load_run"](matches[0])
    if not isinstance(manifest, Mapping) or manifest.get("run_id") != value:
        raise ValueError(f"CAD manifest run_id does not match requested ID: {value}")
    return matches[0], manifest


def _menu_selection(document: Any, stdin: TextIO, output: TextIO) -> Selection:
    entries: list[tuple[str, str]] = []
    for name, preset in document.presets.items():
        entries.append(("preset", name))
        output.write(f"{len(entries)}. preset {name} - {preset.description}\n")
    for item in _ordered_views(document):
        entries.append(("view", item["name"]))
        output.write(f"{len(entries)}. view {item['name']} - {item['description']}\n")
    if not entries:
        raise ValueError("no presets or selectable views were declared")

    for attempt in range(2):
        output.write("Select one preset or one or more views: ")
        output.flush()
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            raise CadSelectionCancelled("CAD menu selection cancelled") from None
        if line == "":
            raise CadSelectionCancelled("CAD menu selection cancelled at end of input")
        tokens = line.split()
        try:
            numbers = [int(token) for token in tokens]
        except ValueError:
            numbers = []
        if numbers and all(1 <= number <= len(entries) for number in numbers):
            chosen = [entries[number - 1] for number in numbers]
            if len(chosen) == 1 and chosen[0][0] == "preset":
                return Selection(preset=chosen[0][1])
            if all(kind == "view" for kind, _ in chosen):
                return Selection(views=tuple(name for _, name in chosen))
        if attempt == 0:
            output.write("Invalid selection; try once more.\n")
    raise ValueError("invalid menu selection")


def _generation_manifest(
    result: object, deps: Mapping[str, CadFunction]
) -> tuple[dict[str, object], str]:
    if isinstance(result, Mapping):
        manifest = dict(result)
        return manifest, str(manifest.get("status", "complete"))
    if isinstance(result, GenerationResult) or hasattr(result, "run_dir"):
        manifest = deps["load_run"](result.run_dir)
        return manifest, str(getattr(result, "status", manifest.get("status", "complete")))
    raise TypeError("CAD generator returned an unsupported result")


def _prepare_system_plan(
    args: argparse.Namespace, context: RuntimeContext, deps: Mapping[str, CadFunction],
    stdin: TextIO, stdout: TextIO, selection: CadSelection | None = None,
    *, allow_dirty: bool = False, selected_system: CadSystem | None = None,
) -> tuple[CadSystem, Any, dict[str, Any]]:
    system = selected_system or _selected_system(args, context, stdin, stdout, deps)
    selected = selection or _selection(args)
    if (selected.product is None and selected.model is None and not selected.sets
            and not selected.all_sets):
        if system.default_product is not None:
            selected = CadSelection(
                product=system.default_product, defines=selected.defines,
                set_defines=selected.set_defines, raw_defines=selected.raw_defines,
            )
        elif _interactive(stdin, args):
            chosen = _product_or_set_menu(system, stdin, stdout)
            selected = CadSelection(
                product=chosen.product, model=chosen.model, sets=chosen.sets,
                all_sets=chosen.all_sets, defines=selected.defines,
                set_defines=selected.set_defines, raw_defines=selected.raw_defines,
            )
        else:
            raise ValueError(
                "CAD system has no default product; select one with --product NAME "
                "or choose MODEL --set SET"
            )
    preliminary = deps["build_plan"](
        system, selected, {name: "pending" for name in system.models}
    )
    model_ids = tuple(dict.fromkeys(job.model_id for job in preliminary.jobs))
    snapshots: dict[str, Any] = {}
    try:
        revision = _generation_revision(args) if getattr(args, "action", None) == "generate" else getattr(args, "revision", None)
        if allow_dirty and revision is None:
            revision = "working-tree-plan"
        for model_id in model_ids:
            snapshots[model_id] = deps["prepare_source"](
                context.root, system.models[model_id].source_path, revision,
                revision_is_commit=False,
            )
        plan = deps["build_plan"](
            system, selected,
            {name: snapshot.source_identity for name, snapshot in snapshots.items()},
        )
        return system, plan, snapshots
    except BaseException:
        for snapshot in snapshots.values():
            if snapshot.cleanup_root is not None:
                shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)
        raise


def _model_set_menu(system: CadSystem, model_name: str, stdin: TextIO,
                    stdout: TextIO) -> CadSelection | None:
    if model_name not in system.models:
        raise ValueError(f"Unknown model {model_name!r}")
    model = system.models[model_name]
    while True:
        sets = tuple(model.sets)
        stdout.write(f"Sets for {model_name}:\n")
        for index, set_name in enumerate(sets, 1):
            stdout.write(f"{index}. set {set_name or '(default)'} - {_described(model.sets[set_name].description)}\n")
        selected = _read_catalog_choice(stdin, "Select set (b for products/models): ", stdout)
        if selected in {"b", "back"}:
            return None
        if selected.isdigit() and 1 <= int(selected) <= len(sets):
            return CadSelection(model=model_name, sets=(sets[int(selected) - 1],))
        stdout.write("Invalid selection.\n")


def _product_or_set_menu(system: CadSystem, stdin: TextIO, stdout: TextIO,
                         model_name: str | None = None) -> CadSelection:
    if model_name is not None:
        selected = _model_set_menu(system, model_name, stdin, stdout)
        if selected is not None:
            return selected
    while True:
        entries: list[tuple[str, str]] = []
        stdout.write(f"System {system.name}: {_described(system.description)}\nProducts:\n")
        for name, product in system.products.items():
            entries.append(("product", name))
            stdout.write(f"{len(entries)}. product {name} - {_described(product.description)}\n")
        stdout.write("Models:\n")
        for name, model in system.models.items():
            entries.append(("model", name))
            stdout.write(f"{len(entries)}. model {name} - {_described(model.description)}\n")
        choice = _read_catalog_choice(stdin, "Select product or model (q to quit): ", stdout)
        if choice in {"q", "quit"}:
            raise CadSelectionCancelled("CAD menu selection cancelled")
        if not choice.isdigit() or not 1 <= int(choice) <= len(entries):
            stdout.write("Invalid selection.\n")
            continue
        kind, name = entries[int(choice) - 1]
        if kind == "product":
            return CadSelection(product=name)
        selected = _model_set_menu(system, name, stdin, stdout)
        if selected is not None:
            return selected


def _generate(
    args: argparse.Namespace,
    context: RuntimeContext,
    deps: Mapping[str, CadFunction],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    selection: CadSelection | None = None,
    selected_system: CadSystem | None = None,
) -> int:
    if selection is not None:
        overlays = _selection(args)
        selection = CadSelection(
            product=selection.product, model=selection.model,
            sets=selection.sets, all_sets=selection.all_sets,
            defines=overlays.defines, set_defines=overlays.set_defines,
            raw_defines=overlays.raw_defines,
        )
    system, plan, snapshots = _prepare_system_plan(
        args, context, deps, stdin, stdout, selection, selected_system=selected_system
    )
    stream = stderr if args.json else stdout
    try:
        regenerate = bool(getattr(args, "regenerate", False))
        resolved_openscad = deps["resolve_openscad"](
            getattr(args, "openscad", None)
        )
        while True:
            try:
                result = deps["generate"](
                    plan,
                    repo_root=context.root,
                    data_dir=context.data_dir,
                    models=system.models,
                    snapshots=snapshots,
                    output=_generation_output(args),
                    openscad=resolved_openscad,
                    revision=_generation_revision(args),
                    stdout=stream,
                    stderr=stderr,
                    regenerate=regenerate,
                )
                break
            except CadRunExistsError as error:
                guidance = f"{error}; rerun with --regenerate"
                interactive = (
                    not args.json
                    and bool(getattr(stdin, "isatty", lambda: False)())
                )
                if regenerate or not interactive:
                    raise CadOperationError(guidance) from None
                stdout.write(
                    "WARNING: matching CAD run already exists: "
                    f"{error.existing_run_dir}\n"
                )
                stdout.write("Regenerate existing run? [y/N] ")
                stdout.flush()
                answer = stdin.readline().strip().lower()
                if answer not in {"y", "yes"}:
                    raise CadOperationError(guidance) from None
                regenerate = True
        manifest, status = _generation_manifest(result, deps)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        raise CadOperationError(str(error) or type(error).__name__) from None
    finally:
        for snapshot in snapshots.values():
            if snapshot.cleanup_root is not None:
                shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)
    if args.json:
        _json_line(stdout, manifest)
    else:
        stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0 if status == "complete" else 4


def run_cad_command(
    args: argparse.Namespace,
    context: RuntimeContext,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    dependencies: Mapping[str, CadFunction] | None = None,
) -> int:
    """Execute one parsed CAD command and return its process exit code."""

    deps = _dependencies(dependencies)
    try:
        if args.action == "systems":
            _emit_rows(_system_rows(context, deps), args.json, stdout)
            return 0

        if args.action in {"models", "sets", "products", "profiles", "libraries"}:
            if (
                args.action == "models"
                and getattr(args, "system", None) is None
                and _interactive(stdin, args)
            ):
                return _catalog_browser(context, stdin, stdout, deps)
            system = _selected_system(args, context, stdin, stdout, deps)
            rows = _catalog_rows(
                args.action, system, context, getattr(args, "model", None)
            )
            _emit_rows(rows, args.json, stdout)
            return 0

        if args.action == "templates":
            rows = []
            for item in deps["discover_templates"](context.root):
                path = _relative(item.path, context.root)
                rows.append({
                    "kind": "template", "id": item.name,
                    "description": _described(item.description), "status": "valid",
                    "diagnostics": [], "path": path,
                    "files": [path, _relative(item.sidecar_path, context.root)],
                })
            _emit_rows(rows, args.json, stdout)
            return 0

        if args.action == "new":
            if args.model is None:
                raise ValueError("cad new requires MODEL")
            system = _selected_system(args, context, stdin, stdout, deps)
            if args.template is not None:
                template = args.template
            elif _interactive(stdin, args):
                template = _choose_template(
                    tuple(deps["discover_templates"](context.root)), stdin, stdout
                )
            else:
                template = "cad"
            created = deps["create_model"](
                context.root, system, args.model, template
            )
            value = {
                "model": created.model_id,
                "system": system.name,
                "template": created.template,
                "directory": created.directory.relative_to(context.root).as_posix(),
                "scad_path": created.scad_path.relative_to(context.root).as_posix(),
                "sidecar_path": created.sidecar_path.relative_to(context.root).as_posix(),
                "metadata_valid": True,
            }
            if args.json:
                _json_line(stdout, value)
            else:
                stdout.write(f"{value['scad_path']}\n{value['sidecar_path']}\n")
                stdout.write(
                    f"plamp cad sets {created.model_id} --system {system.name}\n"
                )
            return 0

        if args.action == "menu" and args.json:
            raise ValueError("cad menu does not support --json")
        if args.action == "views":
            raise ValueError("cad views was removed; use `plamp cad sets MODEL`")
        if args.action == "validate":
            system = _selected_system(args, context, stdin, stdout, deps)
            if args.model is not None and args.model not in system.models:
                raise ValueError(f"Unknown model {args.model!r}")
            value = {
                "valid": True, "system": system.name,
                "system_path": _relative(system.path, context.root),
                "models": [args.model] if args.model is not None else list(system.models),
            }
            _json_line(stdout, value) if args.json else stdout.write(
                f"valid: system {system.name} ({len(value['models'])} model(s))\n"
            )
            return 0

        if args.action == "plan":
            system, plan, snapshots = _prepare_system_plan(
                args, context, deps, stdin, stdout, allow_dirty=True
            )
            try:
                value = plan_as_dict(plan)
                value["job_count"] = len(plan.jobs)
                if args.json:
                    _json_line(stdout, value)
                else:
                    selected = (f"product {plan.selection.product}" if plan.selection.product
                                else f"model {plan.selection.model or plan.jobs[0].model_id}")
                    stdout.write(f"Selected {selected}\n{len(plan.jobs)} render job(s)\nJobs:\n")
                    for job in value["jobs"]:
                        stdout.write(f"- {job['model_id']} / {job['set_name'] or '(default)'}\n")
                        stdout.write(f"  artifact: {job['artifact_id']}\n  fingerprint (SHA-256): {job['fingerprint']}\n")
            finally:
                for snapshot in snapshots.values():
                    if snapshot.cleanup_root is not None:
                        shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)
            return 0

        if args.action == "menu":
            system = _selected_system(args, context, stdin, stdout, deps)
            selected = _product_or_set_menu(system, stdin, stdout, args.model)
            return _generate(
                args, context, deps, stdin, stdout, stderr, selected, system
            )

        if args.action == "generate":
            return _generate(args, context, deps, stdin, stdout, stderr)

        if args.action == "runs":
            value = deps["list_runs"](context.data_dir, args.part)
            if args.json:
                _json_line(stdout, value)
            else:
                for run in value:
                    system_name = run.get("system_name")
                    if not system_name and isinstance(run.get("system"), Mapping):
                        system_name = run["system"].get("name")  # type: ignore[index]
                    stdout.write(
                        f"{run.get('created_at', '?')} {run.get('run_id', '?')} "
                        f"{system_name or '?'} {run.get('status', '?')}\n"
                    )
            return 0

        run, manifest = _load_exact_run(args.run, context.data_dir, deps)
        if args.action == "show":
            if args.json:
                _json_line(stdout, manifest)
            else:
                stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            return 0

        value = deps["load_job_log"](run, args.artifact)
        _json_line(stdout, value) if args.json else stdout.write(value)
        return 0
    except CadSelectionCancelled as error:
        diagnostic = _diagnostic(
            error,
            str(getattr(args, "part", "cad")),
            code="CAD200",
            kind="cancelled",
        )
        _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
        return 2
    except KeyboardInterrupt:
        diagnostic = _diagnostic(
            RuntimeError("CAD generation interrupted"),
            str(getattr(args, "part", "cad")),
            code="CAD400",
            kind="interrupted",
        )
        _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
        return 4
    except (CadMetadataError, CadCatalogMetadataError) as error:
        _emit_diagnostics(error.diagnostics, args.json, stdout, stderr)
        return 2
    except (CadSelectionError, ValueError, TypeError) as error:
        archive_action = args.action in {"runs", "show", "log"}
        code = "CAD400" if archive_action else "CAD200"
        kind = "operation_failed" if archive_action else "invalid_selection"
        diagnostic = _diagnostic(
            error,
            str(getattr(args, "part", getattr(args, "run", "cad"))),
            code=code,
            kind=kind,
        )
        _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
        return 4 if archive_action else 2
    except (OSError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        if args.action == "new" and isinstance(error, CadDestinationExistsError):
            diagnostic = _diagnostic(
                error,
                str(getattr(args, "part", "cad")),
                code="CAD200",
                kind="invalid_selection",
            )
            _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
            return 2
        diagnostic = _diagnostic(
            error,
            str(getattr(args, "part", getattr(args, "run", "cad"))),
            code="CAD400",
            kind="operation_failed",
        )
        _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
        return 4
