# pico_scheduler

Generated MicroPython firmware for one Raspberry Pi Pico.

## What Lives Here

- `generator.py`
  Host-side firmware generator for `pico_scheduler` controllers.
- `templates/`
  Readable firmware templates and device fragments used by the generator.
- `state.json.example`
  Example host-side scheduler JSON input shape.

## Source Of Truth

The Raspberry Pi remains the source of truth.

The scheduler JSON shape is still:

```json
{
  "report_every": 10,
  "devices": [
    {
      "type": "gpio",
      "pin": 25,
      "current_t": 0,
      "reschedule": 1,
      "pattern": [
        {"val": 1, "dur": 5},
        {"val": 0, "dur": 5}
      ]
    }
  ]
}
```

That JSON is generator input on the host. It is not copied to the Pico.

## Generated Firmware

`plamp-web` generates one controller-specific `main.py` and copies only that file to the Pico.

The generated `main.py` starts with a top-level triple-quoted provenance block containing:

- generator source path
- generation timestamp
- git version
- controller id
- generator input JSON, including options

The generator emits only the code needed by the configured device types. For example:

- no PWM import or helper code when the controller has only GPIO devices
- no GPIO output setup when the controller has only PWM devices

## Wire Format

Generated firmware emits minimal JSON messages over USB serial:

- `type: "report"` for full current state snapshots
- `type: "error"` for explicit failures

Every `report` contains the full current `devices` state.

## Deploy

Normal deploy happens through `plamp-web` when controller state is applied.

At a high level:

1. host-side scheduler JSON is validated
2. `generator.py` renders controller-specific `main.py`
3. `mpremote` copies that generated file to `:main.py`
4. the Pico is reset

There is no `state.json` copy step in this design.

## Install Tool

```bash
python3 -m pip install --user mpremote
```

If needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

See also: [`../plamp_web/README.md`](../plamp_web/README.md).
