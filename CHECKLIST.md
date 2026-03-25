# CHECKLIST

Use this as a lightweight checklist for changes in this repo. Not every item applies every time.

## General

- [ ] The thing still works from the directory where a human would normally run it.
- [ ] Paths still make sense after file moves or renames.
- [ ] Commands and examples in docs still match reality.
- [ ] Output locations are sensible and safe.
- [ ] Scripts that create output use a fresh non-existing target directory when that is the expected contract.
- [ ] Local assumptions are documented (`PATH`, tools, machine-specific setup, odd gotchas).
- [ ] Required host-side tools are actually available from a normal shell (`command -v ...`), not just installed somewhere.
- [ ] If a change is expensive to validate, there is still a clear manual check for it.
- [ ] When validating live device behavior, distinguish configured state from runtime state.
- [ ] For report+camera timelines, send a picture immediately after the startup message, then send all reports and only send additional pictures when the observable state actually changes.
- [ ] Verify that the Pico emits a full `report` not only on `report_every`, but also immediately when any output changes state.

## Script / generation changes

- [ ] `generate.bash` (or equivalent) still prints a sane suggested command when run with no args.
- [ ] The suggested command actually works when copied and run.
- [ ] Generated files are easy to find afterward.
- [ ] Logs or generated readme output are useful enough for a human to inspect failures.

## Pico scheduler / hardware validation

Use this when changing the Pico scheduler runtime, state schema, deployment flow, or any camera-based verification around board status.

Precondition:
- [ ] A human is available to connect a Pico and place it in front of the camera; this check is not meaningful without real hardware in view.

- [ ] A Pico is connected over USB and visible to `mpremote connect auto fs ls`.
- [ ] The test state file validates on the host with `python3 -m json.tool state.json >/dev/null`.
- [ ] `main.py` and `state.json` can be copied to the Pico with `mpremote cp ...` and the board can be reset cleanly.
- [ ] The camera is positioned so the Pico LED is clearly visible in frame.
- [ ] A baseline camera capture confirms the LED region is actually discernible before scheduler testing.
- [ ] A simple known pattern is loaded first (for example: LED on long enough to confirm visibility, then off long enough to confirm contrast).
- [ ] Camera captures taken during the test can distinguish LED on vs off reliably enough to validate scheduler behavior.
- [ ] If the validation depends on timing, capture timestamps or logs are preserved so the observed LED state can be compared against the expected schedule.
- [ ] Any failure is attributed to the right layer: Pico schedule, deployment flow, camera visibility/framing, or camera stack reliability.

## Example manual check: Pico LED visible to camera

Run this intentionally when validating end-to-end hardware behavior:

1. Connect the Pico and confirm host access:
   ```bash
   cd /home/hugo/.openclaw/workspace/code/plamp/pico_scheduler
   mpremote connect auto fs ls
   ```
2. Create a simple test schedule in `state.json` from the example.
3. Validate the JSON and deploy it:
   ```bash
   python3 -m json.tool state.json >/dev/null
   mpremote cp main.py :main.py
   mpremote cp state.json :state.json
   mpremote reset
   ```
4. Point the camera so the Pico LED is visible.
5. Capture a baseline image with the canonical wrapper:
   ```bash
   cd /home/hugo/.openclaw/workspace
   ./scripts/camera-shot.sh /tmp/pico-led-baseline.jpg
   ```
6. Capture one or more images during expected LED-on and LED-off windows.
7. Confirm the observed LED state in the images matches the schedule.

Why this is manual:
- it depends on real hardware (`mpremote`, Pico, camera)
- it validates the full chain instead of only the scheduler code in isolation
- timing, framing, and ambient light all affect whether the camera verification is trustworthy

## Example manual check: `things/plamp_stand`

Run this intentionally when changing the model or generation flow:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp/things/plamp_stand
bash ./check_generates_stl_files_from_scad.bash
```

What it checks:
- renders the latest `plamp_stand.scad`
- generates STL files for `assembly`, `plate`, and `camera_clip`
- verifies the generated files and `readme.md` exist and are non-empty

Why this is manual:
- it depends on `openscad`
- it does real rendering work
- it is slower/heavier than a quick script sanity check
