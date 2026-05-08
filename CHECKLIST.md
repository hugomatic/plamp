# CHECKLIST

Use this as a focused validation list for changes in this repo. Pick the checks that match the change.

Each check includes:
- **Description** — what the check protects
- **How to run** — the practical validation path
- **Success** — what counts as passing

## General

### Check: Run from the real working directory
- **Description:** The tool or script should work from the directory where a human would actually run it.
- **How to run:** Run the primary command from the documented directory, usually the repo root or the tool directory.
- **Success:** The command completes without relying on an unusual cwd or hidden shell setup.

### Check: Path references survive moves and renames
- **Description:** File moves should not leave broken relative paths or stale filenames.
- **How to run:** Review changed path references in scripts, docs, and generated outputs. Run the affected command once.
- **Success:** All referenced paths resolve correctly after the change.

### Check: Docs match the commands people should run
- **Description:** README examples should describe the current interface, not an older one.
- **How to run:** Copy the changed commands or examples from docs and run them as written, or verify each flag/path against the implementation.
- **Success:** The documented commands, arguments, and output locations match reality.

### Check: Output locations are safe and obvious
- **Description:** Generated files should land somewhere predictable and non-destructive.
- **How to run:** Run the changed command and inspect where it writes files, logs, or reports.
- **Success:** Outputs land in a documented, sensible location and do not overwrite unrelated files by surprise.

### Check: Fresh output directory contract holds
- **Description:** Tools that promise a new target directory should enforce that contract.
- **How to run:** Run the tool with its expected output arguments, including a pre-existing target if relevant.
- **Success:** The tool creates a fresh directory when required and fails clearly when the contract is violated.

### Check: Local assumptions are written down
- **Description:** Machine-specific requirements should be documented instead of implied.
- **How to run:** Review changed scripts for assumptions about `PATH`, wrapper scripts, host tools, devices, or local setup.
- **Success:** Any non-obvious local dependency is documented in repo docs or config.

### Check: Required host tools are reachable from a normal shell
- **Description:** A dependency is only usable if the expected command resolves in a regular shell.
- **How to run:** Run `command -v <tool>` for newly required host-side tools.
- **Success:** Each required tool resolves by its expected command name from a normal shell.

### Check: Expensive validations still have a manual path
- **Description:** Slow or hardware-dependent changes need an explicit fallback check.
- **How to run:** Confirm the relevant doc or checklist section includes a concrete manual validation path.
- **Success:** A human can follow a specific manual procedure to validate the change.

### Check: Runtime state is distinct from configured state
- **Description:** Live device behavior should not be inferred only from config files.
- **How to run:** Compare the configured state with live outputs, captures, logs, or device behavior.
- **Success:** The validation explicitly distinguishes what was configured from what actually happened.

### Check: Report and camera timeline stays readable
- **Description:** Timeline messages should preserve a clear startup image and avoid redundant follow-up pictures.
- **How to run:** Review the event/report flow for startup and subsequent state changes.
- **Success:** The sequence is: startup message, immediate picture, reports, then extra pictures only when the observable state changes.

### Check: Output changes emit an immediate Pico report
- **Description:** State changes should produce a full report immediately, not only on the periodic interval.
- **How to run:** Trigger an output change and inspect the emitted Pico reports.
- **Success:** A full `report` is emitted on each output state change and on `report_every`.

## Script / generation changes

### Check: Generator prints a sane default command
- **Description:** A script with no args should teach the human how to run it correctly.
- **How to run:** Run `generate.bash` or the equivalent with no arguments.
- **Success:** It prints a useful suggested command.

### Check: Suggested generator command actually works
- **Description:** Example usage should be executable, not aspirational.
- **How to run:** Copy the suggested command and run it.
- **Success:** The command runs successfully and produces the expected output.

### Check: Generated files are easy to find
- **Description:** Output discovery should be obvious after generation.
- **How to run:** Run the generator and inspect its output messaging and output paths.
- **Success:** A human can locate the generated files without reading the implementation.

### Check: Logs and generated readme output help debug failures
- **Description:** Generation failures should leave useful evidence.
- **How to run:** Review the command output and any generated logs or readme/status files.
- **Success:** The output is specific enough for a human to diagnose what failed.

## Pico scheduler / hardware validation

Use these when changing the Pico scheduler runtime, state schema, deployment flow, or camera-based board verification.

### Check: Real hardware is present
- **Description:** Scheduler validation is only meaningful with an actual Pico in view.
- **How to run:** Confirm a human is available to connect the board and place it in front of the camera.
- **Success:** Real hardware is connected and the validation setup is physically possible.

### Check: Pico is visible to `mpremote`
- **Description:** Host-side board access must work before deeper validation.
- **How to run:** Run `mpremote connect auto fs ls`.
- **Success:** The Pico is reachable over USB and `mpremote` lists the filesystem.

### Check: Test state JSON is valid before deployment
- **Description:** Invalid scheduler state should fail on the host first.
- **How to run:** Run `python3 -m json.tool state.json >/dev/null` in `pico_scheduler/`.
- **Success:** The JSON validates cleanly.

### Check: Deployment and reset path works cleanly
- **Description:** The host must be able to push code and restart the board reliably.
- **How to run:** Copy `main.py` and `state.json` with `mpremote cp ...` and reset the board.
- **Success:** Files copy successfully and the board resets cleanly.

### Check: Camera framing makes the LED visible
- **Description:** Camera-based validation fails if the LED is not clearly in frame.
- **How to run:** Position the camera and inspect a live or recent capture.
- **Success:** The Pico LED is clearly visible in the captured image.

### Check: Baseline capture proves the LED region is discernible
- **Description:** The validation needs a baseline before schedule timing matters.
- **How to run:** Capture a baseline image with the canonical camera wrapper.
- **Success:** The LED region is visibly discernible in the baseline capture.

### Check: A simple known pattern is loaded first
- **Description:** Start with an obvious on/off pattern before testing more subtle schedules.
- **How to run:** Deploy a simple schedule with long enough on/off windows to see the LED state clearly.
- **Success:** The board runs a simple pattern that can be checked visually.

### Check: Camera captures can distinguish LED on vs off
- **Description:** The camera signal must be strong enough to support scheduler validation.
- **How to run:** Capture images during expected LED-on and LED-off windows.
- **Success:** The images reliably distinguish the LED-on state from the LED-off state.

### Check: Timing evidence is preserved
- **Description:** Timed validations need timestamps or logs for later comparison.
- **How to run:** Save captures, timestamps, or logs during the test.
- **Success:** Observed LED states can be compared against the expected schedule after the run.

### Check: Failures are attributed to the right layer
- **Description:** End-to-end tests should separate scheduler bugs from deployment or camera issues.
- **How to run:** Review failures against board state, deployment logs, framing, and camera reliability.
- **Success:** Any failure is attributed to the correct layer: Pico schedule, deployment flow, camera visibility/framing, or camera stack reliability.

## Example manual check: Pico LED visible to camera

Run this intentionally when validating end-to-end hardware behavior.

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
