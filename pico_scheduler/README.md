# pico_scheduler

Minimal pattern scheduler for Raspberry Pi Pico.

## Files

- `main.py` - single-file MicroPython runtime
- `state.json` - host-provided scheduler state (not written by the Pico runtime)

## State format

`state.json` contains `report_every` and an `events` list.

Each event uses a timed pattern:

```json
{
  "type": "gpio",
  "ch": 25,
  "current_t": 3,
  "reschedule": 1,
  "pattern": [
    {"val": 1, "dur": 10},
    {"val": 0, "dur": 20}
  ]
}
```

Meaning:
- `type` selects the output kind:
  - `gpio` writes a digital value to a GPIO pin (`0` or `1`)
  - `pwm` writes a PWM duty value to a GPIO pin (`0..65535`)
- `ch` is the Pico GPIO pin number to drive (`0..29`)
- `current_t` is the current second inside the pattern at boot time
- `reschedule` controls whether the pattern repeats:
  - truthy (`1`) means loop forever
  - falsey (`0`) means run once and then hold the last value
- `pattern` is a non-empty list of timed steps
- each pattern step has:
  - `val` - the output value for that step
    - for `gpio`: must be `0` or `1`
    - for `pwm`: integer duty value, clamped to `0..65535`
  - `dur` - step duration in whole seconds, must be `> 0`

## Dependency

Host-side deployment expects `mpremote`.

Install it on the host with:

```bash
python3 -m pip install --user mpremote
```

If needed, bootstrap pip first:

```bash
python3 -m ensurepip --upgrade
python3 -m pip install --user mpremote
```

`mpremote` is often installed into `~/.local/bin`.
If `mpremote help` says command not found, add this to your shell startup file:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload your shell and test:

```bash
mpremote help
```

## Connect to the Pico

With the Pico connected over USB, test that `mpremote` can see it:

```bash
mpremote connect auto fs ls
```

You can also open a REPL:

```bash
mpremote connect auto repl
```

If `mpremote` cannot connect, make sure no other serial tool is holding the device.

## Deploy

Start by creating a host-side state file from the example:

```bash
cp state.json.example state.json
```

Edit `state.json` so it matches the current schema used by `main.py`, then optionally validate it on the host:

```bash
python3 -m json.tool state.json >/dev/null
```

Copy the runtime to the Pico:

```bash
mpremote cp main.py :main.py
```

Copy the state file to the Pico:

```bash
mpremote cp state.json :state.json
```

Reset the board:

```bash
mpremote reset
```

Example from this directory:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/pico_scheduler
cp state.json.example state.json
python3 -m json.tool state.json >/dev/null
mpremote cp main.py :main.py
mpremote cp state.json :state.json
mpremote reset
```

## Host API

The FastAPI host app lives in `../pico_api/` so the firmware directory stays focused on files for the Pico. See `../pico_api/README.md` for setup and runtime page commands.

## Host update flow

Keep `state.json` as a host-side working file, update it with an atomic replace, then copy it to the device and reset the board.

Example host-side pattern:

```bash
python3 emit_state.py > state.json.tmp && mv state.json.tmp state.json
python3 -m json.tool state.json >/dev/null
mpremote cp state.json :state.json
mpremote reset
```

If you are editing by hand instead of generating it, use the same temporary-file pattern:

```bash
$EDITOR state.json.tmp && mv state.json.tmp state.json
python3 -m json.tool state.json >/dev/null
mpremote cp state.json :state.json
mpremote reset
```

## Runtime behavior

- `main.py` reads `state.json` once at boot
- schedule changes take effect after copying a new `state.json` and resetting the board
- invalid or incomplete `state.json` causes startup to fail with a structured JSON error message in `content`
- on successful startup, the runtime emits a structured JSON startup message with a `content` object
- periodic state reports are emitted as structured JSON messages with `content.events` shaped to match the config event list
- the runtime never writes to flash during normal operation
