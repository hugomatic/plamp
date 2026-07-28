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
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import secrets
from typing import IO, Callable

from plamp.cad_model import CadModel
from plamp.cad_dependencies import (
    CadLibrary,
    classify_dependencies,
    geometry_define_argv,
    parse_make_dependencies,
    prepare_discovery_environment,
    query_openscad_info,
    run_dependency_discovery,
    stage_dependency_closure,
    verify_staged_dependencies,
)
from plamp.cad_readme import render_run_readme
from plamp.cad_planning import RenderJob, RenderPlan, plan_as_dict


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
    geometry_identity: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    run_dir: Path
    manifest_path: Path
    status: str


class CadRunExistsError(RuntimeError):
    """A managed archive already contains the same local-day generation."""

    def __init__(self, existing_run_id: str, existing_run_dir: Path) -> None:
        self.existing_run_id = existing_run_id
        self.existing_run_dir = existing_run_dir
        super().__init__(
            f"matching CAD run already exists: {existing_run_dir}"
        )


class _ReuseTargetExists(RuntimeError):
    """A destination artifact appeared while verified reuse was publishing."""


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


def _hash_geometry_tree(root: Path) -> str:
    """Hash render inputs while excluding adjacent descriptive sidecars."""

    digest = hashlib.sha256()
    paths = sorted(
        item for item in root.rglob("*")
        if item.is_file() and not item.name.endswith(".cad.json")
    )
    for path in paths:
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
    if dirty and not revision_is_commit:
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
                _hash_geometry_tree(archived_part),
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
            _hash_geometry_tree(cleanup / part_relative),
        )
    except BaseException:
        shutil.rmtree(cleanup, ignore_errors=True)
        raise


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _local_now() -> datetime:
    return datetime.now().astimezone()


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


def _atomic_text_at(directory_fd: int, name: str, text: str) -> None:
    temporary = f".{name}.{secrets.token_hex(8)}"
    fd = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
        0o644, dir_fd=directory_fd,
    )
    try:
        try:
            data = text.encode("utf-8")
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(
            temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd
        )
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _write_manifest(
    run_dir: Path, manifest: dict[str, object], run_fd: int | None = None,
) -> None:
    manifest["updated_at"] = _timestamp(_utc_now())
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if run_fd is None:
        _atomic_text(run_dir / "manifest.json", text)
    else:
        _atomic_text_at(run_fd, "manifest.json", text)


def _write_readme(
    run_dir: Path, manifest: Mapping[str, object], run_fd: int | None = None,
) -> None:
    text = render_run_readme(manifest)
    if run_fd is None:
        _atomic_text(run_dir / "readme.md", text)
    else:
        _atomic_text_at(run_fd, "readme.md", text)


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
        "geometry_fingerprint": job.geometry_fingerprint,
        "manufacturing_fingerprint": job.manufacturing_fingerprint,
        "model": job.model_id,
        "set": job.set_name,
        "variant_name": job.variant_name,
        "product_paths": [list(path) for path in job.product_paths],
        "variables": _plain(job.variables),
        "raw_defines": dict(job.raw_defines),
        "variable_sources": {
            name: {
                "layers": [{
                    "kind": layer.kind,
                    "source_id": layer.source_id,
                    "value": _plain(layer.value),
                    "raw_expression": layer.raw_expression,
                } for layer in source.layers],
                "winner": {
                    "kind": source.winner.kind,
                    "source_id": source.winner.source_id,
                    "value": _plain(source.winner.value),
                    "raw_expression": source.winner.raw_expression,
                },
            }
            for name, source in job.variable_sources.items()
        },
        "profiles": [
            {
                "name": profile.name,
                "qualified_id": profile.qualified_id,
                "namespace": profile.namespace,
                "source": profile.source,
                "kind": profile.kind,
                "content_hash": profile.content_hash,
                "path": profile.path,
            }
            for profile in job.profiles
        ],
        "manufacturing": {
            "directives": {
                key: {
                    "value": _plain(directive.value),
                    "strength": directive.strength,
                    "source": directive.source.id,
                }
                for key, directive in job.manufacturing.directives.items()
            },
            "notes": [list(note) for note in job.manufacturing.notes],
        },
        "status": "queued",
        "queued_at": queued_at,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "command": [],
        "dependencies": [],
        "dependency_environment": None,
        "artifact": None,
        "artifact_bytes": None,
        "artifact_sha256": None,
        "reused_from": None,
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
    *,
    dependency_file: Path | None = None,
) -> list[str]:
    command = [str(openscad), "-o", str(output)]
    if dependency_file is not None:
        command.extend(("-d", str(dependency_file)))
    command.extend(geometry_define_argv(job, revision))
    command.extend(["--export-format", "asciistl", str(source)])
    return command


def _declared_libraries_for_environment(
    libraries: Mapping[str, CadLibrary], repository_root: Path, staged_root: Path
) -> dict[str, CadLibrary]:
    """Translate repository library declarations into a revision snapshot."""

    translated: dict[str, CadLibrary] = {}
    for name, library in libraries.items():
        try:
            relative = library.path.resolve().relative_to(repository_root)
        except ValueError:
            path = library.path
        else:
            path = staged_root / relative
        translated[name] = CadLibrary(
            library.name, path, library.license, library.revision
        )
    return translated


