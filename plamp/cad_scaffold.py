"""Safe, project-neutral scaffolding for local CAD parts."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys

from plamp.cad_model import CadMetadataError as CadModelMetadataError, load_model
from plamp.cad_system import CadSystem, load_system


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_SCAD_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN = "__PLAMP_PART__"

class CadSelectionError(ValueError):
    """A requested scaffold or selectable template violates the CAD contract."""


class CadDestinationExistsError(FileExistsError):
    """The requested final part path already exists or won publication."""


@dataclass(frozen=True)
class CadTemplate:
    name: str
    path: Path
    sidecar_path: Path
    description: str
    device: int | None = None
    inode: int | None = None
    sidecar_device: int | None = None
    sidecar_inode: int | None = None


@dataclass(frozen=True)
class CreatedModel:
    model_id: str
    template: str
    directory: Path
    scad_path: Path
    sidecar_path: Path


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
        sidecar_path = path.with_suffix(".cad.json")
        sidecar_identity = _regular_identity(sidecar_path) if sidecar_path.exists() else None
        if sidecar_identity is None:
            raise CadSelectionError(f"CAD template {name!r} has no regular sidecar: {sidecar_path}")
        _resolved_beneath(sidecar_path, resolved_template_root, "CAD template sidecar")
        provisional = CadTemplate(
            name, path, sidecar_path, "", *identity, *sidecar_identity
        )
        try:
            sidecar = json.loads(
                _read_template_sidecar(resolved_template_root, provisional).decode("utf-8")
            )
        except (UnicodeError, json.JSONDecodeError) as error:
            raise CadSelectionError(f"CAD template sidecar is invalid: {sidecar_path}: {error}") from None
        description = sidecar.get("description") if isinstance(sidecar, dict) else None
        if not isinstance(description, str) or not description.strip():
            raise CadSelectionError(f"CAD template {name!r} requires a description")
        discovered[name] = CadTemplate(
            name, path, sidecar_path, description, *identity, *sidecar_identity
        )
    return tuple(discovered[name] for name in sorted(discovered))


def _read_template(template_root: Path, template: CadTemplate) -> bytes:
    """Read a discovered regular file without following replacement symlinks."""

    return _read_regular_file(
        template_root, template.path, template.device, template.inode,
        "CAD template",
    )


def _read_regular_file(template_root: Path, path: Path, device: int | None,
                       inode: int | None, description: str) -> bytes:

    try:
        relative = path.relative_to(template_root)
    except ValueError:
        raise CadSelectionError(
            f"{description} escapes expected root: {path}"
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
            raise OSError(errno.EINVAL, f"{description} is not a regular file: {path}")
        if device is None or inode is None:
            raise OSError(errno.ESTALE, f"{description} has no discovered identity: {path}")
        if (details.st_dev, details.st_ino) != (device, inode):
            raise OSError(errno.ESTALE, f"{description} identity changed: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read_template_sidecar(template_root: Path, template: CadTemplate) -> bytes:
    return _read_regular_file(
        template_root, template.sidecar_path, template.sidecar_device,
        template.sidecar_inode, "CAD template sidecar",
    )




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


def _substitute_pair(raw_scad: bytes, raw_sidecar: bytes, model_id: str,
                     template: CadTemplate) -> tuple[bytes, bytes]:
    identifier = _part_identifier(model_id)
    try:
        scad = raw_scad.decode("utf-8")
        sidecar_text = raw_sidecar.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CadSelectionError(f"CAD template is not valid UTF-8: {error}") from None
    if _TOKEN not in scad or _TOKEN not in sidecar_text:
        raise CadSelectionError(
            f"CAD template {template.name!r} must use {_TOKEN} in both files"
        )
    generated_scad = scad.replace(_TOKEN, identifier)
    generated_sidecar = sidecar_text.replace(_TOKEN, identifier)
    try:
        value = json.loads(generated_sidecar)
    except json.JSONDecodeError as error:
        raise CadSelectionError(f"generated model sidecar is invalid: {error}") from None
    if not isinstance(value, dict):
        raise CadSelectionError("generated model sidecar must be an object")
    value["name"] = model_id
    value["source"] = f"{model_id}.scad"
    return generated_scad.encode("utf-8"), (
        json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _replace_system_manifest(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{secrets.token_hex(6)}")
    try:
        _write_exclusive(temporary, data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _restore_system_manifest(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.restore-{secrets.token_hex(6)}")
    try:
        _write_exclusive(temporary, data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _validate_prospective_manifest(system_path: Path, repository: Path,
                                   manifest: dict[str, object], model_id: str,
                                   staged_sidecar: Path) -> None:
    prospective = json.loads(json.dumps(manifest))
    prospective.setdefault("models", {})[model_id] = staged_sidecar.relative_to(
        repository
    ).as_posix()
    temporary = system_path.with_name(
        f".{system_path.name}.prospective-{secrets.token_hex(6)}"
    )
    try:
        _write_exclusive(
            temporary,
            (json.dumps(prospective, indent=2, ensure_ascii=False) + "\n").encode(
                "utf-8"
            ),
        )
        load_system(temporary, repository)
    finally:
        if temporary.exists():
            temporary.unlink()


def _directory_identity(path: Path) -> tuple[int, int]:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(details.st_mode):
        raise OSError(errno.ENOTDIR, f"published CAD model is not a directory: {path}")
    return details.st_dev, details.st_ino


def _exchange_paths(first: Path, second: Path) -> None:
    """Atomically exchange two paths where the host kernel supports it."""

    if not sys.platform.startswith("linux"):
        raise _AtomicExchangeUnsupported("atomic rollback exchange requires Linux renameat2")
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise _AtomicExchangeUnsupported("renameat2 is unavailable")
    result = rename(-100, os.fsencode(first), -100, os.fsencode(second), 2)
    if result != 0:
        value = ctypes.get_errno()
        if value in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
            raise _AtomicExchangeUnsupported(os.strerror(value))
        raise OSError(value, os.strerror(value))


class _AtomicExchangeUnsupported(OSError):
    pass


def _clear_directory_descriptor(descriptor: int) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    for name in os.listdir(descriptor):
        details = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISDIR(details.st_mode):
            child = os.open(
                name, flags | getattr(os, "O_DIRECTORY", 0), dir_fd=descriptor
            )
            try:
                child_details = os.fstat(child)
                if (child_details.st_dev, child_details.st_ino) != (
                    details.st_dev, details.st_ino
                ):
                    raise OSError(errno.ESTALE, f"rollback child changed: {name}")
                _clear_directory_descriptor(child)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=descriptor)
        else:
            os.unlink(name, dir_fd=descriptor)


def _clear_claimed_directory(path: Path, identity: tuple[int, int]) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags | getattr(os, "O_DIRECTORY", 0))
    try:
        details = os.fstat(descriptor)
        if (details.st_dev, details.st_ino) != identity:
            raise OSError(errno.ESTALE, f"rollback claim identity changed: {path}")
        _clear_directory_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _final_remove_claimed_directory(path: Path, identity: tuple[int, int]) -> bool:
    placeholder = path.with_name(f".{path.name}.final-{secrets.token_hex(6)}")
    os.mkdir(placeholder)
    placeholder_identity = _directory_identity(placeholder)
    exchanged = False
    try:
        _exchange_paths(path, placeholder)
        exchanged = True
        if _directory_identity(placeholder) != identity:
            _exchange_paths(path, placeholder)
            exchanged = False
            return False
        os.rmdir(placeholder)
        exchanged = False
        os.rmdir(path)
        return True
    finally:
        if exchanged:
            try:
                _exchange_paths(path, placeholder)
            except OSError:
                pass
        if placeholder.exists():
            try:
                if _directory_identity(placeholder) == placeholder_identity:
                    os.rmdir(placeholder)
            except OSError:
                pass


def _claim_and_remove(candidate: Path, identity: tuple[int, int]) -> bool:
    placeholder = candidate.with_name(
        f".{candidate.name}.rollback-{secrets.token_hex(6)}"
    )
    os.mkdir(placeholder)
    placeholder_identity = _directory_identity(placeholder)
    exchanged = False
    try:
        _exchange_paths(candidate, placeholder)
        exchanged = True
        if _directory_identity(placeholder) != identity:
            _exchange_paths(candidate, placeholder)
            exchanged = False
            return False
        _clear_claimed_directory(placeholder, identity)
        if _final_remove_claimed_directory(placeholder, identity):
            os.rmdir(candidate)
            exchanged = False
            return True
        if _directory_identity(candidate) == placeholder_identity:
            _exchange_paths(candidate, placeholder)
            exchanged = False
        return False
    finally:
        if exchanged and placeholder.exists():
            try:
                _exchange_paths(candidate, placeholder)
            except OSError:
                pass
        if placeholder.exists():
            try:
                if _directory_identity(placeholder) == placeholder_identity:
                    os.rmdir(placeholder)
            except OSError:
                pass


def _remove_owned_directory(path: Path, identity: tuple[int, int]) -> bool:
    """Atomically claim and remove only this transaction's published inode.

    Linux uses ``renameat2(RENAME_EXCHANGE)``. Other kernels fail safely and
    leave the owned directory in place rather than risk deleting another path.
    """

    try:
        for candidate in (path,):
            try:
                if _directory_identity(candidate) != identity:
                    continue
                if _claim_and_remove(candidate, identity):
                    return True
            except (FileNotFoundError, NotADirectoryError):
                continue
        for candidate in path.parent.iterdir():
            if candidate == path or candidate.name.startswith("."):
                continue
            try:
                if _directory_identity(candidate) == identity and _claim_and_remove(
                    candidate, identity
                ):
                    return True
            except (FileNotFoundError, NotADirectoryError):
                continue
    except _AtomicExchangeUnsupported:
        return False
    return False


def create_model(repo_root: Path, system: CadSystem, model_id: str,
                 template_name: str) -> CreatedModel:
    """Create a paired model and register it in ``system`` as one transaction."""

    _validate_name(model_id, "model")
    _validate_name(template_name, "template")
    identifier = _part_identifier(model_id)
    repository = Path(repo_root).resolve()
    things_root = repository / "things"
    _resolved_beneath(things_root, repository, "things directory")
    system_path = Path(system.path).resolve()
    _resolved_beneath(system_path, repository, "system manifest")
    templates = {item.name: item for item in discover_templates(repository)}
    if template_name not in templates:
        choices = ", ".join(sorted(templates)) or "none"
        raise CadSelectionError(
            f"unknown CAD template {template_name!r}; available: {choices}"
        )
    destination = things_root / model_id
    _resolved_beneath(destination, things_root, "model destination")
    _reject_normalized_collision(things_root, model_id, identifier)
    if destination.exists() or destination.is_symlink():
        raise CadDestinationExistsError(
            f"CAD model destination already exists: {destination}"
        )

    template = templates[template_name]
    template_root = things_root / "3d_template"
    scad_data, sidecar_data = _substitute_pair(
        _read_template(template_root, template),
        _read_template_sidecar(template_root, template),
        model_id,
        template,
    )
    staging = _make_staging(things_root, model_id)
    staged_scad = staging / f"{model_id}.scad"
    staged_sidecar = staging / f"{model_id}.cad.json"
    try:
        _write_exclusive(staged_scad, scad_data)
        _write_exclusive(staged_sidecar, sidecar_data)
        try:
            load_model(model_id, staged_sidecar, repository)
        except CadModelMetadataError as error:
            raise CadSelectionError(f"generated CAD model is invalid: {error}") from None

        lock_path = system_path.with_name(system_path.name + ".lock")
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o666)
        published_identity: tuple[int, int] | None = None
        original = b""
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            original = system_path.read_bytes()
            current = load_system(system_path, repository)
            if model_id in current.models:
                raise CadDestinationExistsError(
                    f"CAD model {model_id!r} already exists in system {current.name!r}"
                )
            manifest = json.loads(original.decode("utf-8"))
            relative_sidecar = (destination / f"{model_id}.cad.json").relative_to(
                repository
            ).as_posix()
            manifest.setdefault("models", {})[model_id] = relative_sidecar
            manifest_data = (
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
            ).encode("utf-8")
            prospective_manifest = json.loads(original.decode("utf-8"))
            _validate_prospective_manifest(
                system_path, repository, prospective_manifest, model_id,
                staged_sidecar,
            )
            _publish_noreplace(staging, destination)
            published_identity = _directory_identity(destination)
            try:
                _replace_system_manifest(system_path, manifest_data)
                load_system(system_path, repository)
            except BaseException:
                if published_identity is not None:
                    _remove_owned_directory(destination, published_identity)
                if system_path.read_bytes() != original:
                    _restore_system_manifest(system_path, original)
                raise
        finally:
            os.close(lock_fd)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return CreatedModel(
        model_id=model_id,
        template=template_name,
        directory=destination,
        scad_path=destination / f"{model_id}.scad",
        sidecar_path=destination / f"{model_id}.cad.json",
    )
