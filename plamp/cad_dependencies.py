"""Deterministic parsing of OpenSCAD dependency and installation metadata."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from typing import Mapping

from plamp.cad_values import serialize_scad_value


class CadDependencyError(RuntimeError):
    """Dependency discovery metadata is absent, malformed, or unsafe."""


@dataclass(frozen=True)
class OpenScadInfo:
    version: str
    user_library_path: Path | None
    library_paths: tuple[Path, ...]
    raw_output: str


@dataclass(frozen=True)
class DependencyRecord:
    source_path: Path
    classification: str
    logical_name: str
    archive_path: Path
    content_hash: str
    git_revision: str | None = None
    license: str | None = None
    asset: bool = False


@dataclass(frozen=True)
class DiscoveryEnvironment:
    """Repository tree used only to discover one job's dependency closure."""

    root: Path
    source_path: Path
    revision: str | None
    dirty: bool
    cleanup_root: Path | None

    def cleanup(self) -> None:
        cleanup_discovery_environment(self)

    def __enter__(self) -> "DiscoveryEnvironment":
        return self

    def __exit__(self, *_: object) -> None:
        self.cleanup()


@dataclass(frozen=True)
class DiscoveryResult:
    argv: tuple[str, ...]
    dependencies: tuple[Path, ...]
    output: str


def job_define_argv(job: object) -> tuple[str, ...]:
    """Build the common, ordered OpenSCAD defines for discovery and rendering."""

    arguments: list[str] = [
        "-D", f"set={serialize_scad_value(getattr(job, 'set_name'))}"
    ]
    for name, value in getattr(job, "variables").items():
        if name != "set":
            arguments.extend(("-D", f"{name}={serialize_scad_value(value)}"))
    for name, expression in getattr(job, "raw_defines").items():
        if name != "set":
            arguments.extend(("-D", f"{name}={expression}"))
    return tuple(arguments)


def _git_revision(repo_root: Path, revision: str | None) -> str:
    requested = revision.strip() if revision is not None else "HEAD"
    if not requested:
        requested = "HEAD"
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", f"{requested}^{{commit}}"],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise CadDependencyError(
            f"cannot resolve CAD discovery revision {requested!r}: {detail}"
        ) from error
    return completed.stdout.strip()


def _extract_git_archive(archive_bytes: bytes, destination: Path) -> None:
    """Extract only ordinary Git archive directories/files within destination."""

    import io

    boundary = destination.resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            members = archive.getmembers()
            for member in members:
                relative = Path(member.name)
                if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                    raise CadDependencyError("unsafe path in Git discovery archive")
                target = (destination / relative).resolve()
                try:
                    target.relative_to(boundary)
                except ValueError as error:
                    raise CadDependencyError("unsafe path in Git discovery archive") from error
                if not (member.isdir() or member.isfile()):
                    raise CadDependencyError("unsafe link or special file in Git discovery archive")
            for member in members:
                target = destination / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise CadDependencyError("cannot read file in Git discovery archive")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                os.chmod(target, member.mode & 0o777)
    except (tarfile.TarError, OSError) as error:
        if isinstance(error, CadDependencyError):
            raise
        raise CadDependencyError(f"cannot extract Git discovery archive: {error}") from error


