# pico_scheduler

Minimal cyclic scheduler for Raspberry Pi Pico.

## Files

- `main.py` - single-file MicroPython runtime
- `state.json` - host-provided scheduler state (not written by the Pico runtime)

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

Copy the runtime to the Pico:

```bash
mpremote cp main.py :main.py
```

Copy a state file to the Pico:

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
mpremote cp main.py :main.py
mpremote cp state.json.example :state.json
mpremote reset
```

## Host update flow

Update `state.json` on the host using atomic replace, then copy it to the device.

Example host-side pattern:

```bash
python3 write_state.py > state.json.tmp && mv state.json.tmp state.json
mpremote cp state.json :state.json
```

## Runtime behavior

- `main.py` reloads `state.json` by checking `os.stat()` about every 2 seconds
- invalid JSON is ignored and the previous in-memory state is kept
- missing `state.json` means the scheduler continues with an empty event list
- the runtime never writes to flash during normal operation
