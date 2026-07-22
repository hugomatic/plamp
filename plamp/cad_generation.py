"""Execute CAD render plans into reproducible, instance-local archives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import IO, Callable

from plamp.cad_recipes import RenderJob, RenderPlan, plan_as_dict, serialize_scad_value


MANIFEST_SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class SourceSnapshot:
    scad_path: Path
    source_identity: str
    full_commit: str | None
    revision_label: str
    dirty: bool
    cleanup_root: Path | None


@dataclass(frozen=True)
class GenerationResult:
    run_dir: Path
    manifest_path: Path
    status: str


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def resolve_part(part: str | os.PathLike[str], repo_root: str | os.PathLike[str]) -> Path:
    """Resolve a part name or repository-relative SCAD path."""

    root = Path(repo_root).resolve()
    supplied = Path(part)
    candidates = [supplied if supplied.is_absolute() else root / supplied]
    if len(supplied.parts) == 1 and supplied.suffix != ".scad":
        candidates.insert(0, root / "things" / str(supplied) / f"{supplied}.scad")
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.suffix == ".scad":
            try:
                resolved.relative_to(root)
            except ValueError as error:
                raise ValueError("CAD source must be inside the repository") from error
            return resolved
    raise FileNotFoundError(f"CAD part not found: {part}")


def _is_executable(path: str | os.PathLike[str]) -> bool:
    candidate = Path(path)
    return candidate.is_file() and os.access(candidate, os.X_OK)


def _selected_executable(
    value: str, *, which: Callable[[str], str | None]
) -> Path | None:
    if os.sep in value or (os.altsep is not None and os.altsep in value):
        candidate = Path(value).expanduser()
        return candidate.resolve() if _is_executable(candidate) else None
    located = which(value)
    if located is None:
        return None
    candidate = Path(located)
    return candidate if _is_executable(candidate) else None


def resolve_openscad(
    explicit: str | os.PathLike[str] | None,
    *,
    env: Mapping[str, str] = os.environ,
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    home: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve OpenSCAD using explicit, environment, PATH, then platform paths."""

    def locate(command: str) -> str | None:
        if which is shutil.which:
            return shutil.which(command, path=env.get("PATH"))
        return which(command)

    if explicit is not None:
        value = os.fspath(explicit)
        candidate = _selected_executable(value, which=locate) if value else None
        if candidate is None:
            raise FileNotFoundError(
                f"OpenSCAD selected by --openscad is not executable: {value!r}"
            )
        return candidate

    if "OPENSCAD_BIN" in env:
        value = env["OPENSCAD_BIN"]
        candidate = _selected_executable(value, which=locate) if value else None
        if candidate is None:
            raise FileNotFoundError(
                f"OpenSCAD selected by OPENSCAD_BIN is not executable: {value!r}"
            )
        return candidate

    located = locate("openscad")
    if located is not None and _is_executable(located):
        return Path(located)

    user_home = Path(home) if home is not None else Path.home()
    platform_name = system if system is not None else platform.system()
    if platform_name == "Darwin":
        fallbacks = (
            Path("/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"),
            user_home / "Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
        )
    elif platform_name == "Linux":
        fallbacks = (
            Path("/usr/bin/openscad"),
            Path("/usr/local/bin/openscad"),
            Path("/snap/bin/openscad"),
            Path("/var/lib/flatpak/exports/bin/org.openscad.OpenSCAD"),
            user_home / ".local/share/flatpak/exports/bin/org.openscad.OpenSCAD",
        )
    else:
        fallbacks = ()
    for candidate in fallbacks:
        if _is_executable(candidate):
            return candidate
    raise FileNotFoundError(
        "OpenSCAD executable not found; use --openscad or set OPENSCAD_BIN"
    )


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_snapshot_links(root: Path, *, context: str) -> None:
    boundary = root.resolve()
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            path.resolve(strict=True).relative_to(boundary)
        except (OSError, ValueError) as error:
            raise ValueError(f"unsafe symlink in {context}: {path}") from error


