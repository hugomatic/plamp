# things

## CAD workflow

Run CAD commands from the repository root after `source ./setup.sh`, or invoke
the checkout launcher as `bin/plamp`:

```bash
plamp cad new PART --template cad
plamp cad validate PART
plamp cad plan PART
plamp cad generate PART
```

`openscad` must be available on `PATH` for generation. Discovery, validation,
and planning remain useful without it.

## Checklist

See the repo-level [`CHECKLIST.md`](../CHECKLIST.md) for the general checklist and example manual checks.
