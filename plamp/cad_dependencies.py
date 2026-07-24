"""Deterministic parsing of OpenSCAD dependency and installation metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
from typing import Mapping
import weakref

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
class CadLibrary:
    name: str
    path: Path
    license: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class DependencyClosure:
    records: tuple[DependencyRecord, ...]
    model_root: Path
    repository_root: Path
    source_path: Path
    dirty: bool = False


@dataclass(frozen=True)
class StagedDependencies:
    root: Path
    records: tuple[DependencyRecord, ...]
    model_source: Path
    openscad_paths: tuple[Path, ...]


class _CleanupKey:
    pass


@dataclass
class _CleanupRecord:
    root: Path
    device: int
    inode: int
    parent_fd: int
    root_fd: int
    finalizer: weakref.finalize | None = None
    cleaned: bool = False


_CLEANUP_RECORDS: weakref.WeakKeyDictionary[_CleanupKey, _CleanupRecord] = (
    weakref.WeakKeyDictionary()
)
_CLEANUP_LOCK = threading.RLock()


@dataclass(frozen=True)
class DiscoveryEnvironment:
    """Repository tree used only to discover one job's dependency closure."""

    root: Path
    source_path: Path
    revision: str | None
    dirty: bool
    cleanup_root: Path | None
    _cleanup_key: _CleanupKey | None = field(default=None, repr=False, compare=False)

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


