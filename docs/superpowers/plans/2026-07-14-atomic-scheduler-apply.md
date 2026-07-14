# Atomic Scheduler Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make web and per-channel schedule writes converge on semantic configuration, one complete timer-state compilation, and one Pico flash.

**Architecture:** `timer_schedule.py` compiles configured channel metadata into one state. Server controller apply owns compile/write/flash; the per-channel endpoint updates semantic configuration and delegates to it. The dashboard saves configuration then applies once, while the API test page documents every scheduler workflow.

**Tech Stack:** Python, FastAPI, browser JavaScript embedded by `pages.py`, `unittest`.

## Global Constraints

- One editor submission performs at most one Pico flash.
- Saved clock strings and cycle unit preferences populate editor fields exactly.
- The existing Pico protocol and post-flash `r` request do not change.
- Per-channel API/CLI remain available but cannot mutate compiled timer state directly.

---

### Task 1: Compile Complete Timer State from Semantic Channels

**Files:**
- Modify: `plamp_web/timer_schedule.py`
- Test: `tests/test_timer_schedule.py`

**Interfaces:**
- Produces: `compile_controller_state(channels: list[dict], report_every: int, now: time | None = None) -> dict`.
- Reuses: `apply_cycle_schedule()` and `apply_clock_window_schedule()`.

- [ ] **Step 1: Add failing mixed-controller tests**

