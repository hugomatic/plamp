# Plamp8 Controller Provisioning and Import

## Goal

A Plamp8 controller should arrive with channel identities that match the writing
on its box, enforce disabled outputs locally, and install on a Plamp host without
creating a surprising empty controller. Communication with an unassigned USB
Pico begins only after the user explicitly asks to add it.

The first implementation remains deliberately small: complete reports, one
Plamp8 hardware profile, explicit provisioning, and explicit import. Delta
reports, checksums, automatic discovery conversations, and general controller
profile management are out of scope.

## User-facing principles

- USB enumeration may identify a possible Pico by operating-system metadata, but
  Plamp must not open it, request a report, reflash it, or send commands merely
  because it was plugged in.
- The user initiates communication with **Add/import controller**.
- Import observes and records controller state. It never changes outputs,
  schedules, firmware, or controller storage.
- Provisioning is a separate, visibly mutating operation. The UI must call it
  **Upgrade, provision, and import** and preview its effects before confirmation.
- Host desired configuration and Pico observed state remain distinct. Plamp
  commits imported host configuration only after receiving and validating a
  complete report.
- Device IDs are their only names. There is no separate device label.

## Web UX conventions

The workflow uses progressive disclosure and conventional action naming:

- The configuration page replaces **Pico schedulers** with the exact heading
  **Plamp Pico relay controllers**. Firmware diagnostics may still expose the
  technical family name `pico_scheduler`.
- An unassigned candidate appears as a compact row containing its stable USB
  serial and operating-system description. Its primary action is
  **Add/import controller**.
- Inspection is read-only. While it runs, the selected row shows bounded
  progress and remains associated with the same serial; the rest of Settings
  remains usable.
- A compatible provisioned controller receives an **Import** confirmation that
  previews only the host configuration to be created.
- A controller requiring mutation receives a distinct **Upgrade, provision,
  and import** confirmation. The confirmation shows the before/after channel
  table, firmware change, restart warning, preserved schedules, and channels
  that will be forced off.
- Primary actions use verbs that describe their effects. Generic **Save** does
  not stand in for inspection, import, upgrade, or provisioning.
- Success returns the user to the existing controller page with configured and
  live state visible. Failure leaves the preview and evidence available for
  retry or diagnosis; it does not redirect to an apparently empty controller.
- Technical firmware identity and raw report details are available in an
  expandable diagnostics section without dominating the normal path.
- Buttons, confirmations, progress, errors, focus handling, and tables remain
  keyboard accessible and do not rely on color alone.

Confirmation obtains one fresh report from the selected USB serial. If it no
longer matches the preview, the operation stops and shows the updated preview.

## Canonical Plamp8 profile

The profile is keyed by GPIO pin because provisioning replaces prototype IDs
while preserving the program already associated with each physical output.

| GPIO pin | Device ID | Initial enabled state |
| ---: | --- | --- |
| 21 | `ph_up` | disabled |
| 20 | `ph_down` | disabled |
| 19 | `agitator` | disabled |
| 18 | `nutrients` | disabled |
| 17 | `pump` | enabled |
| 16 | `fan` | enabled |
| 15 | `lights_1` | enabled |
| 14 | `lights_2` | enabled |

The same exact mapping is the contract for controller provisioning and Plamp8
box lettering. The current CAD names `Lights` and `Aux` are stale and must be
corrected directly to `Lights 1` and `Lights 2`.

## Device IDs and display names

New device IDs use lowercase snake case. User-facing pages derive a display name
by replacing underscores with spaces and uppercasing the first character:

- `pump` becomes `Pump`;
- `ph_up` becomes `Ph up`;
- `lights_1` becomes `Lights 1`.

Settings and diagnostics continue to expose the exact raw ID. Controller and
camera labels are unaffected; this design removes only scheduled-device labels.
An existing device-label key is ignored and omitted the next time that
configuration is successfully written; it never renames the device ID. This
does not require a standalone migration framework.

## Firmware state and disabled outputs

The scheduler protocol gains a required Boolean `enabled` field on every device.
This is a protocol compatibility change and therefore advances the firmware
protocol version. Complete reports include `enabled` alongside the existing ID,
type, pin, timing, pattern, and current value.

For an enabled device, existing scheduler and pulse behavior remains unchanged.
For a disabled device, the Pico itself must:

1. drive the logical output to `0` when the disabled state is applied;
2. restore logical `0` on boot before ordinary scheduling begins;
3. exclude the device from schedule advancement and output transitions;
4. retain its stored pattern and phase without executing them;
5. continue including it in complete reports with `enabled: false` and
   `current_value: 0`; and
