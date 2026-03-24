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
- `pattern` is a list of steps
- each step applies `val` for `dur` seconds
- `current_t` is the current second inside the pattern
- if `reschedule` is truthy, the pattern repeats forever
- if `reschedule` is falsey, the pattern runs once and then holds the last value

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
- invalid JSON is ignored and the previous in-memory state is kept
- missing `state.json` means the scheduler continues with an empty event list
- the runtime never writes to flash during normal operation
