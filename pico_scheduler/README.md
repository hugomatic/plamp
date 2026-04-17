# pico_scheduler

MicroPython firmware for one Raspberry Pi Pico.

## Files

- `main.py` - Pico runtime
- `state.json.example` - example state copied to the Pico as `state.json`

## State JSON

The Pico reads `state.json` at boot.

Example:

```json
{
  "report_every": 10,
  "events": [
    {
      "id": "test_pin",
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

Fields:

- `id` - name used by the host
- `type` - `gpio` or `pwm`
- `pin` - Pico GPIO pin, `0..29`
- `current_t` - starting second in the pattern
- `reschedule` - `1` repeats, `0` runs once
- `pattern` - timed output steps

## Install Tool

```bash
python3 -m pip install --user mpremote
```

If needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Deploy

From this directory:

```bash
cp state.json.example state.json
python3 -m json.tool state.json >/dev/null
mpremote cp main.py :main.py
mpremote cp state.json :state.json
mpremote reset
```

## Runtime

- Reads `state.json` once at boot.
- Drives configured pins.
- Reports JSON over USB serial.
- Does not write to flash during normal operation.

See also: [`../plamp_web/README.md`](../plamp_web/README.md).