Test a cycle channel with `unit: "minutes"` and a daily channel with `06:00–23:00` at 09:30. Assert IDs, pins, patterns, cycle phase 0, daily phase 12,600, and report interval.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule.TimerScheduleTests.test_compile_controller_state_builds_all_channels -v`

Expected: import or attribute failure because `compile_controller_state` does not exist.

- [ ] **Step 3: Implement the compiler**

For each channel, create the base device through `_new_channel_device`, inspect `channel["editor"]["kind"]`, and delegate to the existing cycle or clock-window function. Return `{"report_every": report_every, "devices": devices}`. Reject unsupported kinds.

- [ ] **Step 4: Run `tests.test_timer_schedule`**

Expected: all tests pass.

### Task 2: Make Controller Apply the Single Write/Flash Path

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: `compile_controller_state`, `channel_metadata_for_role`, `load_config`, and controller `payload.report_every`.
- Produces: `compiled_timer_state_for_controller(controller, now=None)` and one internal compile/write/apply helper used by both endpoints.

- [ ] **Step 1: Replace the saved-state reapply test with a failing semantic compile test**

Configure pump cycle and lights 06:00–23:00, seed a stale timer file, freeze host time at 09:30, call `post_controller_apply`, and assert the written state has both correct patterns/phases and `apply_timer_state` is called exactly once.

- [ ] **Step 2: Verify RED**

Run the new config API test only. Expected: stale timer file is reapplied instead of semantic configuration being compiled.

- [ ] **Step 3: Implement controller compilation and one apply helper**

Load validated config, obtain channel metadata and report interval, call `compile_controller_state`, validate it, atomically write the timer file under the role lock, then call `apply_timer_state` once. Make `post_controller_apply` delegate to this helper.

- [ ] **Step 4: Verify controller apply GREEN**

Run the focused test, then the controller-apply tests in `tests.test_config_api`.

### Task 3: Refactor the Per-Channel Compatibility Endpoint

**Files:**
- Modify: `plamp_web/server.py`
- Test: `tests/test_config_api.py`
- Test: `tests/test_plamp_cli.py`

**Interfaces:**
- Consumes: per-channel request `{mode, ...}` and existing semantic `editor` metadata.
- Produces: updated controller configuration followed by the Task 2 whole-controller apply helper.

- [ ] **Step 1: Add a failing per-channel semantic persistence test**

Call the per-channel endpoint for lights with 06:00–23:00. Assert config now contains `daily_window`, the complete state contains all configured channels, and flashing occurs once.

- [ ] **Step 2: Verify RED**

Expected: current endpoint changes only `data/timers/<controller>.json` and leaves configuration unchanged.

- [ ] **Step 3: Implement the compatibility wrapper**

Translate `clock_window` to `{kind: "daily_window", on_time, off_time}`. Translate `cycle` to `{kind: "cycle", on_seconds, off_seconds, start_at_seconds, unit}`, preserving an existing valid unit when the request omits it. Save the updated controllers configuration, then call the Task 2 helper once. Remove the direct call to `patch_channel_schedule` from this request path.

- [ ] **Step 4: Run config API and CLI tests**

Expected: per-channel API and CLI behavior remains available through the new path.

### Task 4: Simplify the Dashboard to One Apply

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `channel.editor` and latest event report.
- Produces: clock form values from semantic metadata, with report reconstruction only when metadata is missing.

- [ ] **Step 1: Add failing page-source assertions**

Assert the rendered page passes `channel` into `clockValuesForEvent`, checks `channel.editor.kind === "daily_window"`, includes exactly one controller apply fetch, and contains no channel schedule fetch in `submitScheduleEditor`.

- [ ] **Step 2: Verify RED**

Expected: the page ignores saved clock metadata and includes the per-channel POST loop.

- [ ] **Step 3: Implement the browser changes**

Return saved `on_time` and `off_time` from `clockValuesForEvent(channel, event)` when present. Otherwise retain current report reconstruction. Remove the post-apply loop entirely; keep local `syncSavedEditorMetadata` updates.

- [ ] **Step 4: Run page tests**

Expected: all `tests.test_pages` tests pass after updating obsolete expectations.

### Task 5: Make the API Test Page Show Every Scheduler Workflow

**Files:**
- Modify: `plamp_web/pages.py`
- Test: `tests/test_pages.py`
- Modify: `docs/openapi.json` only through the repository's documented regeneration path if endpoint schema changes require it.

**Interfaces:**
- Documents: controller read, complete config save, controller apply, report request, and per-channel cycle/daily update.

- [ ] **Step 1: Add failing API-page coverage assertions**

Assert rendered HTML contains copyable curl examples and runnable controls for:

- `GET /api/controllers/{controller}`
- `PUT /api/config/controllers`
- `POST /api/controllers/{controller}/apply`
- `POST /api/controllers/{controller}/commands/report`
- `POST /api/controllers/{controller}/channels/{channel}/schedule` with both cycle and daily-window JSON examples

- [ ] **Step 2: Verify RED**

Expected: several scheduler workflow examples are absent.

- [ ] **Step 3: Add concise fieldsets and handlers**

Use the page's existing copy-curl and request helper patterns. Clearly label direct controller-state PUT as a low-level/legacy operation rather than the normal schedule workflow.

- [ ] **Step 4: Run page tests**

Expected: all page tests pass.

### Task 6: Full Verification and Commit

**Files:**
- Verify all modified source, tests, spec, and plan files.

- [ ] **Step 1: Run narrow suites**

```bash
/home/hugo/.local/bin/uv run python -m unittest tests.test_timer_schedule tests.test_config_api tests.test_pages tests.test_plamp_cli -v
```

Expected: zero failures.

- [ ] **Step 2: Run syntax and diff checks**

```bash
python3 -m py_compile plamp_web/timer_schedule.py plamp_web/server.py plamp_web/pages.py
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add plamp_web/timer_schedule.py plamp_web/server.py plamp_web/pages.py tests/test_timer_schedule.py tests/test_config_api.py tests/test_pages.py tests/test_plamp_cli.py docs/superpowers/specs/2026-07-14-atomic-scheduler-apply-design.md docs/superpowers/plans/2026-07-14-atomic-scheduler-apply.md
git commit -m "Apply Pico schedules atomically"
```

- [ ] **Step 4: Do not deploy automatically**

Report test evidence and ask before restarting the live service, because deployment will affect the controller currently running the restored lights schedule.
