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
    GENERATOR_VERSION,
    GenerationResult,
    generate_plan,
    list_runs,
    load_job_log,
    load_run,
    prepare_source,
    resolve_part,
)
from plamp.cad_metadata import CadDiagnostic, CadMetadataError, parse_cad_document
from plamp.cad_recipes import Selection, build_render_plan, plan_as_dict
from plamp.cad_scaffold import (
    CadDestinationExistsError,
    CadSelectionError,
    create_part,
    discover_templates,
)
from plamp.context import RuntimeContext


CadFunction = Callable[..., Any]


class CadOperationError(RuntimeError):
    """An expected failure after CAD generation or archive access began."""


class CadSelectionCancelled(ValueError):
    """Interactive CAD selection ended without a choice."""


def _selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", action="append", metavar="NAME")
    parser.add_argument("--view", action="append", default=[], metavar="NAME")
    parser.add_argument(
        "--define", "-D", action="append", default=[], metavar="NAME=EXPR"
    )
    parser.add_argument(
        "--view-define", action="append", default=[], metavar="VIEW:NAME=EXPR"
    )
    parser.add_argument("--revision", help="revision label or committed revision")


def add_cad_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the local ``cad`` command group to an argparse subparser set."""

    cad = subparsers.add_parser("cad", help="inspect and generate local CAD parts")
    actions = cad.add_subparsers(dest="action", required=True)

    new = actions.add_parser("new")
    new.add_argument("part", nargs="?")
    new.add_argument("--template")
    new.add_argument("--list-templates", action="store_true")
    new.add_argument("--json", action="store_true")

    for action in ("views", "validate"):
        command = actions.add_parser(action)
        command.add_argument("part")
        command.add_argument("--json", action="store_true")

    plan = actions.add_parser("plan")
    plan.add_argument("part")
    _selection_arguments(plan)
    plan.add_argument("--json", action="store_true")

    menu = actions.add_parser("menu")
    menu.add_argument("part")
    menu.add_argument("--define", action="append", default=[], metavar="NAME=EXPR")
    menu.add_argument(
        "--view-define", action="append", default=[], metavar="VIEW:NAME=EXPR"
    )
    menu.add_argument("--revision")
    menu.add_argument("--output", type=Path)
    menu.add_argument("--openscad", default="openscad")
    menu.add_argument("--json", action="store_true")

    generate = actions.add_parser("generate")
    generate.add_argument("part")
    _selection_arguments(generate)
    generate.add_argument(
        "--preview",
        action="store_true",
        help="disable rendered text and use render_fn=24",
    )
    generate.add_argument("--output", type=Path)
    generate.add_argument("--openscad", default="openscad")
    generate.add_argument("--json", action="store_true")
    generate.add_argument("legacy_output", nargs="?", metavar="target_directory")
    generate.add_argument("legacy_commit", nargs="?", metavar="commit")
    generate.add_argument(
        "--legacy-output", dest="legacy_output", type=Path, help=argparse.SUPPRESS
    )
    generate.add_argument(
        "--legacy-commit", dest="legacy_commit", help=argparse.SUPPRESS
    )

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


def _dependencies(overrides: Mapping[str, CadFunction] | None) -> dict[str, CadFunction]:
    values: dict[str, CadFunction] = {
        "resolve_part": resolve_part,
        "parse_document": parse_cad_document,
        "prepare_source": prepare_source,
        "build_plan": build_render_plan,
        "generate": generate_plan,
        "list_runs": list_runs,
        "load_run": load_run,
        "load_job_log": load_job_log,
        "discover_templates": discover_templates,
        "create_part": create_part,
    }
    if overrides:
        values.update(overrides)
    return values


def _json_line(stream: TextIO, value: object) -> None:
    stream.write(json.dumps(value, sort_keys=True) + "\n")


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


def _raw_view_defines(values: list[str]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for value in values:
        if ":" not in value:
            raise ValueError("--view-define requires VIEW:NAME=EXPR")
        view, expression = value.split(":", 1)
        if not view or "=" not in expression or not expression.split("=", 1)[0]:
            raise ValueError("--view-define requires VIEW:NAME=EXPR")
        grouped.setdefault(view, []).append(expression)
    return {view: tuple(expressions) for view, expressions in grouped.items()}


def _selection(
    args: argparse.Namespace, document: Any, *, menu: Selection | None = None
) -> Selection:
    preset_values = list(getattr(args, "preset", None) or [])
    if len(preset_values) > 1:
        raise ValueError("exactly one --preset may be selected")
    raw_view_defines = _raw_view_defines(list(getattr(args, "view_define", []) or []))
    unknown = [view for view in raw_view_defines if view not in document.views]
    if unknown:
        raise ValueError(f"Unknown --view-define view: {unknown[0]}")
    base = menu or Selection(
        preset=preset_values[0] if preset_values else None,
        views=tuple(getattr(args, "view", []) or []),
    )
    raw_defines = []
    if getattr(args, "preview", False):
        raw_defines.extend(("render_text=false", "render_fn=24"))
    raw_defines.extend(getattr(args, "define", []) or [])
    return Selection(
        preset=base.preset,
        views=base.views,
        raw_defines=tuple(raw_defines),
        raw_view_defines=raw_view_defines,
    )


def _generation_revision(args: argparse.Namespace) -> str | None:
    revision = getattr(args, "revision", None)
    legacy_commit = getattr(args, "legacy_commit", None)
    if revision is not None and legacy_commit is not None:
        raise ValueError("commit positional argument cannot be combined with --revision")
    return legacy_commit if legacy_commit is not None else revision


def _generation_output(args: argparse.Namespace) -> Path | None:
    output = getattr(args, "output", None)
    legacy_output = getattr(args, "legacy_output", None)
    if output is not None and legacy_output is not None:
        raise ValueError("target_directory positional argument cannot be combined with --output")
    return Path(legacy_output) if legacy_output is not None else output


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
    legacy_commit = getattr(args, "legacy_commit", None)
    if (
        getattr(args, "action", None) == "generate"
        and legacy_commit is not None
        and getattr(args, "revision", None) is None
    ):
        probe = deps["prepare_source"](context.root, source, None)
        if probe.cleanup_root is not None:
            shutil.rmtree(probe.cleanup_root, ignore_errors=True)
    revision = (
        _generation_revision(args)
        if getattr(args, "action", None) == "generate"
        else getattr(args, "revision", None)
    )
    if allow_dirty and revision is None:
        revision = "working-tree-plan"
    snapshot = deps["prepare_source"](context.root, source, revision)
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


def _generate(
    args: argparse.Namespace,
    context: RuntimeContext,
    deps: Mapping[str, CadFunction],
    stdout: TextIO,
    stderr: TextIO,
    selection: Selection | None = None,
) -> int:
    source, document, plan, snapshot = _with_plan(
        args, context, deps, selection, retain_snapshot=True
    )
    stream = stderr if args.json else stdout
    try:
        result = deps["generate"](
            plan,
            repo_root=context.root,
            data_dir=context.data_dir,
            scad_path=source,
            output=_generation_output(args),
            openscad=getattr(args, "openscad", "openscad"),
            revision=_generation_revision(args),
            metadata=document.metadata_snapshot,
            stdout=stream,
            stderr=stderr,
            snapshot=snapshot,
        )
        manifest, status = _generation_manifest(result, deps)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        raise CadOperationError(str(error) or type(error).__name__) from None
    finally:
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
        if args.action == "new":
            if args.list_templates:
                if args.part is not None or args.template is not None:
                    raise ValueError(
                        "--list-templates cannot be combined with PART or --template"
                    )
                templates = deps["discover_templates"](context.root)
                value = {
                    "templates": [
                        {
                            "name": item.name,
                            "path": item.path.relative_to(context.root).as_posix(),
                        }
                        for item in templates
                    ]
                }
                if args.json:
                    _json_line(stdout, value)
                else:
                    for item in value["templates"]:
                        stdout.write(f"{item['name']} {item['path']}\n")
                return 0
            if args.part is None:
                raise ValueError("cad new requires PART unless --list-templates is used")
            template = args.template or "cad"
            created = deps["create_part"](context.root, args.part, template)
            value = {
                "part": created.part,
                "template": created.template,
                "directory": created.directory.relative_to(context.root).as_posix(),
                "scad_path": created.scad_path.relative_to(context.root).as_posix(),
                "metadata_valid": True,
            }
            if args.json:
                _json_line(stdout, value)
            else:
                stdout.write(f"{value['scad_path']}\n")
                stdout.write(f"plamp cad validate {created.part} --json\n")
            return 0

        if args.action == "menu" and args.json:
            raise ValueError("cad menu does not support --json")
        if args.action in {"views", "validate"}:
            source = deps["resolve_part"](args.part, context.root)
            document = deps["parse_document"](source)
            if args.action == "views":
                value = _catalog(document, source)
                if args.json:
                    _json_line(stdout, value)
                else:
                    for preset in value["presets"]:  # type: ignore[assignment]
                        stdout.write(f"preset {preset['name']}: {preset['description']}\n")
                    for view in value["views"]:  # type: ignore[assignment]
                        stdout.write(f"view {view['name']}: {view['description']}\n")
            else:
                value = {"valid": True, **_catalog(document, source)}
                if args.json:
                    _json_line(stdout, value)
                else:
                    stdout.write(f"valid: {source}\n")
            return 0

        if args.action == "plan":
            source, document, plan, _snapshot = _with_plan(args, context, deps, allow_dirty=True)
            archived_runs = deps["list_runs"](context.data_dir, source.parent.name)
            source_path = source.relative_to(context.root).as_posix()
            value = _plan_object(plan, document, archived_runs, source_path)
            _json_line(stdout, value) if args.json else _print_plan(value, stdout)
            return 0

        if args.action == "menu":
            source = deps["resolve_part"](args.part, context.root)
            document = deps["parse_document"](source)
            selected = _menu_selection(document, stdin, stderr if args.json else stdout)
            return _generate(args, context, deps, stdout, stderr, selected)

        if args.action == "generate":
            return _generate(args, context, deps, stdout, stderr)

        if args.action == "runs":
            value = deps["list_runs"](context.data_dir, args.part)
            if args.json:
                _json_line(stdout, value)
            else:
                for run in value:
                    stdout.write(
                        f"{run.get('created_at', '?')} {run.get('run_id', '?')} "
                        f"{run.get('part', '?')} {run.get('status', '?')}\n"
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
    except CadMetadataError as error:
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
