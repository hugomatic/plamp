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

## Grow loop / tending reflexes

Use these when changing the hourly grow loop, grow folder layout, event log format, or capture/comparison tools.

### Check: Grow README defines the canonical layout and direct tools
- **Description:** Repo docs should keep one clear filesystem-first grow layout and tool entrypoint set.
- **How to run:** Read `grow/README.md` after the change and compare it to the actual grow directory layout and script names.
- **Success:** `grow/README.md` accurately describes the canonical layout and the direct tools people should run.

### Check: Operating model matches the intended cadence
- **Description:** Hourly, 12h, daily, weekly, and monthly responsibilities should stay aligned with the design.
- **How to run:** Compare the changed behavior and docs against `grow/OPERATING_MODEL.md`.
- **Success:** `grow/OPERATING_MODEL.md` matches the intended responsibilities for each cadence.

### Check: `grow.json` remains the tracked source of grow identity
- **Description:** Grow identity and configuration should stay anchored in one tracked file.
- **How to run:** Review any config or layout changes touching grow identity.
- **Success:** `grow/grows/<grow-id>/grow.json` remains the single tracked source of grow identity/config.

### Check: Runtime grow data stays filesystem-only
- **Description:** Runtime artifacts should remain plain files, not drift toward hidden state or a database.
- **How to run:** Review the changed data flow and storage paths.
- **Success:** Runtime data remains in files such as `events.jsonl`, captures, sidecars, summaries, predictions, and amendments.

### Check: `log_event.py` appends exactly one valid event line
- **Description:** Event logging should stay append-only and line-oriented.
- **How to run:** Run `python3 grow/log_event.py --grow <grow-id> ...` once and inspect the end of `events.jsonl`.
- **Success:** The command appends exactly one valid JSON object line.

### Check: `capture_photo.py` writes image plus matching sidecar
- **Description:** A capture is not complete without both the image and its metadata.
- **How to run:** Run `python3 grow/capture_photo.py --grow <grow-id>` and inspect the target capture directory.
- **Success:** The grow folder contains one new image file and one matching sidecar JSON.

### Check: Capture sidecars contain comparison context
- **Description:** Sidecars should support later light comparison without guesswork.
- **How to run:** Open a newly written sidecar JSON.
- **Success:** It includes timestamp, image path, brightness, previous capture pointer, and AI comparison payload/context.

### Check: `compare_light.py` updates the latest sidecar and logs the result
- **Description:** Light comparison should enrich the latest capture and record the comparison in the event log.
- **How to run:** Run `python3 grow/compare_light.py --grow <grow-id>` after at least two captures exist.
- **Success:** The latest sidecar is updated and `events.jsonl` gains a `light_compare` event.

### Check: `hourly_tend.py` composes capture and compare transparently
- **Description:** The hourly pass should remain a thin composition layer, not a place where outputs disappear.
- **How to run:** Run `python3 grow/hourly_tend.py --grow <grow-id>` and inspect the written files and events.
- **Success:** The command performs capture + compare and leaves obvious, inspectable outputs in the grow folder.

### Check: Heartbeat stays an auditor, not the scheduler
- **Description:** The operating model depends on cron owning the hourly reflex.
- **How to run:** Review changed scheduling docs and automation paths.
- **Success:** Heartbeat is described as audit/repair behavior, not as the primary hourly scheduler.

### Check: Fast artifacts feed slower reviews
- **Description:** Hourly outputs should prepare inputs for slower summaries instead of bypassing them.
- **How to run:** Review how summaries, predictions, or amendments consume hourly artifacts.
- **Success:** Higher-frequency artifacts support slower review layers rather than replacing them.

### Check: Predictions stay durable and amendments stay additive
- **Description:** Judgment history should remain inspectable over time.
- **How to run:** Review the write path for predictions and amendments.
- **Success:** New predictions create new artifacts and amendments never overwrite an older prediction in place.

### Check: Summary and prediction outputs are answer-first
- **Description:** Review artifacts should prioritize useful conclusions over plumbing dumps.
- **How to run:** Inspect any emitted summary or prediction artifact.
- **Success:** The artifact foregrounds what happened, what was expected, what it means, and what changed.

### Check: Machine-specific camera wrapper paths are documented
- **Description:** Camera invocation details should not be hidden tribal knowledge.
- **How to run:** Review any machine-specific camera path used by scripts or config.
- **Success:** The wrapper path is documented in repo docs or grow config.

### Check: Real light-state validation still has a manual path
- **Description:** The system needs a practical way to confirm that inferred light state matches reality.
- **How to run:** Confirm the docs include a manual capture-based validation path using real images.
- **Success:** A human can validate tomorrow’s light-on vs light-off images with explicit steps.

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

## Example manual check: grow hourly loop

Run this intentionally when validating the real garden path:

```bash
cd /home/hugo/.openclaw/workspace/code/plamp
python3 grow/hourly_tend.py --grow grow-thai-basil-siam-queen-2026-03-27
```

Then confirm:
- a new image exists under `grow/grows/grow-thai-basil-siam-queen-2026-03-27/captures/YYYY-MM-DD/`
- the matching sidecar JSON points at the previous capture when one exists
- `events.jsonl` gained `capture`, `light_compare`, and `hourly_tend` entries
- the inferred `light_state` matches what Hugo can see in the image

Why this is manual:
- it depends on the real camera and the real grow scene
- ambient light and framing still matter
- the current comparison is deliberately simple and should be checked against reality before trusting automation

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