6. reject pulse or other commands that could energize it with a structured
   disabled-device error.

There is no configurable safe value in this slice. Logical `0` is the Plamp8
safe-off value. Enabling a channel is an explicit configuration transaction;
the proposal supplies the schedule and phase that will become active.

The Pico validates the complete proposed state before persistence or output
changes. Configure verification compares `enabled` in addition to the existing
static fields.

## Explicit add and compatibility check

An unassigned candidate initially exposes only non-invasive operating-system
facts such as USB serial, vendor, model, and tty candidate. Clicking
**Add/import controller** authorizes a bounded serial transaction:

1. open only the selected serial device;
2. request one fresh complete report;
3. validate firmware family, revision, protocol, and report structure;
4. compare the reported device mapping with the selected Plamp8 profile; and
5. present the next applicable action.

The host does not create or save a controller merely because the serial port
opened. A missing, malformed, or incompatible report produces a specific error
and leaves host configuration unchanged.

If the controller already runs the expected firmware and reports the complete
profile, the offered action is **Import**. If it runs the immediately preceding
known scheduler protocol or does not match the Plamp8 profile, the offered
action is **Upgrade, provision, and import**. Arbitrary unidentified firmware is
rejected rather than handled by a general compatibility framework.

## Upgrade, provision, and import transaction

The current installed Plamp8 reports current protocol 2 firmware and prototype
IDs `one` through `eight`. Once the enabled-state protocol ships, the explicit
provisioning transaction performs this controlled transition:

1. Acquire the selected Pico lock and obtain a fresh, valid protocol 2 report.
2. Save the complete pre-change report as recovery evidence.
3. Join each reported device to the Plamp8 profile by GPIO pin.
4. Preserve type, pattern, and captured phase for every matched pin.
5. Replace the prototype ID with the profile ID.
6. Set GPIO 21, 20, 19, and 18 disabled; provisioning will intentionally drive
   those four outputs off.
7. Set GPIO 17, 16, 15, and 14 enabled and preserve their schedules and captured
   phases.
8. Render and install the expected generic scheduler firmware and its complete
   provisioned state, then reset and rediscover the selected USB serial.
9. Require a fresh complete report with the expected firmware identity, exact
   profile IDs and pins, expected enabled states, and preserved patterns.
10. Only after verification, import the reported controller and devices into
    host configuration.

The confirmation explains that the firmware upgrade restarts the Pico and may
briefly drive outputs safe-off. It lists the four channels that will remain
disabled. It does not claim that a firmware restart can preserve electrical
output continuously.

If validation fails before mutation, nothing changes. If flashing,
rediscovery, configuration, or verification fails after mutation, Plamp does
not commit the host import or claim success. It retains the captured report,
raw serial evidence, and failed stage for explicit recovery. It does not
silently retry a mutating operation.

## Read-only import

Import consumes a fresh, compatible complete report and creates or fills the
host controller bound to that Pico serial. For the existing empty `plamp8`
controller, it fills that controller rather than creating a duplicate.

Import records:

- controller firmware identity and Pico USB serial;
- device ID, pin, output type, and enabled state;
- exact pattern and captured runtime phase; and
- report interval when available.

A two-step on/off pattern may be represented as a cycle editor only when that
conversion is lossless. Plamp must not infer that a reported pattern originated
as a host-clock daily window. Patterns that cannot be losslessly represented by
an existing semantic editor remain exact event patterns.

Import sends only the read-only report request. It does not send a mutating
command, reapply the captured state, restart the controller, reset phase,
disable channels, or turn outputs on or off.

## Controller pages

All `/controllers/{id}` pages distinguish desired host configuration from
observed Pico state:

- When host devices exist, show **Configured channels**.
- When host devices are empty and a valid report contains devices, show
  **N channels found on controller**, display the observed IDs, pins, types,
  schedules, and states, and offer the applicable import or provisioning action.
- When a valid report contains an empty device list, show
  **Controller reports 0 channels**.
- When no valid report is available, show
  **Unable to read controller configuration** with the concrete health error.

The existing **No configured pins** message must not conceal reported channels.
Observed channels are clearly marked as observed until import succeeds. Pulse
controls must not treat an observed-but-unimported pin as host-authorized, and a
disabled imported channel cannot be pulsed.

## Settings and later edits

