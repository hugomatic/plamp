# Firmware Family API and CLI Design

## Goal

Evolve the controller API and CLI so they support multiple firmware families cleanly, keep JSON as the source input for firmware generation, and allow direct local firmware generation and flashing for power users and agents.

This slice should:

- replace legacy timer-oriented API naming with controller-oriented naming
- treat controller ids as global instance identifiers
- keep firmware type in payloads rather than in controller resource paths
- establish a firmware-family abstraction for generated Pico firmware
- add direct local CLI commands for generating and flashing firmware without `plamp-web`
- add a placeholder `pico_doser` family with a hello-world generator and flash path

## Problem

The current system still mixes old scheduler-specific transport terms with newer controller-oriented concepts:

- REST routes still use `/api/timers/...` and `/api/timer-config`
- one legacy subresource write exists for channel schedule updates
- the CLI uses `pico-scheduler` as the public command family, but still calls old timer routes internally
- the system is starting to support multiple firmware families, but the API and direct programming workflow do not reflect that cleanly yet

At the same time, firmware experimentation needs a direct local path:

- power users and agents need to generate firmware from JSON
- they need to flash firmware directly without going through the web service
- future firmware families should be easy to add without forcing them into scheduler-specific assumptions

## Design

### Controller identity

Controller ids are global instance identifiers across firmware families.

Examples:

- `pump_n_lights`
- `ph`
- `food`

Rules:

- controller ids must be globally unique
- controller ids must match the existing safe id pattern
- controller ids must not use reserved words

Reserved words include:

- firmware family names such as `pico_scheduler` and `pico_doser`
- top-level API nouns such as `controllers`, `config`, and `pics`

This allows flat controller resource paths without ambiguity.

### Controller API

Use controller-oriented REST paths.

Primary routes:

- `GET /api/controllers`
- `GET /api/controllers/{controller}`
- `PUT /api/controllers/{controller}`

Semantics:

- `GET /api/controllers`
  - discovery only
  - lists controllers and their firmware types
- `GET /api/controllers/{controller}`
  - returns the full controller payload
- `PUT /api/controllers/{controller}`
  - replaces the full controller payload

There is no subresource write for part of a controller in the new model.

In particular, routes like:

- `/api/timers/{role}/channels/{channel_id}/schedule`

should be treated as legacy and eventually retired from public use.

### Discovery payload

`GET /api/controllers` should be discovery-oriented, not a full state dump.

Recommended shape:

```json
{
  "controllers": {
    "pump_n_lights": {
      "firmware": "pico_scheduler"
    },
    "hello_doser": {
      "firmware": "pico_doser"
    }
  }
}
```

Why this shape:

- flat by controller id
- firmware type is explicit
- no duplicated id field inside each object
- easy for humans and agents to consume

### Full controller payload

`GET /api/controllers/{controller}` returns the full controller payload.

Example for `pico_scheduler`:

```json
{
  "controller": "pump_n_lights",
  "firmware": "pico_scheduler",
  "report_every": 10,
  "devices": [
    {
      "type": "gpio",
      "pin": 3,
      "current_t": 0,
      "reschedule": 1,
      "pattern": [
        {"val": 1, "dur": 300},
        {"val": 0, "dur": 900}
      ]
    }
  ]
}
```

Rules:

- the payload includes `controller`
- the payload includes `firmware`
- the payload includes all family-specific state needed to generate firmware
- `PUT` replaces the entire controller payload

### Firmware-family abstraction

Add a host-side firmware-family abstraction.

Each firmware family provides:

- a JSON input contract
- a generator that turns JSON into concrete firmware source
- an optional server-backed controller integration
- a direct local flash path for CLI power users

Initial families:

- `pico_scheduler`
- `pico_doser`

This family abstraction should be explicit and not hidden behind scheduler-specific helpers.

### JSON input

JSON remains first-class input for firmware generation.

Rules:

- every firmware family generator takes JSON input
- JSON can come from:
  - server-managed controller state
  - `@file.json`
  - stdin via `-`