def prepare_discovery_environment(
    repo_root: str | os.PathLike[str],
    source_path: str | os.PathLike[str] | None = None,
    *,
    revision: str | None = None,
    dirty: bool = False,
    revision_label: str | None = None,
) -> DiscoveryEnvironment:
    """Prepare current dirty or revision-pinned repository dependency discovery."""

    root = Path(repo_root).resolve()
    supplied_source = Path(source_path) if source_path is not None else Path(".")
    source = supplied_source.resolve() if supplied_source.is_absolute() else (root / supplied_source).resolve()
    try:
        relative_source = source.relative_to(root)
    except ValueError as error:
        raise CadDependencyError("CAD discovery source must be inside the repository") from error
    if dirty:
        if revision_label is None or not revision_label.strip():
            raise ValueError("dirty CAD dependency discovery requires an explicit revision label")
        if not source.exists():
            raise CadDependencyError(f"CAD discovery source does not exist: {source}")
        return DiscoveryEnvironment(root, source, None, True, None)

    commit = _git_revision(root, revision)
    cleanup = Path(tempfile.mkdtemp(prefix="plamp-cad-discovery-"))
    try:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), "archive", "--format=tar", commit],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            detail = getattr(error, "stderr", b"")
            if isinstance(detail, bytes):
                detail = detail.decode(errors="replace")
            raise CadDependencyError(
                f"cannot archive CAD discovery revision {commit}: {detail or error}"
            ) from error
        _extract_git_archive(completed.stdout, cleanup)
        archived_source = cleanup / relative_source
        if not archived_source.exists():
            raise CadDependencyError(
                f"CAD discovery source {relative_source} is absent from revision {commit}"
            )
        return DiscoveryEnvironment(cleanup, archived_source, commit, False, cleanup)
    except BaseException:
        shutil.rmtree(cleanup, ignore_errors=True)
        raise


def cleanup_discovery_environment(environment: DiscoveryEnvironment) -> None:
    """Remove an archived discovery tree; dirty working trees are never removed."""

    if environment.cleanup_root is not None:
        shutil.rmtree(environment.cleanup_root, ignore_errors=True)