def prepare_source(
    repo_root: str | os.PathLike[str],
    scad_path: str | os.PathLike[str],
    revision: str | None = None,
    *,
    revision_is_commit: bool = False,
) -> SourceSnapshot:
    """Return an archived clean part, or an explicitly labelled dirty source."""

    root = Path(repo_root).resolve()
    source = resolve_part(scad_path, root)
    relative = source.relative_to(root)
    part_relative = relative.parent
    dirty = bool(_git(root, "status", "--porcelain", "--", str(part_relative)))
    if dirty:
        if revision is None or not revision.strip():
            raise ValueError("dirty CAD part requires an explicit revision label")
        cleanup = Path(tempfile.mkdtemp(prefix="plamp-cad-source-"))
        try:
            _validate_snapshot_links(source.parent, context="dirty CAD source")
            archived_part = cleanup / part_relative
            archived_part.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source.parent, archived_part, symlinks=True)
            archived_source = cleanup / relative
            return SourceSnapshot(
                archived_source,
                _hash_tree(archived_part),
                None,
                revision.strip(),
                True,
                cleanup,
            )
        except BaseException:
            shutil.rmtree(cleanup, ignore_errors=True)
            raise

    commit = _git(root, "log", "-1", "--format=%H", "--", str(part_relative))
    if not commit:
        raise ValueError("CAD part has no committed source revision")
    selected_commit = commit
    revision_label = commit[:7]
    if revision is not None and revision.strip():
        requested_revision = revision.strip()
        revision_label = requested_revision
        try:
            selected_commit = _git(
                root, "rev-parse", "--verify", f"{requested_revision}^{{commit}}"
            )
        except subprocess.CalledProcessError:
            if revision_is_commit:
                raise ValueError(f"invalid committed CAD revision: {requested_revision}") from None
            # Non-Git labels remain valid for explicitly labelled clean renders.
            selected_commit = commit
        if revision_is_commit:
            revision_label = _git(root, "rev-parse", "--short", selected_commit)
    cleanup = Path(tempfile.mkdtemp(prefix="plamp-cad-source-"))
    try:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", selected_commit, str(part_relative)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        with tempfile.TemporaryFile() as stream:
            stream.write(archive)
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode="r:") as bundle:
                for member in bundle.getmembers():
                    member_path = Path(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ValueError("unsafe path in Git source archive")
                    is_part_entry = member_path == part_relative
                    is_descendant = part_relative in member_path.parents
                    is_ancestor = member_path in part_relative.parents
                    if not (is_part_entry or is_descendant or is_ancestor):
                        raise ValueError("unsafe path in Git source archive")
                    if member.issym():
                        link_target = Path(member.linkname)
                        target = link_target if link_target.is_absolute() else member_path.parent / link_target
                        if link_target.is_absolute() or ".." in target.parts:
                            raise ValueError("unsafe symlink in Git source archive")
                        try:
                            target.relative_to(part_relative)
                        except ValueError as error:
                            raise ValueError("unsafe symlink in Git source archive") from error
                    elif member.islnk():
                        raise ValueError("unsafe hard link in Git source archive")
                bundle.extractall(cleanup)
        _validate_snapshot_links(cleanup / part_relative, context="Git source archive")
        archived_scad = cleanup / relative
        return SourceSnapshot(
            archived_scad,
            selected_commit,
            selected_commit,
            revision_label,
            False,
            cleanup,
        )
    except BaseException:
        shutil.rmtree(cleanup, ignore_errors=True)
        raise


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_manifest(run_dir: Path, manifest: dict[str, object]) -> None:
    manifest["updated_at"] = _timestamp(_utc_now())
    _atomic_text(
        run_dir / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def _write_readme(run_dir: Path, manifest: Mapping[str, object]) -> None:
    lines = [
        f"# CAD run {manifest['run_id']}",
        "",
        f"Status: {manifest['status']}",
        "",
        "| Artifact | View | Status |",
        "| --- | --- | --- |",
    ]
    jobs = manifest.get("jobs", [])
    assert isinstance(jobs, list)
    for job in jobs:
        assert isinstance(job, Mapping)
        lines.append(f"| {job['artifact_id']} | {job['view'] or 'default'} | {job['status']} |")
    _atomic_text(run_dir / "readme.md", "\n".join(lines) + "\n")


def _best_effort_readme(run_dir: Path, manifest: Mapping[str, object]) -> None:
    try:
        _write_readme(run_dir, manifest)
    except OSError:
        pass


def _geometry() -> dict[str, object]:
    return {
        "render_seconds": None,
        "simple": None,
        "vertices": None,
        "facets": None,
        "volumes": None,
    }


def _job_entry(job: RenderJob, queued_at: str, log: str) -> dict[str, object]:
    return {
        "artifact_id": job.artifact_id,
        "fingerprint": job.fingerprint,
        "view": job.view,
        "variant_name": job.variant_name,
        "preset_paths": [list(path) for path in job.preset_paths],
        "variables": _plain(job.variables),
        "raw_defines": dict(job.raw_defines),
        "status": "queued",
        "queued_at": queued_at,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "command": [],
        "artifact": None,
        "artifact_bytes": None,
        "log": log,
        "exit_code": None,
        "echoes": [],
        "messages": [],
        "warnings": [],
        "errors": [],
        "geometry": _geometry(),
    }


def _duration_seconds(text: str) -> float | None:
    match = re.search(r"(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _capture_line(job: dict[str, object], line: str) -> None:
    stripped = line.rstrip("\r\n")
    echoes = job["echoes"]
    messages = job["messages"]
    warnings = job["warnings"]
    errors = job["errors"]
    geometry = job["geometry"]
    assert isinstance(echoes, list) and isinstance(messages, list)
    assert isinstance(warnings, list) and isinstance(errors, list)
    assert isinstance(geometry, dict)
    if stripped.startswith("ECHO:"):
        payload = stripped.split(":", 1)[1].strip()
        echoes.append(payload)
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            try:
                decoded = json.loads(f"[{payload}]")
            except (json.JSONDecodeError, TypeError):
                decoded = None
        if (
            isinstance(decoded, list)
            and len(decoded) >= 3
            and decoded[0] == "PLAMP"
            and isinstance(decoded[1], str)
        ):
            messages.append({"channel": decoded[1], "payload": decoded[2]})
    if "WARNING:" in stripped:
        warnings.append(stripped)
    if "ERROR:" in stripped:
        errors.append(stripped)
    if "Total rendering time:" in stripped:
        geometry["render_seconds"] = _duration_seconds(stripped)
    match = re.search(r"\bSimple:\s*(yes|no)\b", stripped, re.IGNORECASE)
    if match:
        geometry["simple"] = match.group(1).lower() == "yes"
    for label, key in (("Vertices", "vertices"), ("Facets", "facets"), ("Volumes", "volumes")):
        match = re.search(rf"\b{label}:\s*(\d+)\b", stripped, re.IGNORECASE)
        if match:
            geometry[key] = int(match.group(1))


def _command(
    openscad: Path,
    output: Path,
    source: Path,
    revision: str,
    job: RenderJob,
) -> list[str]:
    command = [str(openscad), "-o", str(output), "-D", f"revision_string={serialize_scad_value(revision)}"]
    if job.view is not None:
        command.extend(["-D", f"view={serialize_scad_value(job.view)}"])
    for name, value in job.variables.items():
        command.extend(["-D", f"{name}={serialize_scad_value(value)}"])
    for name, expression in job.raw_defines.items():
        command.extend(["-D", f"{name}={expression}"])
    command.extend(["--export-format", "asciistl", str(source)])
    return command


def _safe_component(value: str) -> str:
    return _SAFE_COMPONENT.sub("-", value).strip("-.") or "run"


def _error_text(error: BaseException) -> str:
    return str(error) or type(error).__name__


def _remove_temporary_artifact(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _finalize_job_failure(
    job: dict[str, object],
    *,
    started_clock: float,
    error: BaseException,
    process: subprocess.Popen[str] | None,
    temporary_artifact: Path,
) -> None:
    job["status"] = "failed"
    job["exit_code"] = None if process is None else process.returncode
    job["finished_at"] = _timestamp(_utc_now())
    job["elapsed_seconds"] = round(time.monotonic() - started_clock, 6)
    errors = job["errors"]
    assert isinstance(errors, list)
    errors.append(_error_text(error))
    _remove_temporary_artifact(temporary_artifact)


def _copy_snapshot(snapshot: SourceSnapshot, repo_root: Path, run_dir: Path) -> Path:
    relative = snapshot.scad_path.relative_to(snapshot.cleanup_root or repo_root)
    target = run_dir / "source" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshot.scad_path.parent, target.parent, dirs_exist_ok=True)
    return target


def generate_plan(
    plan: RenderPlan,
    *,
    repo_root: str | os.PathLike[str],
    data_dir: str | os.PathLike[str],
    scad_path: str | os.PathLike[str],
    output: str | os.PathLike[str] | None = None,
    openscad: str | os.PathLike[str] = "openscad",
    revision: str | None = None,
    metadata: Mapping[str, object] | None = None,
    env: Mapping[str, str] | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
    snapshot: SourceSnapshot | None = None,
) -> GenerationResult:
    """Render a plan sequentially and persist every observable state change."""

    root = Path(repo_root).resolve()
    source = resolve_part(scad_path, root)
    part = source.parent.name
    snapshot = snapshot or prepare_source(root, source, revision)
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        version_result = subprocess.run(
            [str(openscad), "--version"], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=dict(env) if env is not None else None,
        )
        if version_result.returncode != 0:
            raise RuntimeError(version_result.stdout.strip() or "OpenSCAD version check failed")
        openscad_version = version_result.stdout.strip()
        now = _utc_now()
        selector = plan.selection.preset or (plan.jobs[0].variant_name if len(plan.jobs) == 1 else "views")
        token = secrets.token_hex(3)
        run_id = "-".join((
            now.strftime("%Y%m%dT%H%M%SZ"), _safe_component(part),
            _safe_component(selector), _safe_component(snapshot.revision_label), token,
        ))
        run_dir = Path(output).resolve() if output is not None else Path(data_dir).resolve() / "cad" / "prints" / part / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "artifacts").mkdir()
        (run_dir / "logs").mkdir()
        archived_source = _copy_snapshot(snapshot, root, run_dir)
        content_hash = _hash_tree(archived_source.parent)
        plan_data = plan_as_dict(plan)
        created = _timestamp(now)
        jobs = [
            _job_entry(job, created, f"logs/{job.artifact_id}.log")
            for job in plan.jobs
        ]
        manifest: dict[str, object] = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "run_id": run_id,
            "part": part,
            "status": "running",
            "created_at": created,
            "updated_at": created,
            "started_at": created,
            "finished_at": None,
            "source": {
                "repository_root": str(root),
                "scad_path": str(source.relative_to(root)),
                "part_directory": str(source.parent.relative_to(root)),
                "commit": snapshot.full_commit,
                "revision": snapshot.revision_label,
                "content_hash": content_hash,
                "dirty": snapshot.dirty,
            },
            "selection": {
                "preset": plan_data["selection"]["preset"],
                "views": plan_data["selection"]["views"],
                "defines": plan_data["selection"]["defines"],
                "view_defines": plan_data["selection"]["view_defines"],
            },
            "metadata": _plain(metadata or {}),
            "preset_tree": plan_data["preset_tree"],
            "openscad_version": openscad_version,
            "jobs": jobs,
        }
        _write_manifest(run_dir, manifest)
        try:
            _write_readme(run_dir, manifest)
        except OSError as error:
            finished_at = _timestamp(_utc_now())
            manifest["status"] = "failed"
            manifest["finished_at"] = finished_at
            if jobs:
                first_job = jobs[0]
                first_job["status"] = "failed"
                first_job["started_at"] = created
                first_job["finished_at"] = finished_at
                first_job["elapsed_seconds"] = 0.0
                first_errors = first_job["errors"]
                assert isinstance(first_errors, list)
                first_errors.append(_error_text(error))
            _write_manifest(run_dir, manifest)
            return GenerationResult(run_dir, run_dir / "manifest.json", "failed")

        failed = False
        for render_job, job in zip(plan.jobs, jobs):
            started = _utc_now()
            started_clock = time.monotonic()
            job["status"] = "running"
            job["started_at"] = _timestamp(started)
            temporary_artifact = run_dir / "artifacts" / f".{render_job.artifact_id}.tmp.stl"
            final_artifact = run_dir / "artifacts" / f"{render_job.artifact_id}.stl"
            command = _command(Path(openscad), temporary_artifact, archived_source, snapshot.revision_label, render_job)
            job["command"] = command
            _write_manifest(run_dir, manifest)
            log_path = run_dir / str(job["log"])
            process: subprocess.Popen[str] | None = None
            try:
                _write_readme(run_dir, manifest)
                with log_path.open("w", encoding="utf-8") as log:
                    process = subprocess.Popen(
                        command, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, env=dict(env) if env is not None else None,
                    )
                    assert process.stdout is not None
                    with process.stdout:
                        for line in process.stdout:
                            out.write(line)
                            out.flush()
                            log.write(line)
                            log.flush()
                            _capture_line(job, line)
                    exit_code = process.wait()
                job["exit_code"] = exit_code
                finished = _utc_now()
                job["finished_at"] = _timestamp(finished)
                job["elapsed_seconds"] = round(time.monotonic() - started_clock, 6)
                if exit_code == 0 and temporary_artifact.is_file() and temporary_artifact.stat().st_size > 0:
                    os.replace(temporary_artifact, final_artifact)
                    job["status"] = "complete"
                    job["artifact"] = str(final_artifact.relative_to(run_dir))
                    job["artifact_bytes"] = final_artifact.stat().st_size
                else:
                    job["status"] = "failed"
                    failed = True
                    temporary_artifact.unlink(missing_ok=True)
                    errors = job["errors"]
                    assert isinstance(errors, list)
                    if exit_code == 0:
                        errors.append("OpenSCAD did not produce a non-empty output artifact")
                    elif not errors:
                        errors.append(f"OpenSCAD exited with status {exit_code}")
            except KeyboardInterrupt:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait()
                job["status"] = "interrupted"
                job["exit_code"] = None if process is None else process.returncode
                job["finished_at"] = _timestamp(_utc_now())
                job["elapsed_seconds"] = round(time.monotonic() - started_clock, 6)
                manifest["status"] = "interrupted"
                manifest["finished_at"] = job["finished_at"]
                _remove_temporary_artifact(temporary_artifact)
                _write_manifest(run_dir, manifest)
                _best_effort_readme(run_dir, manifest)
                raise
            except Exception as error:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait()
                _finalize_job_failure(
                    job,
                    started_clock=started_clock,
                    error=error,
                    process=process,
                    temporary_artifact=temporary_artifact,
                )
                failed = True
            _write_manifest(run_dir, manifest)
            _best_effort_readme(run_dir, manifest)
            if failed:
                break

        finished_at = _timestamp(_utc_now())
        manifest["status"] = "failed" if failed else "complete"
        manifest["finished_at"] = finished_at
        _write_manifest(run_dir, manifest)
        _best_effort_readme(run_dir, manifest)
        return GenerationResult(run_dir, run_dir / "manifest.json", str(manifest["status"]))
    except OSError as error:
        print(str(error), file=err)
        raise
    finally:
        if snapshot.cleanup_root is not None:
            shutil.rmtree(snapshot.cleanup_root, ignore_errors=True)


def load_run(path: str | os.PathLike[str]) -> dict[str, object]:
    """Load one archived manifest by run directory or manifest path."""

    candidate = Path(path)
    manifest_path = candidate if candidate.name == "manifest.json" else candidate / "manifest.json"
    with manifest_path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict) or value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"Unsupported CAD manifest: {manifest_path}")
    return value


