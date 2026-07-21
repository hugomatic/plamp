"""Human-facing command boundary for the local CAD engine."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
from collections.abc import Callable, Mapping
from typing import Any, TextIO

from plamp.cad_generation import (
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
from plamp.context import RuntimeContext


CadFunction = Callable[..., Any]


class CadOperationError(RuntimeError):
    """An expected failure after CAD generation or archive access began."""


def _selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", action="append", metavar="NAME")
    parser.add_argument("--view", action="append", default=[], metavar="NAME")
    parser.add_argument("--define", action="append", default=[], metavar="NAME=EXPR")
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
    generate.add_argument("--output", type=Path)
    generate.add_argument("--openscad", default="openscad")
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
    }
    if overrides:
        values.update(overrides)
    return values


def _json_line(stream: TextIO, value: object) -> None:
    stream.write(json.dumps(value, sort_keys=True) + "\n")


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
    return Selection(
        preset=base.preset,
        views=base.views,
        raw_defines=tuple(getattr(args, "define", []) or []),
        raw_view_defines=raw_view_defines,
    )


def _with_plan(
    args: argparse.Namespace,
    context: RuntimeContext,
    deps: Mapping[str, CadFunction],
    selection: Selection | None = None,
    *,
    allow_dirty: bool = False,
) -> tuple[Path, Any, Any]:
    source = deps["resolve_part"](args.part, context.root)
    revision = getattr(args, "revision", None)
    if allow_dirty and revision is None:
        revision = "working-tree-plan"
    snapshot = deps["prepare_source"](context.root, source, revision)
    try:
        document = deps["parse_document"](snapshot.scad_path)
        selected = _selection(args, document, menu=selection)
        plan = deps["build_plan"](document, selected, snapshot.source_identity)
        return source, document, plan
    finally:
        if snapshot.cleanup_root is not None:
            shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)


def _plan_object(
    plan: Any, document: Any, archived_runs: list[Mapping[str, object]]
) -> dict[str, object]:
    value = plan_as_dict(plan)
    value["job_count"] = len(plan.jobs)
    value["shared_job_count"] = sum(1 for job in plan.jobs if len(job.preset_paths) > 1)
    comparable: dict[str, dict[str, object]] = {}
    for run in archived_runs:
        jobs = run.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, Mapping) or job.get("status") != "complete":
                continue
            fingerprint = job.get("fingerprint")
            if not isinstance(fingerprint, str) or fingerprint in comparable:
                continue
            estimate = {
                key: job[key]
                for key in ("elapsed_seconds", "artifact_bytes")
                if job.get(key) is not None
            }
            if estimate:
                comparable[fingerprint] = estimate
    for job in value["jobs"]:  # type: ignore[assignment]
        view = job["view"]
        job["description"] = (
            document.view_metadata[view].description
            if view in document.view_metadata
            else ""
        )
        job["estimate"] = comparable.get(job["fingerprint"])
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


def _resolve_run_argument(value: str, data_dir: Path) -> Path | str:
    supplied = Path(value)
    if supplied.exists() or supplied.parent != Path("."):
        return supplied
    matches = list((data_dir / "cad" / "prints").glob(f"*/{value}"))
    if len(matches) == 1:
        return matches[0]
    return value


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
        tokens = stdin.readline().split()
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
    source, document, plan = _with_plan(args, context, deps, selection)
    stream = stderr if args.json else stdout
    try:
        result = deps["generate"](
            plan,
            repo_root=context.root,
            data_dir=context.data_dir,
            scad_path=source,
            output=getattr(args, "output", None),
            openscad=getattr(args, "openscad", "openscad"),
            revision=getattr(args, "revision", None),
            metadata=document.metadata_snapshot,
            stdout=stream,
            stderr=stderr,
        )
        manifest, status = _generation_manifest(result, deps)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        raise CadOperationError(str(error) or type(error).__name__) from None
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
            source, document, plan = _with_plan(args, context, deps, allow_dirty=True)
            archived_runs = deps["list_runs"](context.data_dir, source.parent.name)
            value = _plan_object(plan, document, archived_runs)
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

        run = _resolve_run_argument(args.run, context.data_dir)
        if args.action == "show":
            value = deps["load_run"](run)
            if args.json:
                _json_line(stdout, value)
            else:
                stdout.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            return 0

        value = deps["load_job_log"](run, args.artifact)
        _json_line(stdout, value) if args.json else stdout.write(value)
        return 0
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
    except (ValueError, TypeError) as error:
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
        diagnostic = _diagnostic(
            error,
            str(getattr(args, "part", getattr(args, "run", "cad"))),
            code="CAD400",
            kind="operation_failed",
        )
        _emit_diagnostics((diagnostic,), args.json, stdout, stderr)
        return 4