def run_dependency_discovery(
    openscad: str | os.PathLike[str],
    environment: DiscoveryEnvironment,
    job: object,
    output_dir: str | os.PathLike[str],
    *,
    env: Mapping[str, str],
) -> DiscoveryResult:
    """Run OpenSCAD's cheap CSG dependency pass without producing an STL."""

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csg = output_root / "discovery.csg"
    dependencies = output_root / "discovery.d"
    try:
        csg.unlink(missing_ok=True)
        dependencies.unlink(missing_ok=True)
    except OSError as error:
        raise CadDependencyError(
            f"cannot clear stale dependency discovery output in {output_root}: {error}"
        ) from error
    argv = (
        str(openscad), "-o", str(csg), "-d", str(dependencies),
        *job_define_argv(job), str(environment.source_path),
    )
    try:
        completed = subprocess.run(
            list(argv), cwd=environment.source_path.parent, env=dict(env), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
    except OSError as error:
        raise CadDependencyError(
            f"cannot run OpenSCAD dependency discovery using {openscad}: {error}"
        ) from error
    output = completed.stdout or ""
    if completed.returncode != 0:
        raise CadDependencyError(
            f"OpenSCAD dependency discovery failed with status {completed.returncode}: {output}"
        )
    if not dependencies.is_file():
        raise CadDependencyError(
            f"OpenSCAD dependency discovery did not produce {dependencies}: {output}"
        )
    return DiscoveryResult(
        argv, parse_make_dependencies(dependencies, environment.source_path.parent), output
    )


def _join_make_continuations(source: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(source):
        if source[index] == "\\":
            if source.startswith("\r\n", index + 1):
                index += 3
                continue
            if source.startswith("\n", index + 1):
                index += 2
                continue
        result.append(source[index])
        index += 1
    return "".join(result)


def _dependency_text(source: str) -> str:
    escaped = False
    target: list[str] = []
    for index, character in enumerate(source):
        if escaped:
            target.append(character)
            escaped = False
            continue
        if character == "\\":
            target.append(character)
            escaped = True
            continue
        if character != ":":
            target.append(character)
            continue
        target_text = "".join(target).lstrip()
        drive_colon = (
            len(target_text) == 1
            and target_text.isalpha()
            and index + 1 < len(source)
            and source[index + 1] in ("/", "\\")
        )
        if not drive_colon:
            return source[index + 1 :]
    raise CadDependencyError("malformed make dependency file: missing target colon")


def _make_tokens(source: str) -> tuple[str, ...]:
    tokens: list[str] = []
    token: list[str] = []
    escaped = False
    in_comment = False
    for character in source:
        if in_comment:
            if character in "\r\n":
                in_comment = False
            continue
        if escaped:
            token.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "#":
            if token:
                tokens.append("".join(token))
                token.clear()
            in_comment = True
        elif character.isspace():
            if token:
                tokens.append("".join(token))
                token.clear()
        else:
            token.append(character)
    if escaped:
        raise CadDependencyError("malformed make dependency file: dangling escape")
    if token:
        tokens.append("".join(token))
    return tuple(tokens)


def parse_make_dependencies(path: Path, working_directory: Path) -> tuple[Path, ...]:
    """Return strict absolute dependency files in first-seen order."""

    try:
        source = path.read_text()
    except (OSError, UnicodeError) as error:
        raise CadDependencyError(f"cannot read dependency file {path}: {error}") from error
    tokens = _make_tokens(_dependency_text(_join_make_continuations(source)))
    dependencies: list[Path] = []
    seen: set[Path] = set()
    for token in tokens:
        try:
            candidate = Path(token)
            if not candidate.is_absolute():
                candidate = working_directory / candidate
            resolved = candidate.resolve(strict=True)
        except ValueError as error:
            raise CadDependencyError(
                f"invalid dependency path token {token!r}: {error}"
            ) from error
        except (OSError, RuntimeError) as error:
            raise CadDependencyError(
                f"dependency {candidate} does not exist: {error}"
            ) from error
        if not resolved.is_file():
            raise CadDependencyError(f"dependency {resolved} is not a file")
        if resolved not in seen:
            seen.add(resolved)
            dependencies.append(resolved)
    return tuple(dependencies)


_VERSION = re.compile(r"^OpenSCAD Version:\s*(\S.*?)\s*$", re.MULTILINE)
_LABEL = re.compile(r"^[A-Za-z_][^/\\]*:\s*(.*)$")


def _is_label(line: str) -> bool:
    match = _LABEL.match(line)
    return bool(match and not (len(line) > 2 and line[1] == ":" and line[2] in "/\\"))


def parse_openscad_info(output: str) -> OpenScadInfo:
    """Parse version and active library roots from ``openscad --info``."""

    version_match = _VERSION.search(output)
    if version_match is None or not version_match.group(1).strip():
        raise CadDependencyError("malformed OpenSCAD --info: missing version")

    lines = output.splitlines()
    user_library: Path | None = None
    library_paths: list[Path] | None = None
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("User Library Path:"):
            value = stripped.partition(":")[2].strip()
            if not value and index + 1 < len(lines):
                following = lines[index + 1].strip()
                if following and not _is_label(following):
                    value = following
                    index += 1
            if value:
                user_library = Path(value)
        elif stripped == "OpenSCAD library path:":
            library_paths = []
            index += 1
            while index < len(lines):
                value = lines[index].strip()
                if not value or _is_label(value):
                    break
                library_paths.append(Path(value))
                index += 1
            continue
        index += 1
    if not library_paths:
        raise CadDependencyError(
            "malformed OpenSCAD --info: missing or empty library path section"
        )
    return OpenScadInfo(
        version=version_match.group(1).strip(),
        user_library_path=user_library,
        library_paths=tuple(library_paths),
        raw_output=output,
    )


def query_openscad_info(
    executable: str | Path = "openscad", *, env: Mapping[str, str] | None = None
) -> OpenScadInfo:
    """Query OpenSCAD without invoking a shell and return parsed metadata."""

    argv = [str(executable), "--info"]
    try:
        completed = subprocess.run(
            argv,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as error:
        raise CadDependencyError(
            f"cannot run OpenSCAD --info using {executable}: {error}"
        ) from error
    if completed.returncode != 0:
        raise CadDependencyError(
            f"OpenSCAD --info failed with status {completed.returncode}: "
            f"{completed.stdout or ''}"
        )
    return parse_openscad_info(completed.stdout or "")


def content_hash(path: Path) -> str:
    """Return the SHA-256 digest of one regular file's exact bytes."""

    try:
        if not path.is_file():
            raise CadDependencyError(f"cannot hash non-file dependency {path}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise CadDependencyError(f"cannot hash dependency {path}: {error}") from error
