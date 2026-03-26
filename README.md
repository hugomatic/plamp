# plamp

Tools and hardware notes for claws that want to grow things.

## What is here

### Pico scheduler

A minimal Raspberry Pi Pico scheduler lives in:

- [`pico_scheduler/`](./pico_scheduler/)

It reads a complete `state.json`, drives GPIO/PWM outputs, and emits structured JSON `startup`, `report`, and `error` messages.

Host-side deployment uses `mpremote`.
Start here:

- [`pico_scheduler/README.md`](./pico_scheduler/README.md)

### Things / printable parts

3D-printable parts and generators live in:

- [`things/`](./things/)

Current example:

- [`things/plamp_stand/`](./things/plamp_stand/)

Reference photo:

![Pi with 3D-printed tripod and camera holder](./things/plamp_stand/doc/stand.jpg)

See also:

- [`things/README.md`](./things/README.md)
- [`CHECKLIST.md`](./CHECKLIST.md)

## Repo habits

- prefer simple tools with one obvious contract
- keep runtime state and configured state clearly separated
- document manual validation paths when hardware is involved
- when changing generation or deployment flow, update the relevant README and checklist too
