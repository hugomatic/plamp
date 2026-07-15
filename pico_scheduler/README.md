# Pico Scheduler

`pico_scheduler` generates one controller-specific MicroPython `main.py` for a Raspberry Pi Pico.

## Inputs

Host scheduler state contains report cadence and devices:

```json
{
  "report_every": 10,
  "devices": [
    {
      "id": "pump",
      "type": "gpio",
      "pin": 15,
      "current_t": 0,
      "reschedule": 1,
      "pattern": [
        {"val": 1, "dur": 300},
        {"val": 0, "dur": 1800}
      ]
    }
  ]
}
```

The Pi is authoritative. This JSON is generator input and is not copied to the Pico.

## Generated firmware

`generator.py` renders `templates/` into a readable `main.py` containing provenance and only the helpers required by configured device types. The host copies that file to `:main.py` with `mpremote` and resets the Pico.

Current firmware:

- runs GPIO/PWM patterns independently of the host;
- emits newline-delimited `type: report` and `type: error` JSON;
- answers the `r` command with a full report;
- also emits startup, changed-state, and periodic reports.

Demand-only full reports and runtime schedule updates without reflashing are target architecture, not current firmware behavior.

## Tools

```bash
python3 -m pip install --user mpremote
```

Normal generation and deployment happen through `plamp-web`. See [current contract](../docs/spec-current.md).