def _staged_render_environment(
    base: Mapping[str, str], openscad_paths: tuple[Path, ...], isolated_root: Path
) -> dict[str, str]:
    environment = dict(base)
    home = isolated_root / "home"
    config = isolated_root / "config"
    data = isolated_root / "data"
    local_data = isolated_root / "local-data"
    for directory in (home, config, data, local_data):
        directory.mkdir(parents=True, exist_ok=True)
    environment.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config),
        "XDG_DATA_HOME": str(data),
        "APPDATA": str(data),
        "LOCALAPPDATA": str(local_data),
        "OPENSCADPATH": os.pathsep.join(str(path) for path in openscad_paths),
    })
    return environment


def _dependency_inventory(records: object) -> list[dict[str, object]]:
    """Serialize the verified immutable records, never the mutable stage tree."""

    return [{
        "logical_name": record.logical_name,
        "classification": record.classification,
        "archive_path": record.archive_path.as_posix(),
        "content_hash": record.content_hash,
        "git_revision": record.git_revision,
        "license": record.license,
        "asset": record.asset,
    } for record in sorted(records, key=lambda item: item.archive_path.as_posix())]


def _search_environment(environment: Mapping[str, str]) -> dict[str, object]:
    """Return only OpenSCAD resolution inputs; never archive arbitrary env vars."""

    result: dict[str, object] = {}
    for key in ("OPENSCADPATH", "HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        value = environment.get(key)
        if value is None:
            result[key] = None
        elif key == "OPENSCADPATH":
            result[key] = [item for item in value.split(os.pathsep) if item]
        else:
            result[key] = value
    return result


def _safe_component(value: str) -> str:
    return _SAFE_COMPONENT.sub("-", value).strip("-.") or "run"


def _readable_run_id(
    now: datetime, part: str, selector: str, revision: str
) -> str:
    return "-".join((
        f"{now.year:04d}",
        f"{now.strftime('%b').lower()}{now.day}",
        _safe_component(part),
        _safe_component(selector),
        f"{now.hour:02d}h:{now.minute:02d}m",
        _safe_component(revision),
    ))


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
    artifacts_fd: int | None = None,
) -> None:
    job["status"] = "failed"
    job["exit_code"] = None if process is None else process.returncode
    job["finished_at"] = _timestamp(_utc_now())
    job["elapsed_seconds"] = round(time.monotonic() - started_clock, 6)
    errors = job["errors"]
    assert isinstance(errors, list)
    errors.append(_error_text(error))
    if artifacts_fd is None:
        _remove_temporary_artifact(temporary_artifact)
    else:
        _unlink_artifact(artifacts_fd, temporary_artifact.name)


def _copy_snapshot(
    snapshot: SourceSnapshot, model_id: str, run_dir: Path,
    source_fd: int | None = None,
) -> Path:
    visible = run_dir / "source" / _safe_component(model_id) / snapshot.scad_path.name
    target = (
        Path(f"/proc/self/fd/{source_fd}") / _safe_component(model_id)
        / snapshot.scad_path.name
        if source_fd is not None else visible
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshot.scad_path.parent, target.parent, dirs_exist_ok=True)
    return visible


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass
class _VerifiedArtifact:
    fd: int
    size: int
    checksum: str
    source_path: Path
    manifest: dict[str, object]
    job: Mapping[str, object]

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _read_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(fd, 1024 * 1024, offset)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while True:
        chunk = os.pread(fd, 1024 * 1024, offset)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)
        offset += len(chunk)


def _proc_fd_path(fd: int, *parts: str) -> Path:
    root = Path("/proc/self/fd")
    if not root.is_dir():
        raise RuntimeError(
            "descriptor-anchored CAD rendering requires Linux /proc/self/fd"
        )
    anchored = root / str(fd)
    try:
        os.fstat(fd)
    except OSError as error:
        raise RuntimeError("CAD render descriptor is not open") from error
    return anchored.joinpath(*parts)


def _open_artifact(
    artifacts_fd: int, name: str,
) -> tuple[int, os.stat_result] | None:
    try:
        fd = os.open(
            name, os.O_RDONLY | _NOFOLLOW | _CLOEXEC, dir_fd=artifacts_fd
        )
    except FileNotFoundError:
        return None
    details = os.fstat(fd)
    if not stat.S_ISREG(details.st_mode) or details.st_size <= 0:
        os.close(fd)
        return None
    return fd, details


def _unlink_artifact(artifacts_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=artifacts_fd)
    except FileNotFoundError:
        pass


def _open_run_manifest(root_fd: int, run_name: str) -> tuple[int, dict[str, object]]:
    run_fd = os.open(
        run_name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
        dir_fd=root_fd,
    )
    try:
        manifest_fd = os.open(
            "manifest.json", os.O_RDONLY | _NOFOLLOW | _CLOEXEC,
            dir_fd=run_fd,
        )
        try:
            if not stat.S_ISREG(os.fstat(manifest_fd).st_mode):
                raise ValueError("CAD run manifest is not a regular file")
            value = json.loads(_read_fd(manifest_fd))
        finally:
            os.close(manifest_fd)
        if not isinstance(value, dict) or value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported CAD run manifest")
        return run_fd, value
    except BaseException:
        os.close(run_fd)
        raise


