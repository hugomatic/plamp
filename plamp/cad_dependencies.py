"""Deterministic parsing of OpenSCAD dependency and installation metadata."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
from typing import Mapping


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
        drive_colon = (
            len(target) == 1
            and target[0].isalpha()
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
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = working_directory / candidate
        try:
            resolved = candidate.resolve(strict=True)
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
