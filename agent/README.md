# Plamp agent entrypoint

Start with the [Plamp workflow skill](skills/plamp-workflow/SKILL.md). It
explains checkout setup and routes host lifecycle, direct device/API, and CAD
work to the correct command.

For OpenSCAD models, printable artifacts, or new parts under `things/`, also
read the [OpenSCAD CAD skill](skills/openscad-cad/SKILL.md) and its linked
repository conventions.

From a clone, source `./setup.sh` to select that checkout and its data directory.
If shell setup is undesirable, invoke the checkout launcher as `bin/plamp`.
