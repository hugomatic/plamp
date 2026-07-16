# Pico Scheduler

`pico_scheduler` generates one controller-specific MicroPython `main.py` for a Raspberry Pi Pico.

## Host state

Generator input contains the complete device list:

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

`report_every` remains in the host state schema but is not copied into firmware and does not control health checks. The host requests reports every five seconds.

## Firmware contract

Generated firmware:

- runs GPIO and PWM schedules without the host;
- stays silent during routine schedule transitions;
- answers `r` with one newline-delimited JSON report;
- answers `p <pin> <seconds>` with a report or error;
- rejects a pulse when the GPIO is already on;
- applies a pulse as a temporary overlay, then restores the scheduler's value.

The host copies generated code to `:main.py` with `mpremote` and resets the Pico. USB serial may disappear and return during this operation. Flash success requires a valid report after it returns; port presence alone is not success.

Normal schedule changes are compiled and flashed by `plamp-web`. See [the current contract](../docs/spec-current.md).