def list_runs(data_dir: str | os.PathLike[str], part: str | None = None) -> list[dict[str, object]]:
    """List instance-data runs newest first."""

    root = Path(data_dir) / "cad" / "prints"
    if part is not None:
        supplied = Path(part)
        if not part or supplied.is_absolute() or supplied.name != part or part in {".", ".."}:
            raise ValueError("CAD part must be a single path component")
    search = root / part if part is not None else root
    manifests = [] if not search.exists() else list(search.glob("*/manifest.json") if part else search.glob("*/*/manifest.json"))
    runs = [load_run(path) for path in manifests]
    return sorted(runs, key=lambda item: (str(item.get("created_at", "")), str(item.get("run_id", ""))), reverse=True)


def load_job_log(run: str | os.PathLike[str], artifact_id: str) -> str:
    """Load the log addressed by an exact manifest artifact ID."""

    run_dir = Path(run).parent if Path(run).name == "manifest.json" else Path(run)
    manifest = load_run(run_dir)
    jobs = manifest.get("jobs")
    assert isinstance(jobs, list)
    for job in jobs:
        if isinstance(job, Mapping) and job.get("artifact_id") == artifact_id:
            expected = Path("logs") / f"{artifact_id}.log"
            recorded = Path(str(job.get("log", "")))
            candidate = (run_dir / recorded).resolve()
            resolved_run = run_dir.resolve()
            try:
                candidate.relative_to(resolved_run)
            except ValueError as error:
                raise ValueError("unsafe CAD job log path") from error
            if recorded != expected:
                raise ValueError("unsafe CAD job log path")
            return candidate.read_text(encoding="utf-8")
    raise KeyError(artifact_id)