The settings page calls these devices **channels** where that is clearer to the
user. Remove the scheduled-device **Label** column and input entirely. Settings
edits the canonical device ID directly and shows its derived display name; the
device ID is the only editable channel name. Controller and camera label fields
remain unchanged.

Saving controller assignment remains a host operation and does not implicitly
probe or configure hardware. After import, changing a channel ID or enabled
state is a verified runtime configuration transaction, not a firmware reflash.
Unchanged schedules and phases are preserved. Disabling is applied immediately
and verified as off; renaming an ID alone must not toggle an output or reset its
phase.

## Shared operation and agent CLI

Keep the implementation narrow. One shared library operation evaluates or adds
a controller. It discovers the selected serial, reads and validates one fresh
report, decides whether the action is read-only import or provisioning followed
by import, and returns the before/after preview. With `apply=false` it stops
there. With `apply=true` it imports directly unless provisioning was also
explicitly allowed. A required but unauthorized firmware change is an error.
The operation verifies success and commits the host controller. The web service
and direct CLI call this same operation; the browser contains no firmware or
migration logic.

The primary direct CLI supports the complete workflow even when `plamp-web` is
stopped:

```bash
plamp controllers candidates
plamp controllers add plamp8 --serial 9d480174e373e801 --profile plamp8
plamp controllers add plamp8 --serial 9d480174e373e801 --profile plamp8 --apply
plamp controllers add plamp8 --serial 9d480174e373e801 --profile plamp8 --provision --apply
```

`candidates` is non-invasive and uses operating-system enumeration only. `add`
without `--apply` is the explicit read-only inspection and preview. `add` with
`--apply` obtains a new report and permits only read-only hardware import. The
additional `--provision` flag explicitly authorizes firmware and output changes.
There are no interactive prompts, saved plan documents, confirmation tokens, or
a general provisioning framework.

The CLI remains agent-safe: stdout is compact JSON, diagnostics go to stderr,
`--timeout` bounds hardware work, and nonzero exit status indicates failure.
Success states whether hardware changed, whether a reset occurred, whether host
configuration changed, and whether verification passed. Failure identifies the
stage and preserves the recovery evidence path when hardware mutation began.

The web client uses one thin preview/apply REST operation backed by the same
library function. REST is not a dependency of the direct `plamp` command. Both
interfaces use stable USB serials and the existing cross-process Pico and
configuration locks.

## Boundaries

This slice does not add:

- labels to Pico configuration or reports;
- automatic communication with every attached Pico;
- automatic firmware upgrades on discovery or health polling;
- delta reports, configuration checksums, sequence reconstruction, or periodic
  full-snapshot recovery;
- configurable output polarity or safe values;
- support for arbitrary historical scheduler protocols; or
- automatic reconciliation when host and Pico state later diverge.

Complete reports remain the only report format for now.

## Verification

Unit and fake-serial coverage must prove:

- USB enumeration alone performs no serial exchange;
- the explicit add action checks firmware identity before offering import or
  provisioning;
- malformed, unidentified, and unsupported reports do not create host config;
- profile mapping uses pins and produces the eight exact IDs and enabled states;
- device-display humanization is consistent across dashboard and controller
  pages;
- a config rewrite removes obsolete device labels without renaming IDs;
- read-only import sends no Pico command and preserves reported patterns and
  phases;
- import fills the existing serial-matched empty controller instead of creating
  a duplicate;
- disabled GPIO and PWM outputs are driven to zero, do not advance, remain off
  after reboot, continue reporting, and reject pulses;
- enabled outputs retain existing scheduling and pulse behavior;
- provisioning preserves schedules by pin for the four enabled Plamp8 outputs;
- configure verification includes `enabled`; and
- every controller-page state has distinct, accurate copy and available
  actions;
- web confirmation refreshes the selected report and stops when the applicable
  action changed;
- direct CLI discovery performs no serial I/O and `controllers add` without
  `--apply` performs only the selected bounded report transaction;
- CLI preview and apply return the same simple result shape;
- CLI stdout remains valid JSON while progress and diagnostics remain on
  stderr; and
- web, REST, and CLI adapters produce the same preview and result from the
  shared operation.

Hardware verification on the installed Plamp8 must be explicitly authorized
because it reflashes and resets the live Pico. Before execution, confirm manual
switch and load safety. Verification then checks the preview, captured backup,
firmware identity, all eight IDs, the four disabled outputs remaining off, the
four enabled schedules being preserved, successful host import, and correct
controller-page display.