def geometry_define_argv(job: object, revision: str) -> tuple[str, ...]:
    """Build every geometry-affecting define shared by discovery and rendering."""

    arguments: list[str] = [
        "-D", f"revision_string={serialize_scad_value(revision)}",
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
            directories = sorted(
                (member for member in members if member.isdir()),
                key=lambda member: len(Path(member.name).parts),
                reverse=True,
            )
            for member in directories:
                os.chmod(destination / member.name, member.mode & 0o777)
    except (tarfile.TarError, OSError) as error:
        if isinstance(error, CadDependencyError):
            raise
        raise CadDependencyError(f"cannot extract Git discovery archive: {error}") from error


def _lexical_repository_path(root: Path, source_path: str | os.PathLike[str]) -> Path:
    supplied = Path(source_path)
    if supplied.is_absolute():
        source = Path(os.path.abspath(os.fspath(supplied)))
    else:
        if ".." in supplied.parts:
            raise CadDependencyError("CAD discovery source must be inside the repository")
        source = Path(os.path.abspath(os.fspath(root / supplied)))
    try:
        relative = source.relative_to(root)
    except ValueError as error:
        raise CadDependencyError("CAD discovery source must be inside the repository") from error
    if not relative.parts or ".." in relative.parts:
        raise CadDependencyError("CAD discovery source must be inside the repository")
    return relative


def _archived_regular_file(root: Path, relative: Path, revision: str) -> Path:
    """Validate a source through directory descriptors without following links."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0) | nofollow
    descriptors: list[int] = []
    try:
        current = os.open(root, directory_flags)
        descriptors.append(current)
        for component in relative.parts[:-1]:
            current = os.open(component, directory_flags, dir_fd=current)
            descriptors.append(current)
        source_fd = os.open(relative.name, flags | nofollow, dir_fd=current)
        descriptors.append(source_fd)
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            raise CadDependencyError(
                f"CAD discovery source {relative} is not a regular file in revision {revision}"
            )
    except FileNotFoundError as error:
        raise CadDependencyError(
            f"CAD discovery source {relative} is absent from revision {revision}"
        ) from error
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise CadDependencyError(
                f"unsafe CAD discovery source {relative} in revision {revision}"
            ) from error
        raise CadDependencyError(
            f"cannot validate CAD discovery source {relative} in revision {revision}: {error}"
        ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return root / relative


def _dirty_regular_file(root: Path, relative: Path) -> tuple[Path, int, os.stat_result]:
    """Open and validate a dirty source without permitting links or escapes."""

    lexical = root / relative
    try:
        before = lexical.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise CadDependencyError(f"CAD discovery source does not exist: {lexical}") from error
    if stat.S_ISLNK(before.st_mode):
        raise CadDependencyError(f"dirty CAD discovery source must not be a symlink: {lexical}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lexical, flags)
    except OSError as error:
        raise CadDependencyError(f"dirty CAD discovery source changed during validation: {lexical}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise CadDependencyError(
                f"dirty CAD discovery source must be a regular file: {lexical}"
            )
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise CadDependencyError(
                f"dirty CAD discovery source changed during validation: {lexical}"
            )
        resolved = lexical.resolve(strict=True)
        after = lexical.stat(follow_symlinks=False)
        if stat.S_ISLNK(after.st_mode) or (
            after.st_dev, after.st_ino
        ) != (opened.st_dev, opened.st_ino):
            raise CadDependencyError(
                f"dirty CAD discovery source changed during validation: {lexical}"
            )
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise CadDependencyError(
                f"dirty CAD discovery source must remain inside the repository: {lexical}"
            ) from error
        return resolved, descriptor, opened
    except BaseException:
        os.close(descriptor)
        raise


def _close_cleanup_descriptors(parent_fd: int, root_fd: int) -> None:
    for descriptor in (root_fd, parent_fd):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _register_owned_environment(
    cleanup: Path, source: Path, revision: str | None, dirty: bool
) -> DiscoveryEnvironment:
    parent_fd = os.open(
        cleanup.parent,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        root_fd = os.open(
            cleanup.name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0),
            dir_fd=parent_fd,
        )
    except BaseException:
        os.close(parent_fd)
        raise
    details = os.fstat(root_fd)
    key = _CleanupKey()
    record = _CleanupRecord(
        cleanup, details.st_dev, details.st_ino, parent_fd, root_fd
    )
    record.finalizer = weakref.finalize(
        key, _close_cleanup_descriptors, parent_fd, root_fd
    )
    with _CLEANUP_LOCK:
        _CLEANUP_RECORDS[key] = record
    return DiscoveryEnvironment(cleanup, source, revision, dirty, cleanup, key)


def _snapshot_dirty_repository(
    root: Path, relative_source: Path, source_fd: int, cleanup: Path
) -> Path:
    """Copy Git-visible dirty candidates without following working-tree links."""

    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise CadDependencyError(f"cannot enumerate dirty CAD snapshot: {error}") from error
    names = listed.decode("utf-8", errors="surrogateescape").split("\0")
    relative_names = {Path(name) for name in names if name}
    relative_names.add(relative_source)
    for relative in sorted(relative_names, key=lambda item: item.as_posix()):
        if relative.is_absolute() or ".." in relative.parts:
            raise CadDependencyError(f"unsafe dirty CAD snapshot path: {relative}")
        descriptor: int
        close_descriptor = False
        if relative == relative_source:
            descriptor = source_fd
        else:
            _, descriptor, _ = _dirty_regular_file(root, relative)
            close_descriptor = True
        destination = cleanup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with os.fdopen(os.dup(descriptor), "rb") as input_file, destination.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file)
        finally:
            if close_descriptor:
                os.close(descriptor)
    return cleanup / relative_source


def _clear_cleanup_descriptor(descriptor: int) -> None:
    """Delete contents relative to the retained owned-root descriptor."""
    from plamp.cad_fs import remove_owned_entry_at

    for name in tuple(os.listdir(descriptor)):
        details = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if not remove_owned_entry_at(
            descriptor, name, (details.st_dev, details.st_ino)
        ):
            raise CadDependencyError(f"cleanup child changed during deletion: {name}")


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
    relative_source = (
        _lexical_repository_path(root, source_path)
        if source_path is not None else None
    )
    if dirty:
        if revision_label is None or not revision_label.strip():
            raise ValueError("dirty CAD dependency discovery requires an explicit revision label")
        if relative_source is None:
            raise CadDependencyError("dirty CAD dependency discovery requires a source file")
        _source, source_fd, _source_stat = _dirty_regular_file(root, relative_source)
        cleanup = Path(tempfile.mkdtemp(prefix="plamp-cad-discovery-dirty-"))
        try:
            staged_source = _snapshot_dirty_repository(
                root, relative_source, source_fd, cleanup
            )
            return _register_owned_environment(cleanup, staged_source, None, True)
        except BaseException:
            shutil.rmtree(cleanup, ignore_errors=True)
            raise
        finally:
            os.close(source_fd)

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
        archived_source = (
            cleanup if relative_source is None
            else _archived_regular_file(cleanup, relative_source, commit)
        )
        return _register_owned_environment(
            cleanup, archived_source, commit, False
        )
    except BaseException:
        shutil.rmtree(cleanup, ignore_errors=True)
        raise


def cleanup_discovery_environment(environment: DiscoveryEnvironment) -> None:
    """Remove an archived discovery tree; dirty working trees are never removed."""

    if environment.cleanup_root is None and environment._cleanup_key is None:
        return
    key = environment._cleanup_key
    if key is None:
        raise CadDependencyError("CAD discovery cleanup root is not owned by this process")
    with _CLEANUP_LOCK:
        record = _CLEANUP_RECORDS.get(key)
        if record is None:
            raise CadDependencyError("CAD discovery cleanup root is not owned by this process")
        if record.cleaned:
            return
        if environment.cleanup_root != record.root or environment.root != record.root:
            raise CadDependencyError("CAD discovery cleanup root does not match its owner")
        opened = os.fstat(record.root_fd)
        if not stat.S_ISDIR(opened.st_mode) or (
            opened.st_dev, opened.st_ino
        ) != (record.device, record.inode):
            raise CadDependencyError("CAD discovery cleanup descriptor lost ownership")
        _clear_cleanup_descriptor(record.root_fd)
        from plamp.cad_fs import remove_owned_path

        if not remove_owned_path(record.root, (record.device, record.inode)):
            raise CadDependencyError("owned CAD discovery cleanup root could not be removed safely")
        if record.finalizer is not None:
            record.finalizer()
        record.cleaned = True


# Failure diagnostics deliberately expose only this allowlist, never the full
# process environment (which commonly contains credentials).
_DISCOVERY_ENV_DIAGNOSTIC_KEYS = ("OPENSCADPATH",)


def _discovery_context(
    argv: tuple[str, ...], cwd: Path, env: Mapping[str, str]
) -> str:
    visible = {key: env[key] for key in _DISCOVERY_ENV_DIAGNOSTIC_KEYS if key in env}
    return f"argv={argv!r}; cwd={cwd}; env={visible!r}"


def run_dependency_discovery(
    openscad: str | os.PathLike[str],
    environment: DiscoveryEnvironment,
    job: object,
    output_dir: str | os.PathLike[str],
    *,
    env: Mapping[str, str],
    revision: str,
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
        *geometry_define_argv(job, revision), str(environment.source_path),
    )
    cwd = environment.source_path.parent
    context = _discovery_context(argv, cwd, env)
    try:
        completed = subprocess.run(
            list(argv), cwd=cwd, env=dict(env), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
    except OSError as error:
        raise CadDependencyError(
            f"cannot run OpenSCAD dependency discovery: {error}; {context}"
        ) from error
    output = completed.stdout or ""
    if completed.returncode != 0:
        raise CadDependencyError(
            f"OpenSCAD dependency discovery failed with status {completed.returncode}: "
            f"{output}; {context}"
        )
    if not dependencies.is_file():
        raise CadDependencyError(
            f"OpenSCAD dependency discovery did not produce {dependencies}: "
            f"{output}; {context}"
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
            _reject_link_components(candidate)
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


def _open_regular_no_follow(path: Path) -> tuple[int, os.stat_result]:
    absolute = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        current = os.open(absolute.anchor, directory_flags)
        descriptors.append(current)
        for component in absolute.parts[1:-1]:
            current = os.open(component, directory_flags, dir_fd=current)
            descriptors.append(current)
        result = os.open(
            absolute.name, flags | getattr(os, "O_NOFOLLOW", 0), dir_fd=current
        )
        details = os.fstat(result)
        if not stat.S_ISREG(details.st_mode):
            os.close(result)
            raise CadDependencyError(f"cannot open non-file dependency {path}")
        return result, details
    except OSError as error:
        raise CadDependencyError(f"cannot safely open dependency {path}: {error}") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def content_hash(path: Path) -> str:
    """Return the SHA-256 digest of one regular file's exact bytes."""

    try:
        descriptor, _details = _open_regular_no_follow(path)
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise CadDependencyError(f"cannot hash dependency {path}: {error}") from error


_ASSET_SUFFIXES = frozenset({".stl", ".svg", ".dxf", ".png"})
_LIBRARY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _reject_link_components(path: Path) -> None:
    """Reject links in an existing absolute path before canonicalizing it."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    try:
        for component in absolute.parts[1:]:
            current /= component
            if stat.S_ISLNK(current.stat(follow_symlinks=False).st_mode):
                raise CadDependencyError(f"unsafe symlink CAD dependency: {path}")
    except FileNotFoundError as error:
        raise CadDependencyError(f"CAD dependency does not exist: {path}") from error


def _regular_files_without_links(root: Path) -> tuple[Path, ...]:
    """Enumerate a portable folder snapshot while rejecting every link/special."""

    rows: list[Path] = []
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            candidate = directory_path / name
            details = candidate.stat(follow_symlinks=False)
            if stat.S_ISLNK(details.st_mode):
                raise CadDependencyError(f"unsafe symlink in CAD model folder: {candidate}")
            if not stat.S_ISDIR(details.st_mode):
                raise CadDependencyError(f"unsafe special entry in CAD model folder: {candidate}")
        for name in files:
            candidate = directory_path / name
            details = candidate.stat(follow_symlinks=False)
            if stat.S_ISLNK(details.st_mode):
                raise CadDependencyError(f"unsafe symlink in CAD model folder: {candidate}")
            if not stat.S_ISREG(details.st_mode):
                raise CadDependencyError(f"unsafe special entry in CAD model folder: {candidate}")
            rows.append(candidate)
    return tuple(sorted(rows, key=lambda item: item.relative_to(root).as_posix()))


def classify_dependencies(
    *,
    dependencies: tuple[Path, ...],
    model_root: Path,
    repository_root: Path,
    declared_libraries: Mapping[str, CadLibrary],
    openscad_library_roots: tuple[Path, ...],
    selected_revision: str | None,
) -> DependencyClosure:
    """Classify a discovered closure by its most-specific approved root."""

    repository = repository_root.resolve(strict=True)
    model = model_root.resolve(strict=True)
    if _relative_to(model, repository) is None:
        raise CadDependencyError("CAD model root must remain inside the repository")
    libraries: list[tuple[str, CadLibrary, Path]] = []
    for name, declaration in declared_libraries.items():
        if name != declaration.name or _LIBRARY_NAME.fullmatch(name) is None:
            raise CadDependencyError(f"unsafe or inconsistent CAD library name: {name!r}")
        root = declaration.path.resolve(strict=True)
        if not root.is_dir():
            raise CadDependencyError(f"declared CAD library is not a directory: {root}")
        libraries.append((name, declaration, root))
    install_roots: list[Path] = []
    for raw_root in openscad_library_roots:
        root = raw_root.resolve(strict=True)
        if not root.is_dir():
            raise CadDependencyError(f"OpenSCAD library root is not a directory: {root}")
        if root not in install_roots:
            install_roots.append(root)

    discovered_rows: list[Path] = []
    for item in dependencies:
        _reject_link_components(Path(item))
        discovered_rows.append(Path(item).resolve(strict=True))
    discovered = tuple(discovered_rows)
    if not discovered:
        raise CadDependencyError("OpenSCAD dependency closure is empty")
    source_path = next((item for item in discovered if _relative_to(item, model) is not None), None)
    if source_path is None:
        raise CadDependencyError("dependency closure does not contain the selected model source")
    ordered = list(discovered)
    seen = set(ordered)
    for item in _regular_files_without_links(model):
        if item not in seen:
            ordered.append(item)
            seen.add(item)

    records: list[DependencyRecord] = []
    for source in ordered:
        try:
            details = source.stat(follow_symlinks=False)
        except OSError as error:
            raise CadDependencyError(f"cannot inspect CAD dependency {source}: {error}") from error
        if not stat.S_ISREG(details.st_mode):
            raise CadDependencyError(f"unsafe non-regular CAD dependency: {source}")

        candidates: list[tuple[int, int, str, str, Path, str | None, str | None]] = []
        relative = _relative_to(source, model)
        if relative is not None:
            candidates.append((len(model.parts), 0, "model-local", relative.as_posix(),
                               Path("repository") / model.relative_to(repository) / relative,
                               selected_revision, None))
        for name, declaration, root in libraries:
            relative = _relative_to(source, root)
            if relative is not None:
                candidates.append((len(root.parts), 1, "declared-shared",
                                   f"{name}/{relative.as_posix()}",
                                   Path("libraries") / name / relative,
                                   declaration.revision, declaration.license))
        relative = _relative_to(source, repository)
        if relative is not None:
            candidates.append((len(repository.parts), 2, "repository-local",
                               relative.as_posix(), Path("repository") / relative,
                               selected_revision, None))
        for index, root in enumerate(install_roots, 1):
            relative = _relative_to(source, root)
            if relative is not None:
                candidates.append((len(root.parts), 3, "built-in",
                                   f"openscad-{index}/{relative.as_posix()}",
                                   Path("libraries") / f"openscad-{index}" / relative,
                                   None, None))
        if not candidates:
            raise CadDependencyError(
                f"undeclared host CAD dependency {source}; declare its library in the system manifest"
            )
        _length, _priority, classification, logical, archive, revision, license_name = min(
            candidates, key=lambda row: (-row[0], row[1])
        )
        records.append(DependencyRecord(
            source_path=source, classification=classification,
            logical_name=logical, archive_path=archive,
            content_hash=content_hash(source), git_revision=revision,
            license=license_name, asset=source.suffix.lower() in _ASSET_SUFFIXES,
        ))
    return DependencyClosure(
        tuple(records), model, repository, source_path, selected_revision is None
    )


def _copy_verified(record: DependencyRecord, stage: Path, stage_fd: int) -> None:
    destination = stage / record.archive_path
    try:
        destination.relative_to(stage)
    except ValueError as error:
        raise CadDependencyError(f"unsafe dependency archive path: {record.archive_path}") from error
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_fd = os.dup(stage_fd)
    try:
        for component in record.archive_path.parts[:-1]:
            try:
                os.mkdir(component, 0o755, dir_fd=parent_fd)
            except FileExistsError:
                pass
            next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        source_fd, details = _open_regular_no_follow(record.source_path)
        try:
            digest = hashlib.sha256()
            output_fd = os.open(
                record.archive_path.name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                stat.S_IMODE(details.st_mode) & 0o777,
                dir_fd=parent_fd,
            )
            with os.fdopen(os.dup(source_fd), "rb") as source, os.fdopen(output_fd, "r+b") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
                os.fchmod(output.fileno(), stat.S_IMODE(details.st_mode) & 0o777)
                output.flush()
                output.seek(0)
                copied = hashlib.sha256()
                for chunk in iter(lambda: output.read(1024 * 1024), b""):
                    copied.update(chunk)
        finally:
            os.close(source_fd)
    except (OSError, FileExistsError) as error:
        raise CadDependencyError(f"cannot stage CAD dependency {record.source_path}: {error}") from error
    finally:
        os.close(parent_fd)
    if digest.hexdigest() != record.content_hash or copied.hexdigest() != record.content_hash:
        raise CadDependencyError(f"CAD dependency changed while staging: {record.source_path}")


def stage_dependency_closure(
    closure: DependencyClosure, destination: str | os.PathLike[str]
) -> StagedDependencies:
    """Copy a classified closure to deterministic repository/library roots."""

    archive_paths: set[Path] = set()
    for record in closure.records:
        archive = record.archive_path
        parts = archive.parts
        if (
            archive.is_absolute() or not parts
            or any(
                component in ("", ".", "..")
                or "\\" in component or ":" in component or "\x00" in component
                for component in parts
            )
        ):
            raise CadDependencyError(f"unsafe dependency archive path: {archive}")
        if archive in archive_paths:
            raise CadDependencyError(f"duplicate dependency archive path: {archive}")
        archive_paths.add(archive)
    for archive in archive_paths:
        for length in range(1, len(archive.parts)):
            ancestor = Path(*archive.parts[:length])
            if ancestor in archive_paths:
                raise CadDependencyError(
                    f"dependency archive path collision: file {ancestor} "
                    f"is also a directory required by {archive}"
                )

    stage = Path(destination).absolute()
    if stage.exists() and (stage.is_symlink() or not stage.is_dir()):
        raise CadDependencyError(f"unsafe CAD dependency staging root: {stage}")
    stage.mkdir(parents=True, exist_ok=True)
    try:
        stage_fd = os.open(
            stage,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise CadDependencyError(f"cannot safely open CAD dependency staging root: {error}") from error
    stage_identity = os.fstat(stage_fd)
    try:
        for record in closure.records:
            _copy_verified(record, stage, stage_fd)
    finally:
        os.close(stage_fd)
    final_identity = stage.stat(follow_symlinks=False)
    if stat.S_ISLNK(final_identity.st_mode) or (
        final_identity.st_dev, final_identity.st_ino
    ) != (stage_identity.st_dev, stage_identity.st_ino):
        raise CadDependencyError("CAD dependency staging root changed while staging")
    source_relative = closure.source_path.relative_to(closure.repository_root)
    openscad_paths = [stage / "libraries"]
    for record in closure.records:
        if record.classification not in ("declared-shared", "built-in"):
            continue
        root = stage / Path(*record.archive_path.parts[:2])
        if root not in openscad_paths:
            openscad_paths.append(root)
    return StagedDependencies(
        stage, closure.records, stage / "repository" / source_relative,
        tuple(openscad_paths),
    )


def verify_staged_dependencies(
    *,
    expected: tuple[DependencyRecord, ...],
    actual: tuple[Path, ...],
    staged_root: str | os.PathLike[str],
) -> None:
    """Verify a final render resolved the exact staged logical closure."""

    root = Path(staged_root).resolve(strict=True)
    expected_by_archive = {record.archive_path: record for record in expected}
    actual_by_archive: dict[Path, Path] = {}
    for supplied in actual:
        _reject_link_components(Path(supplied))
        resolved = Path(supplied).resolve(strict=True)
        try:
            archive_path = resolved.relative_to(root)
        except ValueError as error:
            raise CadDependencyError(
                f"final dependency outside staged dependency closure: {resolved}"
            ) from error
        if archive_path in actual_by_archive:
            continue
        record = expected_by_archive.get(archive_path)
        if record is None:
            raise CadDependencyError(
                f"final dependency logical closure mismatch: unexpected {archive_path}"
            )
        if content_hash(resolved) != record.content_hash:
            raise CadDependencyError(
                f"final dependency content hash mismatch: {archive_path}"
            )
        actual_by_archive[archive_path] = resolved
    missing = sorted(
        set(expected_by_archive).difference(actual_by_archive),
        key=lambda item: item.as_posix(),
    )
    if missing:
        raise CadDependencyError(
            "final dependency logical closure mismatch: missing "
            + ", ".join(item.as_posix() for item in missing)
        )
