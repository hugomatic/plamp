"""Safe, project-neutral scaffolding for local CAD parts."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys

from plamp.cad_metadata import CadMetadataError, parse_cad_document


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_SCAD_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN = "__PLAMP_PART__"
_VIEW_ASSIGNMENT = re.compile(
    r'^\s*view\s*=\s*"(?P<default>[^"]+)"\s*;\s*//\s*\[(?P<choices>[^]]*)\]',
    re.MULTILINE,
)
_METADATA = re.compile(r"/\*\s*generate\.json(?P<body>.*?)\*/", re.DOTALL)


class CadSelectionError(ValueError):
    """A requested scaffold or selectable template violates the CAD contract."""


class CadDestinationExistsError(FileExistsError):
    """The requested final part path already exists or won publication."""


@dataclass(frozen=True)
class CadTemplate:
    name: str
    path: Path
    device: int | None = None
    inode: int | None = None


@dataclass(frozen=True)
class CreatedPart:
    part: str
    template: str
    directory: Path
    scad_path: Path


def _validate_name(name: str, kind: str) -> None:
    if Path(name).name != name or _SAFE_NAME.fullmatch(name) is None:
        raise CadSelectionError(
            f"invalid {kind} name {name!r}; names must match {_SAFE_NAME.pattern}"
        )


def _part_identifier(part_name: str) -> str:
    identifier = part_name.replace("-", "_")
    if _SCAD_IDENTIFIER.fullmatch(identifier) is None:
        raise CadSelectionError(
            f"invalid OpenSCAD identifier {identifier!r} derived from part {part_name!r}"
        )
    return identifier


def _resolved_beneath(path: Path, root: Path, description: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise CadSelectionError(
            f"{description} escapes expected root: {path}"
        ) from None
    return resolved


def _regular_identity(path: Path) -> tuple[int, int] | None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(details.st_mode):
        return None
    return details.st_dev, details.st_ino


def discover_templates(repo_root: Path) -> tuple[CadTemplate, ...]:
    """Discover selectable SCAD templates beneath ``things/3d_template``."""

    repository = Path(repo_root).resolve()
    things_root = repository / "things"
    template_root = things_root / "3d_template"
    if not template_root.is_dir():
        raise FileNotFoundError(f"CAD template root does not exist: {template_root}")
    _resolved_beneath(things_root, repository, "things directory")
    resolved_template_root = _resolved_beneath(
        template_root, things_root, "CAD template root"
    )

    candidates: list[tuple[str, Path]] = []
    root_template = template_root / "cad.scad"
    if root_template.exists() and _regular_identity(root_template) is not None:
        candidates.append(("cad", root_template))
    named_root = template_root / "scad"
    if named_root.is_dir():
        for path in named_root.iterdir():
            if path.suffix == ".scad" and _regular_identity(path) is not None:
                candidates.append((path.stem, path))

    discovered: dict[str, CadTemplate] = {}
    for name, path in candidates:
        _validate_name(name, "template")
        _resolved_beneath(path, resolved_template_root, "CAD template")
        if name in discovered:
            raise CadSelectionError(f"duplicate CAD template name: {name}")
        identity = _regular_identity(path)
        if identity is None:
            raise OSError(errno.ESTALE, f"CAD template identity changed: {path}")
        discovered[name] = CadTemplate(name, path, *identity)
    return tuple(discovered[name] for name in sorted(discovered))


def _read_template(template_root: Path, template: CadTemplate) -> bytes:
    """Read a discovered regular file without following replacement symlinks."""

    try:
        relative = template.path.relative_to(template_root)
    except ValueError:
        raise CadSelectionError(
            f"CAD template escapes expected root: {template.path}"
        ) from None
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0)
    descriptors: list[int] = []
    try:
        current = os.open(template_root, directory_flags)
        descriptors.append(current)
        for component in relative.parts[:-1]:
            current = os.open(component, directory_flags, dir_fd=current)
            descriptors.append(current)
        descriptor = os.open(relative.name, flags, dir_fd=current)
        descriptors.append(descriptor)
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise OSError(errno.EINVAL, f"CAD template is not a regular file: {template.path}")
        if template.device is None or template.inode is None:
            raise OSError(errno.ESTALE, f"CAD template has no discovered identity: {template.path}")
        if (details.st_dev, details.st_ino) != (template.device, template.inode):
            raise OSError(errno.ESTALE, f"CAD template identity changed: {template.path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _metadata(source: str, description: str) -> dict[str, object]:
    match = _METADATA.search(source)
    if match is None:
        raise CadSelectionError(f"{description} has no generate.json metadata")
    try:
        value = json.loads(match.group("body"))
    except (json.JSONDecodeError, ValueError) as error:
        raise CadSelectionError(f"{description} has invalid generate.json metadata: {error}") from None
    if not isinstance(value, dict):
        raise CadSelectionError(f"{description} generate.json metadata must be an object")
    return value


def _validate_contract(
    source: str, identifier: str, description: str, *, allow_reserved: bool = False
) -> None:
    if not allow_reserved and _TOKEN in source:
        raise CadSelectionError(f"{description} retains reserved token {_TOKEN}")
    view = _VIEW_ASSIGNMENT.search(source)
    expected_views = (identifier, "assembly")
    if view is None:
        raise CadSelectionError(f"{description} has no declared view choices")
    choices = tuple(item.strip() for item in view.group("choices").split(",") if item.strip())
    if view.group("default") != identifier or choices != expected_views:
        raise CadSelectionError(
            f"{description} must default to {identifier!r} with exactly {expected_views!r}"
        )

    metadata = _metadata(source, description)
    raw_views = metadata.get("views")
    if (
        not isinstance(raw_views, dict)
        or set(raw_views) != set(expected_views)
        or any(not isinstance(raw_views[name], dict) for name in expected_views)
    ):
        raise CadSelectionError(f"{description} metadata must describe both declared views")
    presets = metadata.get("presets")
    if not isinstance(presets, dict) or not presets:
        raise CadSelectionError(f"{description} must declare at least one preset")
    default_preset = metadata.get("default_preset")
    if not isinstance(default_preset, str) or default_preset not in presets:
        raise CadSelectionError(f"{description} must select a declared default preset")
    default_value = presets[default_preset]
    if not isinstance(default_value, dict) or default_value.get("items") != [
        f"view:{identifier}",
        "view:assembly",
    ]:
        raise CadSelectionError(
            f"{description} default preset must contain both views in declared order"
        )
    for preset_name, preset in presets.items():
        if not isinstance(preset, dict) or not isinstance(preset.get("items", []), list):
            raise CadSelectionError(f"{description} preset {preset_name!r} is invalid")
        for item in preset.get("items", []):
            if isinstance(item, str) and item.startswith("view:") and item[5:] not in expected_views:
                raise CadSelectionError(
                    f"{description} preset {preset_name!r} references undeclared view {item[5:]!r}"
                )

    for suffix in ("_positive", "_negative", ""):
        declaration = rf"\bmodule\s+{re.escape(identifier + suffix)}\s*\(\s*\)"
        if re.search(declaration, source) is None:
            raise CadSelectionError(
                f"{description} is missing module {identifier + suffix}()"
            )
    if re.search(r"\bmodule\s+part(?:_positive|_negative)?\s*\(", source):
        raise CadSelectionError(f"{description} retains a forbidden generic part module")
    for view_name in expected_views:
        dispatch = re.compile(
            rf'\b(?:if|else\s+if)\s*\(\s*view\s*==\s*"{re.escape(view_name)}"\s*\)\s*\{{[^}}]*\b{re.escape(identifier)}\s*\(\s*\)\s*;',
            re.DOTALL,
        )
        if dispatch.search(source) is None:
            raise CadSelectionError(
                f"{description} view {view_name!r} must call {identifier}()"
            )


def _substitute_template(raw: bytes, identifier: str, description: str) -> str:
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CadSelectionError(f"{description} is not valid UTF-8: {error}") from None
    if _TOKEN not in source:
        raise CadSelectionError(f"{description} has no reserved token {_TOKEN}")
    _validate_contract(source, _TOKEN, description, allow_reserved=True)
    generated = source.replace(_TOKEN, identifier)
    _validate_contract(generated, identifier, description)
    return generated


def _reject_normalized_collision(things_root: Path, part_name: str, identifier: str) -> None:
    for sibling in things_root.iterdir():
        if sibling.name == part_name or not sibling.is_dir() or _SAFE_NAME.fullmatch(sibling.name) is None:
            continue
        sibling_identifier = sibling.name.replace("-", "_")
        if _SCAD_IDENTIFIER.fullmatch(sibling_identifier) and sibling_identifier == identifier:
            raise CadSelectionError(
                f"part {part_name!r} conflicts with existing part {sibling.name!r}; shared OpenSCAD stem {identifier!r}"
            )


def _make_staging(things_root: Path, part_name: str) -> Path:
    for _attempt in range(100):
        staging = things_root / f".{part_name}.staging-{secrets.token_hex(6)}"
        try:
            os.mkdir(staging, 0o777)
            return staging
        except FileExistsError:
            continue
    raise FileExistsError(errno.EEXIST, "could not allocate unique CAD staging directory")


def _write_exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(errno.EIO, f"short write creating {path}")
            view = view[written:]
    finally:
        os.close(descriptor)


def _publish_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish ``source`` without replacing ``destination``."""

    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform.startswith("linux"):
        rename = getattr(library, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "renameat2 is unavailable")
        result = rename(-100, source_bytes, -100, destination_bytes, 1)
    elif sys.platform == "darwin":
        rename = getattr(library, "renamex_np", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "renamex_np is unavailable")
        result = rename(source_bytes, destination_bytes, 0x00000004)
    else:
        raise OSError(errno.ENOTSUP, f"atomic no-replace rename unsupported on {sys.platform}")
    if result != 0:
        value = ctypes.get_errno()
        raise OSError(value, os.strerror(value), destination)