- generated firmware embeds the exact JSON input in its provenance block

For `pico_scheduler`, the JSON input remains the existing controller state shape.

For `pico_doser`, the initial hello-world placeholder may use a minimal family-specific JSON shape such as:

```json
{
  "report_every": 5,
  "message": "hello from pico_doser"
}
```

### Direct CLI firmware commands

Add a direct local firmware command family to `plamp`.

Recommended command surface:

- `plamp firmware families`
- `plamp firmware generate --firmware pico_scheduler --controller pump_n_lights @state.json --out main.py`
- `plamp firmware flash --firmware pico_scheduler --controller pump_n_lights @state.json --port /dev/ttyACM0`
- `plamp firmware generate --firmware pico_doser @hello.json --out main.py`
- `plamp firmware flash --firmware pico_doser @hello.json --port /dev/ttyACM0`
- `plamp firmware pull --port /dev/ttyACM0`
- `plamp firmware pull --port /dev/ttyACM0 --out main.py`
- `plamp firmware show --port /dev/ttyACM0`

Rules:

- these commands are for local power-user and agent workflows
- they do not require `plamp-web`
- they explicitly bypass the normal server-backed control flow
- they should require JSON input rather than inventing hidden defaults
- `firmware pull` writes firmware source to stdout by default so shell redirection works:
  - `plamp firmware pull --port /dev/ttyACM0 > main.py`
- `firmware pull --out ...` is an optional convenience/safety path
- `firmware show` is a convenience alias for terminal display
- firmware source output must go only to stdout
- diagnostics and progress messages must go only to stderr

### Server-backed CLI commands

For normal admin use, keep a controller-oriented CLI surface that talks to `plamp-web`.

Recommended command surface:

- `plamp controllers list`
- `plamp controllers get pump_n_lights`
- `plamp controllers set pump_n_lights @controller.json`

Rules:

- use the new `/api/controllers` routes
- stop using `/api/timers/...` and `/api/timer-config` in the CLI implementation
- keep `pico-scheduler` CLI compatibility only if needed during transition

### Placeholder `pico_doser`

Add a minimal `pico_doser` family now to prove the architecture is really multi-family.

Initial scope:

- generator exists
- generator consumes JSON input
- generator emits simple hello-world firmware
- direct local `plamp firmware generate/flash` works for it
- no web visualization or advanced dosing behavior yet

The hello-world firmware should:

- emit minimal structured serial output
- be easy to inspect
- prove the family-specific generation and flashing path

### Legacy compatibility

The system can keep old timer routes temporarily while the API and CLI migrate, but the new public model should be controller-oriented.

Acceptable transition behavior:

- old `/api/timers/...` routes may remain as compatibility aliases
- old `/api/timer-config` may remain temporarily
- existing UI code can migrate in stages

Final target:

- public docs and CLI use `/api/controllers`
- public docs and CLI do not use `timers`
- partial controller schedule mutation is not the preferred API pattern

## Impacted areas

- `plamp_web/server.py`
- `plamp_web/pages.py`
- `plamp_cli/main.py`
- `plamp_cli/README.md`
- new firmware-family support modules
- `pico_scheduler/`
- new `pico_doser/`
- tests for API, CLI, settings, and page references

## Testing requirements

Required coverage:

- controller discovery route returns controller ids with firmware types
- controller get/put routes use full controller payloads
- controller ids reject reserved firmware names
- CLI server-backed controller commands use `/api/controllers`
- direct `plamp firmware generate` accepts JSON input for `pico_scheduler`
- direct `plamp firmware flash` accepts JSON input and target port
- placeholder `pico_doser` generator emits deterministic hello-world firmware
- `pico_doser` direct flash path is covered with mocked transport
- docs and examples stop presenting `/api/timers/...` as the preferred API

## Non-goals

- complete `pico_doser` business logic
- web visualization for `pico_doser`
- removing all legacy timer routes in the same slice if compatibility is still needed
- allowing duplicate controller ids across firmware families
