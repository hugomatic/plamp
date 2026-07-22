"""Safe, project-neutral scaffolding for local CAD parts."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import tempfile
from pathlib import Path

from plamp.cad_metadata import parse_cad_document


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class CadTemplate:
    name: str
    path: Path


@dataclass(frozen=True)
class CreatedPart:
    part: str
    template: str
    directory: Path
    scad_path: Path


def _validate_name(name: str, kind: str) -> None:
    if Path(name).name != name or _SAFE_NAME.fullmatch(name) is None:
        raise ValueError(
            f"invalid {kind} name {name!r}; names must match {_SAFE_NAME.pattern}"
        )


def _resolved_beneath(path: Path, root: Path, description: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"{description} escapes expected root: {path}") from None
    return resolved


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
    if root_template.is_file():
        candidates.append(("cad", root_template))
    named_root = template_root / "scad"
    if named_root.is_dir():
        candidates.extend(
            (path.stem, path) for path in named_root.glob("*.scad") if path.is_file()
        )

    discovered: dict[str, CadTemplate] = {}
    for name, path in candidates:
        _validate_name(name, "template")
        _resolved_beneath(path, resolved_template_root, "CAD template")
        if name in discovered:
            raise ValueError(f"duplicate CAD template name: {name}")
        discovered[name] = CadTemplate(name=name, path=path)
    return tuple(discovered[name] for name in sorted(discovered))


def create_part(repo_root: Path, part_name: str, template_name: str) -> CreatedPart:
    """Atomically create one part directory from a validated SCAD template."""

    _validate_name(part_name, "part")
    _validate_name(template_name, "template")
    templates = {item.name: item for item in discover_templates(repo_root)}
    if template_name not in templates:
        choices = ", ".join(sorted(templates)) or "none"
        raise ValueError(
            f"unknown CAD template {template_name!r}; available: {choices}"
        )

    repository = Path(repo_root).resolve()
    things_root = repository / "things"
    _resolved_beneath(things_root, repository, "things directory")
    destination = things_root / part_name
    _resolved_beneath(destination, things_root, "part destination")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"CAD part destination already exists: {destination}")

    source = templates[template_name].path
    document = parse_cad_document(source)
    if not document.metadata_snapshot:
        raise ValueError(f"CAD template has no generation metadata: {source}")

    staging = Path(tempfile.mkdtemp(prefix=f".{part_name}.staging-", dir=things_root))
    staged_scad = staging / f"{part_name}.scad"
    try:
        shutil.copyfile(source, staged_scad)
        staged_document = parse_cad_document(staged_scad)
        if not staged_document.metadata_snapshot:
            raise ValueError(f"staged CAD part has no generation metadata: {staged_scad}")
        staging.rename(destination)
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