def create_part(repo_root: Path, part_name: str, template_name: str) -> CreatedPart:
    """Atomically create one part directory from a validated SCAD template."""

    _validate_name(part_name, "part")
    _validate_name(template_name, "template")
    identifier = _part_identifier(part_name)
    templates = {item.name: item for item in discover_templates(repo_root)}
    if template_name not in templates:
        choices = ", ".join(sorted(templates)) or "none"
        raise CadSelectionError(
            f"unknown CAD template {template_name!r}; available: {choices}"
        )

    repository = Path(repo_root).resolve()
    things_root = repository / "things"
    template_root = things_root / "3d_template"
    _resolved_beneath(things_root, repository, "things directory")
    destination = things_root / part_name
    _resolved_beneath(destination, things_root, "part destination")
    _reject_normalized_collision(things_root, part_name, identifier)
    if destination.exists() or destination.is_symlink():
        raise CadDestinationExistsError(
            f"CAD part destination already exists: {destination}"
        )

    template = templates[template_name]
    raw = _read_template(template_root, template)
    generated = _substitute_template(raw, identifier, str(template.path))

    staging = _make_staging(things_root, part_name)
    staged_scad = staging / f"{part_name}.scad"
    try:
        _write_exclusive(staged_scad, generated.encode("utf-8"))
        try:
            staged_document = parse_cad_document(staged_scad)
        except (CadMetadataError, UnicodeError, ValueError) as error:
            raise CadSelectionError(f"staged CAD part is invalid: {error}") from None
        if not staged_document.metadata_snapshot:
            raise CadSelectionError(f"staged CAD part has no generation metadata: {staged_scad}")
        _validate_contract(generated, identifier, str(staged_scad))
        try:
            _publish_noreplace(staging, destination)
        except FileExistsError:
            raise CadDestinationExistsError(
                f"CAD part destination already exists: {destination}"
            ) from None
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return CreatedPart(
        part=part_name,
        template=template_name,
        directory=destination,
        scad_path=destination / f"{part_name}.scad",
    )
