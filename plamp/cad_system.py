"""Discover and validate repository CAD system manifests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from difflib import get_close_matches
import json
from pathlib import Path
import re
from types import MappingProxyType

from plamp.cad_model import CadDiagnostic, CadMetadataError, CadModel, load_model


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SYSTEM_KEYS = frozenset({
    "schema", "name", "description", "models", "libraries", "profiles",
    "default_product", "products",
})
_PRODUCT_KEYS = frozenset({"description", "items", "variables", "profiles", "slicing"})
_ITEM_KEYS = frozenset({
    "product", "model", "set", "variant", "description", "note", "variables",
    "profiles", "slicing",
})
_LIBRARY_KEYS = frozenset({"path", "license", "description", "revision"})


@dataclass(frozen=True)
class SystemCandidate:
    path: Path
    name: str
    description: str
    default_product: str | None
    status: str
    diagnostics: tuple[CadDiagnostic, ...] = ()


@dataclass(frozen=True)
class CadProductItem:
    product: str | None = None
    model: str | None = None
    set_name: str | None = None
    variant: str | None = None
    description: str = ""
    variables: Mapping[str, object] = field(default_factory=dict)
    profiles: tuple[str, ...] = ()
    slicing: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CadProduct:
    name: str
    description: str
    items: tuple[CadProductItem, ...]
    variables: Mapping[str, object] = field(default_factory=dict)
    profiles: tuple[str, ...] = ()
    slicing: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CadSystem:
    name: str
    description: str
    path: Path
    models: Mapping[str, CadModel]
    products: Mapping[str, CadProduct]
    default_product: str | None
    libraries: Mapping[str, object]
    profiles: Mapping[str, Path]
    metadata_snapshot: Mapping[str, object]


def _diagnostic(path: Path, message: str, *, json_path: str | None = None,
                code: str = "CAD120", kind: str = "invalid_system_metadata",
                value: object | None = None, choices: tuple[str, ...] = (),
                suggestion: str | None = None) -> CadDiagnostic:
    return CadDiagnostic(code, kind, message, str(path), json_path=json_path,
                         value=value, choices=choices, suggestion=suggestion)


def _fail(path: Path, message: str, **fields: object) -> None:
    raise CadMetadataError((_diagnostic(path, message, **fields),))


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        _fail(path, f"Invalid system manifest: {error}", code="CAD100", kind="invalid_json")
    if not isinstance(value, dict):
        _fail(path, "System manifest must be a JSON object", json_path="$", value=value)
    return value


def _unknown_keys(value: Mapping[str, object], allowed: frozenset[str], path: Path,
                  json_path: str) -> None:
    for key in value:
        if key not in allowed:
            _fail(path, f"Unknown metadata key {key!r}", json_path=f"{json_path}.{key}", value=key)


def _string(value: Mapping[str, object], key: str, path: Path, json_path: str,
            default: str | None = None) -> str:
    result = value.get(key, default)
    if not isinstance(result, str):
        _fail(path, f"{json_path} must be a string", json_path=json_path, value=result)
    return result


def _mapping(value: Mapping[str, object], key: str, path: Path,
             json_path: str) -> dict[str, object]:
    result = value.get(key, {})
    if not isinstance(result, dict):
        _fail(path, f"{json_path} must be a JSON object", json_path=json_path, value=result)
    return result


def _profiles(value: Mapping[str, object], path: Path, json_path: str) -> tuple[str, ...]:
    raw = value.get("profiles", [])
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        _fail(path, f"{json_path} must be an array of strings", json_path=json_path, value=raw)
    return tuple(raw)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_existing(reference: str, repo_root: Path, manifest: Path,
                      json_path: str) -> Path:
    raw = Path(reference)
    resolved = (raw if raw.is_absolute() else repo_root / raw).resolve()
    if raw.is_absolute() or not _inside(resolved, repo_root):
        _fail(manifest, f"{json_path} must remain inside the repository",
              code="CAD109", kind="unsafe_path", json_path=json_path, value=reference)
    if not resolved.exists():
        _fail(manifest, f"Referenced path does not exist: {reference}",
              code="CAD121", kind="missing_path", json_path=json_path, value=reference)
    return resolved


def _safe_name(name: str, path: Path, json_path: str) -> None:
    if not _SAFE_NAME.fullmatch(name):
        _fail(path, f"Unsafe name {name!r}", json_path=json_path, value=name)


def discover_systems(repo_root: Path) -> tuple[SystemCandidate, ...]:
    """Return every direct CAD system manifest, retaining invalid candidates."""
    repo_root = Path(repo_root).resolve()
    rows = []
    for path in sorted((repo_root / "cad").glob("*.system.cad.json"), key=lambda item: item.name):
        try:
            system = load_system(path, repo_root)
            rows.append(SystemCandidate(path, system.name, system.description,
                                        system.default_product, "valid"))
        except CadMetadataError as error:
            metadata = {}
            try:
                metadata = _read_json(path)
            except CadMetadataError:
                pass
            name = metadata.get("name", "")
            description = metadata.get("description", "")
            default = metadata.get("default_product")
            rows.append(SystemCandidate(
                path, name if isinstance(name, str) else "",
                description if isinstance(description, str) else "",
                default if isinstance(default, str) else None, "invalid", error.diagnostics))
    paths_by_name: dict[str, list[Path]] = {}
    for row in rows:
        if row.name:
            paths_by_name.setdefault(row.name, []).append(row.path)
    duplicate_names = {name: tuple(paths) for name, paths in paths_by_name.items()
                       if len(paths) > 1}
    for index, row in enumerate(rows):
        if row.name not in duplicate_names:
            continue
        duplicate_paths = tuple(str(item) for item in duplicate_names[row.name])
        diagnostic = _diagnostic(
            row.path, f"Duplicate system name {row.name!r}: {', '.join(duplicate_paths)}",
            code="CAD128", kind="duplicate_system_name", json_path="$.name",
            value=row.name, choices=duplicate_paths,
        )
        rows[index] = replace(row, status="invalid",
                              diagnostics=row.diagnostics + (diagnostic,))
    return tuple(rows)


def select_system(candidates: Iterable[SystemCandidate], selector: str) -> SystemCandidate:
    """Select a unique candidate by declared name or explicit manifest path."""
    rows = tuple(candidates)
    if rows:
        repo_root = rows[0].path.parent.parent.resolve()
    else:
        repo_root = Path.cwd().resolve()
    raw_selector_path = Path(selector)
    selector_path = (raw_selector_path if raw_selector_path.is_absolute()
                     else repo_root / raw_selector_path).resolve()
    path_matches = tuple(row for row in rows if row.path.resolve() == selector_path)
    name_matches = tuple(row for row in rows if row.name == selector)
    matches = path_matches or name_matches
    if len(matches) == 1:
        return matches[0]
    explicit_path = (raw_selector_path.is_absolute() or len(raw_selector_path.parts) > 1
                     or selector.endswith(".system.cad.json"))
    if not path_matches and explicit_path:
        if not _inside(selector_path, repo_root):
            _fail(selector_path, "Explicit system manifest must remain inside the repository",
                  code="CAD109", kind="unsafe_path", value=selector)
        system = load_system(selector_path, repo_root)
        return SystemCandidate(selector_path, system.name, system.description,
                               system.default_product, "valid")
    choices = tuple(f"{row.name or '<invalid>'} ({row.path})" for row in rows)
    reason = "ambiguous" if len(matches) > 1 else "not found"
    source = rows[0].path if rows else Path(selector)
    _fail(source, f"System {selector!r} was {reason}; discovered choices: {', '.join(choices) or '(none)'}",
          code="CAD122", kind="system_selection", value=selector, choices=choices)


def load_system(reference: Path, repo_root: Path) -> CadSystem:
    """Load and fully validate one repository CAD system manifest."""
    repo_root = Path(repo_root).resolve()
    path = Path(reference)
    path = (path if path.is_absolute() else repo_root / path).resolve()
    if not _inside(path, repo_root):
        _fail(path, "System manifest must remain inside the repository", code="CAD109", kind="unsafe_path")
    metadata = _read_json(path)
    _unknown_keys(metadata, _SYSTEM_KEYS, path, "$" )
    schema = _string(metadata, "schema", path, "$.schema")
    if schema != "plamp-cad-system/1":
        _fail(path, "$.schema must equal 'plamp-cad-system/1'", json_path="$.schema", value=schema)
    name = _string(metadata, "name", path, "$.name")
    _safe_name(name, path, "$.name")
    description = _string(metadata, "description", path, "$.description", "")

    raw_models = _mapping(metadata, "models", path, "$.models")
    models = {}
    for model_id, raw_reference in raw_models.items():
        _safe_name(model_id, path, f"$.models.{model_id}")
        if not isinstance(raw_reference, str):
            _fail(path, "Model reference must be a string", json_path=f"$.models.{model_id}", value=raw_reference)
        _resolve_existing(raw_reference, repo_root, path, f"$.models.{model_id}")
        models[model_id] = load_model(model_id, Path(raw_reference), repo_root)

    raw_profiles = _mapping(metadata, "profiles", path, "$.profiles")
    profiles = {}
    for profile_name, raw_reference in raw_profiles.items():
        _safe_name(profile_name, path, f"$.profiles.{profile_name}")
        if not isinstance(raw_reference, str):
            _fail(path, "Profile reference must be a string", json_path=f"$.profiles.{profile_name}", value=raw_reference)
        profiles[profile_name] = _resolve_existing(raw_reference, repo_root, path, f"$.profiles.{profile_name}")

    raw_libraries = _mapping(metadata, "libraries", path, "$.libraries")
    libraries = {}
    for library_name, declaration in raw_libraries.items():
        _safe_name(library_name, path, f"$.libraries.{library_name}")
        if isinstance(declaration, str):
            library_path = declaration
        elif isinstance(declaration, dict):
            _unknown_keys(declaration, _LIBRARY_KEYS, path, f"$.libraries.{library_name}")
            library_path = _string(declaration, "path", path, f"$.libraries.{library_name}.path")
        else:
            _fail(path, "Library declaration must be a string or JSON object",
                  json_path=f"$.libraries.{library_name}", value=declaration)
        _resolve_existing(library_path, repo_root, path, f"$.libraries.{library_name}.path")
        libraries[library_name] = declaration

    raw_products = _mapping(metadata, "products", path, "$.products")
    products = {}
    for product_name, raw_product in raw_products.items():
        _safe_name(product_name, path, f"$.products.{product_name}")
        if not isinstance(raw_product, dict):
            _fail(path, "Product must be a JSON object", json_path=f"$.products.{product_name}", value=raw_product)
        product_path = f"$.products.{product_name}"
        _unknown_keys(raw_product, _PRODUCT_KEYS, path, product_path)
        raw_items = raw_product.get("items", [])
        if not isinstance(raw_items, list):
            _fail(path, f"{product_path}.items must be an array", json_path=f"{product_path}.items", value=raw_items)
        items = []
        for index, raw_item in enumerate(raw_items):
            item_path = f"{product_path}.items[{index}]"
            if not isinstance(raw_item, dict):
                _fail(path, f"{item_path} must be a JSON object", json_path=item_path, value=raw_item)
            _unknown_keys(raw_item, _ITEM_KEYS, path, item_path)
            product_ref = raw_item.get("product")
            model_ref = raw_item.get("model")
            if (isinstance(product_ref, str)) + (isinstance(model_ref, str)) != 1:
                _fail(path, "Product item must contain exactly one of 'product' or 'model'",
                      json_path=item_path, value=raw_item)
            if product_ref is not None and "set" in raw_item:
                _fail(path, "A product reference cannot contain 'set'", json_path=item_path, value=raw_item)
            set_name = raw_item.get("set")
            if model_ref is not None and not isinstance(set_name, str):
                _fail(path, "A model reference requires a string 'set'", json_path=f"{item_path}.set", value=set_name)
            variant = raw_item.get("variant")
            if variant is not None and (not isinstance(variant, str) or not _SAFE_NAME.fullmatch(variant)):
                _fail(path, "Variant must be a safe name", json_path=f"{item_path}.variant", value=variant)
            item_description = raw_item.get("description", raw_item.get("note", ""))
            if not isinstance(item_description, str):
                _fail(path, "Item description must be a string", json_path=f"{item_path}.description", value=item_description)
            items.append(CadProductItem(
                product=product_ref, model=model_ref, set_name=set_name, variant=variant,
                description=item_description,
                variables=MappingProxyType(_mapping(raw_item, "variables", path, f"{item_path}.variables").copy()),
                profiles=_profiles(raw_item, path, f"{item_path}.profiles"),
                slicing=MappingProxyType(_mapping(raw_item, "slicing", path, f"{item_path}.slicing").copy()),
            ))
        product_description = _string(raw_product, "description", path, f"{product_path}.description", "")
        products[product_name] = CadProduct(
            product_name, product_description, tuple(items),
            MappingProxyType(_mapping(raw_product, "variables", path, f"{product_path}.variables").copy()),
            _profiles(raw_product, path, f"{product_path}.profiles"),
            MappingProxyType(_mapping(raw_product, "slicing", path, f"{product_path}.slicing").copy()),
        )

    choices = tuple(products)
    for product_name, product in products.items():
        for profile_name in product.profiles:
            if profile_name not in profiles:
                _fail(path, f"Unknown profile {profile_name!r}", code="CAD127",
                      kind="unknown_profile", value=profile_name,
                      choices=tuple(profiles))
        siblings: dict[tuple[str, str], list[CadProductItem]] = {}
        for item in product.items:
            for profile_name in item.profiles:
                if profile_name not in profiles:
                    _fail(path, f"Unknown profile {profile_name!r}", code="CAD127",
                          kind="unknown_profile", value=profile_name,
                          choices=tuple(profiles))
            if item.product is not None and item.product not in products:
                suggestion = (get_close_matches(item.product, choices, n=1, cutoff=0.6) or [None])[0]
                _fail(path, f"Unknown product {item.product!r}", code="CAD123", kind="unknown_product",
                      value=item.product, choices=choices, suggestion=suggestion)
            if item.model is not None:
                if item.model not in models:
                    _fail(path, f"Unknown model {item.model!r}", code="CAD124", kind="unknown_model", value=item.model)
                if item.set_name not in models[item.model].sets:
                    _fail(path, f"Unknown set {item.set_name!r} for model {item.model!r}",
                          code="CAD111", kind="unknown_set", value=item.set_name,
                          choices=tuple(models[item.model].sets))
                siblings.setdefault((item.model, item.set_name or ""), []).append(item)
        for model_set, repeated in siblings.items():
            if len(repeated) > 1:
                variants = tuple(item.variant for item in repeated)
                if any(variant is None for variant in variants) or len(set(variants)) != len(variants):
                    _fail(path, f"Sibling references to {model_set[0]}/{model_set[1]} require distinct variants",
                          code="CAD125", kind="invalid_variant", value=variants)

    default = metadata.get("default_product")
    if default is not None and not isinstance(default, str):
        _fail(path, "$.default_product must be a string or null", json_path="$.default_product", value=default)
    if default is not None and default not in products:
        _fail(path, f"Unknown default product {default!r}", code="CAD123", kind="unknown_product",
              json_path="$.default_product", value=default, choices=choices)

    visited = set()
    active = []
    def visit(product_name: str) -> None:
        if product_name in active:
            start = active.index(product_name)
            cycle = active[start:] + [product_name]
            _fail(path, f"Product cycle: {' -> '.join(cycle)}", code="CAD126", kind="product_cycle", value=tuple(cycle))
        if product_name in visited:
            return
        active.append(product_name)
        for item in products[product_name].items:
            if item.product is not None:
                visit(item.product)
        active.pop()
        visited.add(product_name)
    for product_name in products:
        visit(product_name)

    return CadSystem(
        name, description, path, MappingProxyType(models), MappingProxyType(products),
        default, MappingProxyType(libraries.copy()), MappingProxyType(profiles),
        MappingProxyType(metadata.copy()),
    )