def _open_archive_directory(
    data_dir: str | os.PathLike[str], system_name: str,
) -> tuple[Path, int]:
    """Open/create cad/prints/system without following intermediate symlinks."""

    if _safe_component(system_name) != system_name or system_name in {".", ".."}:
        raise ValueError("CAD system name is not a safe archive component")
    trusted_root = Path(data_dir).resolve()
    trusted_root.mkdir(parents=True, exist_ok=True)
    current_fd = os.open(
        trusted_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
    )
    current_path = trusted_root
    try:
        for component in ("cad", "prints", system_name):
            try:
                os.mkdir(component, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(
                component, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
            current_path /= component
        return current_path, current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _find_geometry_artifact(
    archive_root: Path, *, model_id: str, model_geometry_hash: str,
    geometry_fingerprint: str, excluded: Path, archive_fd: int | None = None,
) -> _VerifiedArtifact | None:
    """Find a verified successful artifact with identical render inputs."""

    try:
        root_fd = os.dup(archive_fd) if archive_fd is not None else os.open(
            archive_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
        )
    except OSError:
        return None
    try:
        for run_name in sorted(os.listdir(root_fd), reverse=True):
            if run_name == excluded.name or run_name.startswith("."):
                continue
            try:
                run_fd, manifest = _open_run_manifest(root_fd, run_name)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            try:
                models = manifest.get("models")
                jobs = manifest.get("jobs")
                if not isinstance(models, Mapping) or not isinstance(jobs, list):
                    continue
                model = models.get(model_id)
                if (not isinstance(model, Mapping)
                        or model.get("geometry_hash") != model_geometry_hash):
                    continue
                for job in jobs:
                    if not isinstance(job, Mapping) or (
                        job.get("model") != model_id
                        or job.get("geometry_fingerprint") != geometry_fingerprint
                        or job.get("status") != "complete"
                    ):
                        continue
                    recorded = job.get("artifact_sha256")
                    relative = job.get("artifact")
                    if (not isinstance(recorded, str) or _SHA256.fullmatch(recorded) is None
                            or not isinstance(relative, str)):
                        continue
                    parts = Path(relative).parts
                    if (len(parts) != 2 or parts[0] != "artifacts"
                            or parts[1] in {"", ".", ".."}):
                        continue
                    artifacts_fd = os.open(
                        "artifacts", os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                        dir_fd=run_fd,
                    )
                    try:
                        artifact_fd = os.open(
                            parts[1], os.O_RDONLY | _NOFOLLOW | _CLOEXEC,
                            dir_fd=artifacts_fd,
                        )
                    finally:
                        os.close(artifacts_fd)
                    try:
                        details = os.fstat(artifact_fd)
                        if not stat.S_ISREG(details.st_mode) or details.st_size <= 0:
                            continue
                        checksum = _sha256_fd(artifact_fd)
                        if checksum != recorded:
                            continue
                        verified = _VerifiedArtifact(
                            artifact_fd, details.st_size, checksum,
                            archive_root / run_name / relative, manifest, job,
                        )
                        artifact_fd = -1
                        return verified
                    finally:
                        if artifact_fd >= 0:
                            os.close(artifact_fd)
            except OSError:
                continue
            finally:
                os.close(run_fd)
        return None
    finally:
        os.close(root_fd)


def _copy_verified_artifact(
    source: _VerifiedArtifact, target: Path, destination_fd: int | None = None,
) -> None:
    """Atomically copy a verified open regular file into a fresh run."""

    directory_fd = os.dup(destination_fd) if destination_fd is not None else os.open(
        target.parent, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
    )
    temporary_name = f".{target.name}.reuse.tmp"
    fd = -1
    try:
        fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o644,
            dir_fd=directory_fd,
        )
        offset = 0
        digest = hashlib.sha256()
        while offset < source.size:
            chunk = os.pread(source.fd, min(1024 * 1024, source.size - offset), offset)
            if not chunk:
                raise OSError("verified artifact changed while being copied")
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            offset += len(chunk)
        if digest.hexdigest() != source.checksum:
            raise OSError("verified artifact changed while being copied")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            os.link(
                temporary_name, target.name,
                src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise _ReuseTargetExists(
                f"artifact target appeared during reuse: {target.name}"
            ) from error
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        finally:
            os.close(directory_fd)


def _destination_exists(path: Path, destination_fd: int | None = None) -> bool:
    directory_fd = os.dup(destination_fd) if destination_fd is not None else os.open(
        path.parent, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
    )
    try:
        try:
            os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True
    finally:
        os.close(directory_fd)


def _generation_identity(
    plan_data: Mapping[str, object], source_hashes: Mapping[str, str]
) -> dict[str, object]:
    jobs = plan_data.get("jobs", [])
    selection = plan_data.get("selection")
    assert isinstance(jobs, list)
    assert isinstance(selection, Mapping)
    return {
        "source_hashes": dict(source_hashes),
        "system_manifest_hash": plan_data.get("system_manifest_hash"),
        "selection": dict(selection),
        "geometry_fingerprints": [
            job.get("geometry_fingerprint")
            for job in jobs
            if isinstance(job, Mapping)
        ],
        "manufacturing_fingerprints": [
            job.get("manufacturing_fingerprint")
            for job in jobs
            if isinstance(job, Mapping)
        ],
    }


def _manufacturing_run_token(jobs: tuple[RenderJob, ...]) -> str:
    fingerprints = tuple(job.manufacturing_fingerprint for job in jobs)
    if len(fingerprints) == 1:
        return fingerprints[0]
    return hashlib.sha256("\0".join(fingerprints).encode("ascii")).hexdigest()


def _only_manufacturing_identity_differs(
    first: Mapping[str, object], second: Mapping[str, object]
) -> bool:
    keys = (
        "source_hashes", "system_manifest_hash", "selection",
        "geometry_fingerprints",
    )
    return (
        all(first.get(key) == second.get(key) for key in keys)
        and first.get("manufacturing_fingerprints")
        != second.get("manufacturing_fingerprints")
    )


def _secure_existing_identity(
    archive_root: Path, run_name: str, archive_fd: int | None = None,
) -> dict[str, object] | None:
    try:
        root_fd = os.dup(archive_fd) if archive_fd is not None else os.open(
            archive_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
        )
        try:
            run_fd, manifest = _open_run_manifest(root_fd, run_name)
            os.close(run_fd)
        finally:
            os.close(root_fd)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return _manifest_generation_identity(manifest)


def _create_managed_run_directory(
    archive_root: Path, base_run_id: str, plan: RenderPlan,
    identity: Mapping[str, object], archive_fd: int,
) -> tuple[str, Path, int]:
    """Atomically allocate a deterministic unique managed run directory."""

    archive_root.mkdir(parents=True, exist_ok=True)

    def claim(name: str) -> tuple[Path, int] | None:
        candidate = archive_root / name
        try:
            os.mkdir(name, dir_fd=archive_fd)
        except FileExistsError:
            return None
        run_fd = os.open(
            name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            dir_fd=archive_fd,
        )
        try:
            opened = os.fstat(run_fd)
            try:
                visible = os.stat(candidate, follow_symlinks=False)
            except OSError as error:
                raise OSError(
                    "CAD archive path changed during run allocation"
                ) from error
            if (opened.st_dev, opened.st_ino) != (visible.st_dev, visible.st_ino):
                raise OSError("CAD archive path changed during run allocation")
        except BaseException:
            os.close(run_fd)
            raise
        return candidate, run_fd

    claimed = claim(base_run_id)
    if claimed is not None:
        return base_run_id, claimed[0], claimed[1]

    existing = _secure_existing_identity(archive_root, base_run_id, archive_fd)
    if existing is not None and _only_manufacturing_identity_differs(existing, identity):
        token = _manufacturing_run_token(plan.jobs)
        for length in range(7, len(token) + 1):
            name = f"{base_run_id}-mfg{token[:length]}"
            claimed = claim(name)
            if claimed is not None:
                return name, claimed[0], claimed[1]
        stem = f"{base_run_id}-mfg{token}"
    else:
        stem = base_run_id

    counter = 2
    while True:
        name = f"{stem}-{counter}"
        claimed = claim(name)
        if claimed is not None:
            return name, claimed[0], claimed[1]
        counter += 1


def _verify_visible_directory(fd: int, path: Path, label: str) -> None:
    opened = os.fstat(fd)
    try:
        visible = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise OSError(f"CAD {label} path changed during generation") from error
    if (not stat.S_ISDIR(visible.st_mode)
            or (opened.st_dev, opened.st_ino) != (visible.st_dev, visible.st_ino)):
        raise OSError(f"CAD {label} path changed during generation")


def _publish_rendered_artifact(
    temporary: Path, final: Path, artifacts_fd: int,
) -> tuple[int, str]:
    opened = _open_artifact(artifacts_fd, temporary.name)
    if opened is None:
        raise OSError("rendered artifact is not a non-empty regular file")
    fd, details = opened
    checksum = _sha256_fd(fd)
    candidate = _VerifiedArtifact(
        fd, details.st_size, checksum, temporary, {}, {}
    )
    try:
        _copy_verified_artifact(candidate, final, artifacts_fd)
    finally:
        candidate.close()
    _unlink_artifact(artifacts_fd, temporary.name)
    return details.st_size, checksum


def _manifest_generation_identity(
    manifest: Mapping[str, object],
) -> dict[str, object] | None:
    models = manifest.get("models")
    jobs = manifest.get("jobs")
    if not isinstance(models, Mapping) or not isinstance(jobs, list):
        return None
    source_hashes = {str(name): value.get("content_hash") for name, value in models.items()
                     if isinstance(value, Mapping)}
    if len(source_hashes) != len(models) or not all(isinstance(value, str) for value in source_hashes.values()) or not all(
        isinstance(job, Mapping)
        and isinstance(job.get("geometry_fingerprint"), str)
        and isinstance(job.get("manufacturing_fingerprint"), str)
        for job in jobs
    ):
        return None
    return {
        "source_hashes": source_hashes,
        "system_manifest_hash": manifest.get("system", {}).get("manifest_hash") if isinstance(manifest.get("system"), Mapping) else None,
        "selection": manifest.get("selection"),
        "geometry_fingerprints": [job["geometry_fingerprint"] for job in jobs],
        "manufacturing_fingerprints": [
            job["manufacturing_fingerprint"] for job in jobs
        ],
    }


def _created_local_date(
    manifest: Mapping[str, object], local_now: datetime
) -> object | None:
    created = manifest.get("created_at")
    if not isinstance(created, str):
        return None
    try:
        parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(local_now.tzinfo).date()


def _find_duplicate_run(
    part_root: Path,
    identity: Mapping[str, object],
    local_now: datetime,
    archive_fd: int | None = None,
) -> tuple[str, Path] | None:
    try:
        root_fd = os.dup(archive_fd) if archive_fd is not None else os.open(
            part_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
        )
    except OSError:
        return None
    try:
        for run_name in sorted(os.listdir(root_fd)):
            if run_name.startswith("."):
                continue
            try:
                run_fd, manifest = _open_run_manifest(root_fd, run_name)
                os.close(run_fd)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            run_id = manifest.get("run_id")
            if (
                isinstance(run_id, str)
                and _created_local_date(manifest, local_now) == local_now.date()
                and _manifest_generation_identity(manifest) == identity
            ):
                return run_id, part_root / run_name
        return None
    finally:
        os.close(root_fd)


def _hidden_directory(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=parent, prefix=f".{prefix}."))


def _rewrite_run_paths(run_dir: Path, old: Path, new: Path) -> None:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = load_run(manifest_path)
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        return
    old_text = str(old)
    new_text = str(new)
    for job in jobs:
        if not isinstance(job, dict):
            continue
        command = job.get("command")
        if isinstance(command, list):
            job["command"] = [
                item.replace(old_text, new_text)
                if isinstance(item, str)
                else item
                for item in command
            ]
    _write_manifest(run_dir, manifest)
    _best_effort_readme(run_dir, manifest)


def _preserve_failed_regeneration(staging: Path, target: Path) -> Path:
    failed = _hidden_directory(
        target.parent, f"{target.name}.regeneration-failed"
    )
    failed.rmdir()
    try:
        _rewrite_run_paths(staging, staging, failed)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    os.replace(staging, failed)
    return failed


def _publish_regeneration(staging: Path, target: Path) -> Path:
    _rewrite_run_paths(staging, staging, target)
    backup = _hidden_directory(target.parent, f"{target.name}.backup")
    backup.rmdir()
    os.replace(target, backup)
    try:
        os.replace(staging, target)
    except BaseException:
        os.replace(backup, target)
        raise
    shutil.rmtree(backup)
    return target


def _finish_regeneration(
    result: GenerationResult, target: Path | None
) -> GenerationResult:
    if target is None:
        return result
    if result.status == "complete":
        published = _publish_regeneration(result.run_dir, target)
        return GenerationResult(
            published, published / "manifest.json", result.status
        )
    failed = _preserve_failed_regeneration(result.run_dir, target)
    return GenerationResult(failed, failed / "manifest.json", result.status)


def generate_plan(
    plan: RenderPlan,
    *,
    repo_root: str | os.PathLike[str],
    data_dir: str | os.PathLike[str],
    models: Mapping[str, CadModel],
    snapshots: Mapping[str, SourceSnapshot],
    libraries: Mapping[str, CadLibrary] | None = None,
    output: str | os.PathLike[str] | None = None,
    openscad: str | os.PathLike[str] = "openscad",
    revision: str | None = None,
    env: Mapping[str, str] | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
    regenerate: bool = False,
) -> GenerationResult:
    """Render a plan sequentially and persist every observable state change."""

    root = Path(repo_root).resolve()
    declared_libraries = dict(libraries or {})
    if not plan.jobs:
        raise ValueError("CAD render plan contains no jobs")
    selected_model_ids = tuple(dict.fromkeys(job.model_id for job in plan.jobs))
    missing_models = [name for name in selected_model_ids if name not in models]
    missing_snapshots = [name for name in selected_model_ids if name not in snapshots]
    if missing_models:
        raise ValueError(f"Missing CAD model: {missing_models[0]}")
    if missing_snapshots:
        raise ValueError(f"Missing source snapshot: {missing_snapshots[0]}")
    archive_name = plan.system_name
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    regeneration_target: Path | None = None
    run_dir: Path | None = None
    archive_fd = -1
    run_fd = -1
    source_fd = -1
    artifacts_fd = -1
    logs_fd = -1
    try:
        local_now = _local_now()
        selector = (f"product-{plan.selection.product}" if plan.selection.product else
                    f"{plan.selection.model or plan.jobs[0].model_id}-" +
                    (plan.jobs[0].variant_name if len(plan.jobs) == 1 else "sets"))
        plan_data = plan_as_dict(plan)
        source_hashes = {name: _hash_tree(snapshots[name].scad_path.parent)
                         for name in selected_model_ids}
        archive_part_root, archive_fd = _open_archive_directory(
            data_dir, archive_name
        )
        generation_identity = _generation_identity(plan_data, source_hashes)
        if output is None:
            duplicate = _find_duplicate_run(
                archive_part_root,
                generation_identity,
                local_now,
                archive_fd,
            )
            if duplicate is not None:
                if not regenerate:
                    raise CadRunExistsError(*duplicate)
                run_id, regeneration_target = duplicate
        version_result = subprocess.run(
            [str(openscad), "--version"], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=dict(env) if env is not None else None,
        )
        if version_result.returncode != 0:
            raise RuntimeError(version_result.stdout.strip() or "OpenSCAD version check failed")
        openscad_version = version_result.stdout.strip()
        base_environment = dict(env) if env is not None else dict(os.environ)
        # Derive the archive creation instant and its local-day identity from
        # one clock sample; crossing midnight between separate samples must
        # not make a just-created run invisible to duplicate detection.
        now = local_now.astimezone(timezone.utc)
        if regeneration_target is None:
            base_run_id = _readable_run_id(
                local_now, archive_name, selector,
                "-".join(dict.fromkeys(snapshots[name].revision_label for name in selected_model_ids))
            )
            if output is None:
                run_id, run_dir, run_fd = _create_managed_run_directory(
                    archive_part_root, base_run_id, plan, generation_identity,
                    archive_fd,
                )
            else:
                run_id = base_run_id
                run_dir = Path(output).resolve()
                try:
                    run_dir.mkdir(parents=True, exist_ok=False)
                except FileExistsError as error:
                    raise ValueError(f"CAD output directory already exists: {run_dir}") from error
                run_fd = os.open(
                    run_dir, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
                )
        else:
            run_dir = _hidden_directory(
                archive_part_root,
                f"{regeneration_target.name}.regenerating",
            )
            run_fd = os.open(
                run_dir, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
            )
        for child in ("source", "artifacts", "logs"):
            os.mkdir(child, dir_fd=run_fd)
        source_fd = os.open(
            "source", os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            dir_fd=run_fd,
        )
        artifacts_fd = os.open(
            "artifacts", os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            dir_fd=run_fd,
        )
        logs_fd = os.open(
            "logs", os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            dir_fd=run_fd,
        )

        def verify_destination() -> None:
            _verify_visible_directory(archive_fd, archive_part_root, "system archive")
            _verify_visible_directory(run_fd, run_dir, "run")
            _verify_visible_directory(source_fd, run_dir / "source", "source")
            _verify_visible_directory(artifacts_fd, run_dir / "artifacts", "artifacts")
            _verify_visible_directory(logs_fd, run_dir / "logs", "logs")

        archived_sources: dict[str, Path] = {}
        for name in selected_model_ids:
            verify_destination()
            archived_sources[name] = _copy_snapshot(
                snapshots[name], name, run_dir, source_fd
            )
            verify_destination()
        created = _timestamp(now)
        jobs = [
            _job_entry(job, created, f"logs/{job.artifact_id}.log")
            for job in plan.jobs
        ]
        manifest: dict[str, object] = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "run_id": run_id,
            "system_name": plan.system_name,
            "status": "running",
            "created_at": created,
            "updated_at": created,
            "started_at": created,
            "finished_at": None,
            "system": {"name": plan.system_name, "path": str(plan.system_path),
                       "manifest_hash": plan.system_manifest_hash},
            "selection": plan_data["selection"],
            "models": {
                name: {
                    "scad_path": str(models[name].source_path.relative_to(root)),
                    "metadata_path": (str(models[name].sidecar_path.relative_to(root))
                                      if models[name].sidecar_path is not None else None),
                    "commit": snapshots[name].full_commit,
                    "revision": snapshots[name].revision_label,
                    "content_hash": _hash_tree(archived_sources[name].parent),
                    "geometry_hash": (
                        snapshots[name].geometry_identity
                        or snapshots[name].source_identity
                    ),
                    "dirty": snapshots[name].dirty,
                } for name in selected_model_ids
            },
            "openscad_version": openscad_version,
            "openscad": {
                "version": openscad_version.removeprefix("OpenSCAD version ").removeprefix("OpenSCAD Version: "),
                "info_sha256": None,
            },
            "jobs": jobs,
        }
        def write_manifest_state() -> None:
            verify_destination()
            _write_manifest(run_dir, manifest, run_fd)

        def write_readme_state() -> None:
            verify_destination()
            _write_readme(run_dir, manifest, run_fd)

        def best_effort_readme_state() -> None:
            try:
                write_readme_state()
            except OSError:
                pass

        write_manifest_state()
        try:
            write_readme_state()
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
            write_manifest_state()
            return _finish_regeneration(
                GenerationResult(run_dir, run_dir / "manifest.json", "failed"),
                regeneration_target,
            )

        failed = False
        for render_job, job in zip(plan.jobs, jobs):
            set_banner = (
                f"\n====== {plan.system_name} cad: set name: "
                f"{render_job.set_name} ======\n\n"
            )
            out.write(set_banner)
            out.flush()
            started = _utc_now()
            started_clock = time.monotonic()
            job["status"] = "running"
            job["started_at"] = _timestamp(started)
            artifact_stem = (
                f"{render_job.artifact_id}--{_safe_component(snapshots[render_job.model_id].revision_label)}"
            )
            temporary_artifact = run_dir / "artifacts" / f".{artifact_stem}.tmp.stl"
            final_artifact = run_dir / "artifacts" / f"{artifact_stem}.stl"
            anchored_output = _proc_fd_path(artifacts_fd, temporary_artifact.name)
            geometry_hash = (
                snapshots[render_job.model_id].geometry_identity
                or snapshots[render_job.model_id].source_identity
            )
            verify_destination()
            reusable = None if regeneration_target is not None else _find_geometry_artifact(
                archive_part_root,
                model_id=render_job.model_id,
                model_geometry_hash=geometry_hash,
                geometry_fingerprint=render_job.geometry_fingerprint,
                excluded=run_dir,
                archive_fd=archive_fd,
            )
            if reusable is not None:
                try:
                    verify_destination()
                    _copy_verified_artifact(
                        reusable, final_artifact, artifacts_fd
                    )
                    log_name = Path(str(job["log"])).name
                    empty_log_fd = os.open(
                        log_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                        0o644, dir_fd=logs_fd,
                    )
                    os.write(empty_log_fd, set_banner.encode("utf-8"))
                    os.close(empty_log_fd)
                    finished = _utc_now()
                    job["status"] = "complete"
                    job["finished_at"] = _timestamp(finished)
                    job["elapsed_seconds"] = round(
                        time.monotonic() - started_clock, 6
                    )
                    job["exit_code"] = 0
                    job["artifact"] = str(final_artifact.relative_to(run_dir))
                    reused_output = _open_artifact(artifacts_fd, final_artifact.name)
                    if reused_output is None:
                        raise OSError("reused artifact disappeared after publication")
                    reused_fd, reused_details = reused_output
                    try:
                        job["artifact_bytes"] = reused_details.st_size
                        job["artifact_sha256"] = _sha256_fd(reused_fd)
                    finally:
                        os.close(reused_fd)
                    job["reused_from"] = {
                        "run_id": reusable.manifest.get("run_id"),
                        "artifact_id": reusable.job.get("artifact_id"),
                        "artifact": reusable.job.get("artifact"),
                    }
                    write_manifest_state()
                    best_effort_readme_state()
                    continue
                except _ReuseTargetExists as error:
                    _finalize_job_failure(
                        job,
                        started_clock=started_clock,
                        error=error,
                        process=None,
                        temporary_artifact=temporary_artifact,
                        artifacts_fd=artifacts_fd,
                    )
                    failed = True
                except Exception as error:
                    if _destination_exists(final_artifact, artifacts_fd):
                        _finalize_job_failure(
                            job,
                            started_clock=started_clock,
                            error=RuntimeError(
                                "artifact target appeared after reuse failure; "
                                "the existing target was preserved"
                            ),
                            process=None,
                            temporary_artifact=temporary_artifact,
                            artifacts_fd=artifacts_fd,
                        )
                        failed = True
                    else:
                        warnings = job["warnings"]
                        assert isinstance(warnings, list)
                        warnings.append(
                            "Geometry reuse failed; rendering normally: "
                            f"{_error_text(error)}"
                        )
                finally:
                    reusable.close()
            if failed:
                write_manifest_state()
                best_effort_readme_state()
                break
            stage_context: tempfile.TemporaryDirectory[str] | None = None
            staged = None
            render_dependencies: Path | None = None
            process_env: dict[str, str] | None = None
            discovery_output = ""
            try:
                verify_destination()
                stage_context = tempfile.TemporaryDirectory(
                    prefix="plamp-cad-render-"
                )
                transaction_root = Path(stage_context.name)
                info_environment = dict(base_environment)
                # Caller search paths are discovery inputs, not evidence that
                # their roots are OpenSCAD installation libraries.
                info_environment.pop("OPENSCADPATH", None)
                openscad_info = query_openscad_info(
                    openscad, env=info_environment
                )
                manifest["openscad"] = {
                    "version": openscad_info.version,
                    "info_sha256": hashlib.sha256(
                        openscad_info.raw_output.encode("utf-8")
                    ).hexdigest(),
                }
                snapshot = snapshots[render_job.model_id]
                model = models[render_job.model_id]
                discovery_env = prepare_discovery_environment(
                    root,
                    model.source_path,
                    revision=snapshot.full_commit or revision,
                    dirty=snapshot.dirty,
                    revision_label=snapshot.revision_label,
                )
                try:
                    translated_libraries = _declared_libraries_for_environment(
                        declared_libraries, root, discovery_env.root
                    )
                    source_environment = dict(base_environment)
                    discovery_paths = [
                        str(library.path)
                        for library in translated_libraries.values()
                    ]
                    configured_paths = source_environment.get("OPENSCADPATH")
                    if configured_paths:
                        discovery_paths.extend(
                            item for item in configured_paths.split(os.pathsep) if item
                        )
                    else:
                        discovery_paths.extend(
                            str(path) for path in openscad_info.library_paths
                        )
                    source_environment["OPENSCADPATH"] = os.pathsep.join(
                        dict.fromkeys(discovery_paths)
                    )
                    discovery = run_dependency_discovery(
                        openscad,
                        discovery_env,
                        render_job,
                        transaction_root / "discovery",
                        env=source_environment,
                        revision=snapshot.revision_label,
                    )
                    discovery_output = discovery.output
                    installation_roots = tuple(
                        path for path in openscad_info.library_paths
                        if openscad_info.user_library_path is None
                        or path.resolve() != openscad_info.user_library_path.resolve()
                    )
                    closure = classify_dependencies(
                        dependencies=discovery.dependencies,
                        model_root=discovery_env.source_path.parent,
                        repository_root=discovery_env.root,
                        declared_libraries=translated_libraries,
                        openscad_library_roots=installation_roots,
                        selected_revision=discovery_env.revision,
                    )
                    staged = stage_dependency_closure(
                        closure, transaction_root / "stage"
                    )
                    discovered_set = set(discovery.dependencies)
                    expected_records = tuple(
                        record for record in staged.records
                        if record.source_path in discovered_set
                    )
                finally:
                    discovery_env.cleanup()
                render_dependencies = transaction_root / "render.d"
                process_env = _staged_render_environment(
                    base_environment, staged.openscad_paths,
                    transaction_root / "isolated",
                )
                job["dependencies"] = _dependency_inventory(staged.records)
                job["dependency_environment"] = {
                    "discovery": _search_environment(source_environment),
                    "render": _search_environment(process_env),
                }
                process_env["PLAMP_CAD_MANIFEST"] = str(
                    _proc_fd_path(run_fd, "manifest.json")
                )
                command = _command(
                    Path(openscad), anchored_output, staged.model_source,
                    snapshot.revision_label, render_job,
                    dependency_file=render_dependencies,
                )
            except Exception as error:
                if stage_context is not None:
                    stage_context.cleanup()
                log_name = Path(str(job["log"])).name
                try:
                    failed_log_fd = os.open(
                        log_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                        0o644,
                        dir_fd=logs_fd,
                    )
                except FileExistsError:
                    pass
                else:
                    with os.fdopen(failed_log_fd, "w", encoding="utf-8") as failed_log:
                        if discovery_output:
                            failed_log.write("OpenSCAD dependency discovery:\n")
                            failed_log.write(discovery_output)
                            if not discovery_output.endswith("\n"):
                                failed_log.write("\n")
                        failed_log.write(f"dependency transaction failed: {_error_text(error)}\n")
                _finalize_job_failure(
                    job, started_clock=started_clock, error=error, process=None,
                    temporary_artifact=temporary_artifact,
                    artifacts_fd=artifacts_fd,
                )
                failed = True
                write_manifest_state()
                best_effort_readme_state()
                break
            job["command"] = command
            log_path = run_dir / str(job["log"])
            process: subprocess.Popen[str] | None = None
            try:
                write_manifest_state()
                write_readme_state()
                verify_destination()
                log_fd = os.open(
                    log_path.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                    0o644, dir_fd=logs_fd,
                )
                with os.fdopen(log_fd, "w", encoding="utf-8") as log:
                    log.write(set_banner)
                    log.flush()
                    verify_destination()
                    if discovery_output:
                        log.write("OpenSCAD dependency discovery:\n")
                        log.write(discovery_output)
                        if not discovery_output.endswith("\n"):
                            log.write("\n")
                        log.flush()
                    assert process_env is not None
                    assert staged is not None
                    process = subprocess.Popen(
                        command, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, env=process_env,
                        pass_fds=(artifacts_fd, source_fd, run_fd),
                        cwd=staged.model_source.parent,
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
                verify_destination()
                rendered = _open_artifact(artifacts_fd, temporary_artifact.name)
                if rendered is not None:
                    os.close(rendered[0])
                if exit_code == 0 and rendered is not None:
                    assert render_dependencies is not None
                    verify_staged_dependencies(
                        expected=expected_records,
                        actual=parse_make_dependencies(
                            render_dependencies, staged.model_source.parent
                        ),
                        staged_root=staged.root,
                    )
                    artifact_bytes, artifact_sha256 = _publish_rendered_artifact(
                        temporary_artifact, final_artifact, artifacts_fd
                    )
                    job["status"] = "complete"
                    job["artifact"] = str(final_artifact.relative_to(run_dir))
                    job["artifact_bytes"] = artifact_bytes
                    job["artifact_sha256"] = artifact_sha256
                else:
                    job["status"] = "failed"
                    failed = True
                    _unlink_artifact(artifacts_fd, temporary_artifact.name)
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
                _unlink_artifact(artifacts_fd, temporary_artifact.name)
                write_manifest_state()
                best_effort_readme_state()
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
                    artifacts_fd=artifacts_fd,
                )
                failed = True
            finally:
                if stage_context is not None:
                    stage_context.cleanup()
            write_manifest_state()
            best_effort_readme_state()
            if failed:
                break

        finished_at = _timestamp(_utc_now())
        manifest["status"] = "failed" if failed else "complete"
        manifest["finished_at"] = finished_at
        write_manifest_state()
        best_effort_readme_state()
        return _finish_regeneration(
            GenerationResult(
                run_dir,
                run_dir / "manifest.json",
                str(manifest["status"]),
            ),
            regeneration_target,
        )
    except KeyboardInterrupt:
        if (
            regeneration_target is not None
            and run_dir is not None
            and run_dir.is_dir()
        ):
            _preserve_failed_regeneration(run_dir, regeneration_target)
        raise
    except OSError as error:
        if (
            regeneration_target is not None
            and run_dir is not None
            and run_dir.is_dir()
        ):
            _preserve_failed_regeneration(run_dir, regeneration_target)
        print(str(error), file=err)
        raise
    finally:
        for fd in (logs_fd, artifacts_fd, source_fd, run_fd):
            if fd >= 0:
                os.close(fd)
        if archive_fd >= 0:
            os.close(archive_fd)


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
    manifests = [
        path for path in manifests
        if not path.parent.name.startswith(".")
        and not path.parent.parent.name.startswith(".")
    ]
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
