"""Render deterministic, human-first guidance for archived CAD runs."""

from __future__ import annotations

from collections.abc import Mapping


def _directive_line(key: str, directive: Mapping[str, object]) -> str:
    value = directive.get("value")
    lines = {
        "orientation": (
            "Use the exported orientation."
            if value == "as-exported" else f"Orient the part {value}."
        ),
        "supports": {
            "required": "Generate supports.",
            "recommended": "Generate supports where needed.",
            "optional": "Supports are optional.",
            "discouraged": "Avoid supports where possible.",
            "forbidden": "Do not generate supports.",
        }.get(value, f"Supports: {value}."),
        "support_style": f"Use {value} supports if supports are enabled.",
        "ironing": {
            "required": "Enable ironing.",
            "recommended": "Enable ironing.",
            "optional": "Ironing is optional.",
            "discouraged": "Avoid ironing.",
            "forbidden": "Do not enable ironing.",
        }.get(value, f"Ironing: {value}."),
        "material": f"Use {value}.",
        "layer_height": f"Use a {value} mm layer height.",
        "minimum_perimeters": f"Use at least {value} perimeters.",
        "adhesion": f"Use {value} bed adhesion.",
    }
    text = lines[key]
    strength = directive.get("strength")
    source = directive.get("source", "unknown")
    label = "Requirement" if strength == "requirement" else "Recommendation"
    return f"- {text} ({label} from `{source}`.)"


def render_run_readme(manifest: Mapping[str, object]) -> str:
    """Return a deterministic human-readable archive guide."""

    run_id = str(manifest["run_id"])
    jobs_value = manifest.get("jobs", [])
    jobs = [job for job in jobs_value if isinstance(job, Mapping)] \
        if isinstance(jobs_value, list) else []
    lines = [
        f"# CAD run {run_id}", "", f"Status: {manifest.get('status', 'unknown')}",
        "", "## Artifacts", "",
        "| Artifact | Model / set | Status | SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for job in jobs:
        set_name = job.get("set") or "(default)"
        checksum = job.get("artifact_sha256") or "—"
        lines.append(
            f"| {job.get('artifact_id')} | {job.get('model')} / {set_name} | "
            f"{job.get('status')} | `{checksum}` |"
        )

    for job in jobs:
        artifact_id = str(job.get("artifact_id"))
        lines.extend(("", f"## {artifact_id}", "", "### Slicing guidance", ""))
        manufacturing = job.get("manufacturing")
        directives_value = manufacturing.get("directives", {}) \
            if isinstance(manufacturing, Mapping) else {}
        directives = directives_value if isinstance(directives_value, Mapping) else {}
        ordered_keys = (
            "orientation", "material", "layer_height", "minimum_perimeters",
            "supports", "support_style", "ironing", "adhesion",
        )
        rendered = False
        for key in ordered_keys:
            directive = directives.get(key)
            if isinstance(directive, Mapping):
                lines.append(_directive_line(key, directive))
                rendered = True
        notes_value = manufacturing.get("notes", []) \
            if isinstance(manufacturing, Mapping) else []
        if isinstance(notes_value, (list, tuple)):
            for note in notes_value:
                if (isinstance(note, (list, tuple)) and len(note) == 2):
                    lines.append(f"- {note[1]} (Note from `{note[0]}`.)")
                    rendered = True
        if not rendered:
            lines.append("- No slicing guidance was supplied; use your normal printer profile.")

        artifact = job.get("artifact")
        checksum = job.get("artifact_sha256")
        lines.extend(("", "### Verification", ""))
        if isinstance(artifact, str) and isinstance(checksum, str):
            lines.extend((
                f"Expected SHA-256: `{checksum}`", "",
                "```sh", f"sha256sum {artifact}", "```",
            ))
        else:
            lines.append("No completed artifact checksum is available.")

        lines.extend(("", "### Variable provenance", ""))
        variables = job.get("variable_sources", {})
        if isinstance(variables, Mapping) and variables:
            for name, provenance in variables.items():
                if isinstance(provenance, Mapping):
                    winner = provenance.get("winner", {})
                    if isinstance(winner, Mapping):
                        lines.append(
                            f"- `{name}`: `{winner.get('kind')}` / "
                            f"`{winner.get('source_id')}` (all layers in `manifest.json`)."
                        )
        else:
            lines.append("- No externally resolved variables.")

    lines.extend((
        "", "## Inspection", "",
        "- Open `manifest.json` for complete profiles, hashes, manufacturing policy, and variable provenance.",
        "- Open `logs/` for per-artifact OpenSCAD output.",
        "- Open `source/` for the archived model sources.",
        f"- Run `plamp cad show {run_id}` to inspect this run with the CLI.",
    ))
    return "\n".join(lines) + "\n"
