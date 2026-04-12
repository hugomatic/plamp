from __future__ import annotations

import html
import json
from typing import Any


def render_settings_page(summary: dict[str, Any]) -> str:
    host = summary["host"]
    host_time = summary.get("host_time") if isinstance(summary.get("host_time"), dict) else {}
    picos = summary["picos"]
    networks = host["network"]

    pico_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('role') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('port') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('usb_device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('serial') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('vendor_id') or '-'))}:{html.escape(str(item.get('product_id') or '-'))}</td>"
        "</tr>"
        for item in picos
    ) or '<tr><td colspan="5">No Picos found.</td></tr>'

    network_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('device') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('ipv4') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('network') or '-'))}</td>"
        "</tr>"
        for item in networks
    ) or '<tr><td colspan="3">No network devices found.</td></tr>'

    software_rows = (
        "<tr>"
        "<td>mpremote</td>"
        f"<td><code>{html.escape(str(summary['tools']['mpremote'] or 'not found'))}</code></td>"
        "</tr>"
        "<tr>"
        "<td>pyserial</td>"
        f"<td><code>{html.escape(str(summary['tools']['pyserial']))}</code></td>"
        "</tr>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plamp settings</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; max-width: 960px; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f4f4f4; padding: .1rem .25rem; }}
    footer {{ color: #555; font-size: .9rem; margin-top: 2rem; }}
    .host-clock {{ color: #555; font-size: .95rem; }}
  </style>
</head>
<body>
  <nav><a href="/">Plamp</a> | <a href="/timers/test">Timer test</a> | <a href="/settings.json">Settings JSON</a></nav>
  <h1>Plamp settings</h1>
  <p class="host-clock"><strong>Host time:</strong> {html.escape(str(host_time.get("display") or "-"))}</p>
  <h2>Picos</h2>
  <table>
    <thead><tr><th>Role</th><th>Port</th><th>USB Device</th><th>Serial</th><th>USB ID</th></tr></thead>
    <tbody>{pico_rows}</tbody>
  </table>

  <h2>Network</h2>
  <p><strong>Hostname:</strong> {html.escape(host['hostname'])}</p>
  <table>
    <thead><tr><th>Device</th><th>IPv4</th><th>Network</th></tr></thead>
    <tbody>{network_rows}</tbody>
  </table>

  <h2>Software</h2>
  <table>
    <thead><tr><th>Tool</th><th>Path</th></tr></thead>
    <tbody>{software_rows}</tbody>
  </table>

  <footer>Refreshing in <span id="refresh-countdown">30</span>s</footer>
  <script>
    let seconds = 30;
    const countdown = document.getElementById("refresh-countdown");
    setInterval(() => {{
      seconds -= 1;
      if (seconds <= 0) {{
        window.location.reload();
        return;
      }}
      countdown.textContent = String(seconds);
    }}, 1000);
  </script>
</body>
</html>"""


def render_timer_dashboard_page(
    roles: list[str],
    time_format: str,
    channels_by_role: dict[str, list[dict[str, Any]]] | None = None,
    host_seconds_since_midnight: int = 0,
) -> str:
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plamp</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }
    nav { margin-bottom: 1.5rem; }
    a { color: #174ea6; }
    button { border: 1px solid #222; border-radius: 6px; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; background: #fff; }
    input, select { box-sizing: border-box; padding: .35rem; }
    .host-clock { color: #555; font-size: .95rem; margin: -.5rem 0 1rem; }
    .status-board { display: grid; gap: .75rem; margin: 1rem 0; max-width: 980px; }
    .timer-card { border: 1px solid #ccc; border-radius: 6px; padding: .75rem; }
    .timer-top { align-items: baseline; display: flex; gap: .75rem; justify-content: space-between; }
    .timer-name { font-weight: 700; }
    .timer-value { border-radius: 6px; padding: .15rem .45rem; }
    .timer-value.on { background: #d9f7d9; }
    .timer-value.off { background: #eee; }
    .timer-meta { color: #555; font-size: .9rem; margin: .25rem 0 .5rem; }
    .timer-bar { background: #eee; border-radius: 6px; height: .65rem; overflow: hidden; }
    .timer-fill { background: #3b7f4a; height: 100%; width: 0; }
    .timer-fill.off { background: #888; }
    .timer-actions { margin-top: .65rem; }
    .timer-editor { border: 1px solid #ccc; border-radius: 6px; display: grid; gap: .65rem; margin: 1rem 0; max-width: 980px; padding: .75rem; }
    .timer-editor[hidden] { display: none; }
    .editor-row[hidden] { display: none; }
    .editor-row { align-items: end; display: flex; flex-wrap: wrap; gap: .75rem; }
    .editor-row label { display: grid; gap: .25rem; }
    .editor-row select, .editor-row input { min-width: 8rem; }
    .editor-note { color: #555; font-size: .9rem; }
    .editor-error { color: #9a3412; font-weight: 600; }
    .editor-success { color: #166534; font-weight: 600; }
  </style>
</head>
<body>
  <nav><a href="/settings">Settings</a></nav>
  <h1>Plamp</h1>
  <h2>Timers</h2>
  <p class="host-clock">Host time: <span id="host-clock">--:--</span></p>
  <p id="timer-stream-status">Connecting...</p>
  <div id="timer-status-board" class="status-board">Waiting for timer report...</div>
  <div id="timer-editor-panel" class="timer-editor" hidden></div>
  <footer>Refreshing in <span id="refresh-countdown">30</span>s</footer>

  <script>
    const clockTimeFormat = __TIME_FORMAT__;
    const timerRoles = __ROLES__;
    const timerChannels = __CHANNELS__;
    let timerHostSecondsAtLoad = __HOST_SECONDS__;
    let timerHostLoadedAt = Date.now();
    const timerStatus = document.getElementById("timer-stream-status");
    const timerBoard = document.getElementById("timer-status-board");
    const timerEditorPanel = document.getElementById("timer-editor-panel");
    const hostClock = document.getElementById("host-clock");
    const refreshCountdown = document.getElementById("refresh-countdown");
    let refreshSeconds = 30;
    const timerEventSources = new Map();
    const timerMessages = new Map();

    function formatChangeTime(secondsFromNow) {
      const when = new Date(Date.now() + secondsFromNow * 1000);
      if (clockTimeFormat === "24h") {
        return when.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hour12: false});
      }
      return when.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    }

    function formatChangeLabel(secondsFromNow) {
      if (!Number.isFinite(Number(secondsFromNow))) return "?";
      const seconds = Math.max(0, Math.ceil(Number(secondsFromNow)));
      return formatChangeTime(seconds) + " (" + seconds + " secs)";
    }

    function secondsToClock(seconds) {
      const normalized = ((seconds % 86400) + 86400) % 86400;
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      if (clockTimeFormat === "24h") {
        return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
      }
      const hour = hours % 12 || 12;
      const suffix = hours < 12 ? "AM" : "PM";
      return hour + ":" + String(minutes).padStart(2, "0") + " " + suffix;
    }

    function hostSecondsNow() {
      const elapsed = Math.floor((Date.now() - timerHostLoadedAt) / 1000);
      return (timerHostSecondsAtLoad + elapsed) % 86400;
    }

    function tickPageRefresh() {
      refreshSeconds -= 1;
      if (refreshSeconds <= 0) {
        window.location.reload();
        return;
      }
      refreshCountdown.textContent = String(refreshSeconds);
    }

    async function refreshHostClock() {
      if (!hostClock) return;
      try {
        const response = await fetch("/api/host-time");
        const data = await response.json();
        if (response.ok && typeof data.display === "string") {
          hostClock.textContent = data.display;
          if (Number.isFinite(Number(data.seconds_since_midnight))) {
            timerHostSecondsAtLoad = Number(data.seconds_since_midnight);
            timerHostLoadedAt = Date.now();
          }
          return;
        }
      } catch (error) {
      }
      hostClock.textContent = secondsToClock(hostSecondsNow());
    }

    function currentTimerStep(event) {
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (!pattern.length) return null;
      const durations = pattern.map((step) => Number(step.dur));
      if (durations.some((duration) => !Number.isFinite(duration) || duration <= 0)) return null;
      const total = durations.reduce((sum, duration) => sum + duration, 0);
      let cycleT = Number(event.cycle_t ?? event.elapsed_t ?? event.current_t ?? 0);
      if (!Number.isFinite(cycleT)) cycleT = 0;
      if (Number(event.reschedule ?? 1)) {
        cycleT = ((cycleT % total) + total) % total;
      } else {
        cycleT = Math.min(Math.max(cycleT, 0), total);
      }
      let start = 0;
      for (let index = 0; index < pattern.length; index += 1) {
        const end = start + durations[index];
        if (cycleT < end || index === pattern.length - 1) {
          return {step: pattern[index], elapsed: Math.max(0, cycleT - start), duration: durations[index], remaining: Math.max(0, end - cycleT)};
        }
        start = end;
      }
      return null;
    }

    function timerEventsFromMessage(message) {
      const candidates = [
        message?.report?.content?.events,
        message?.last_report?.content?.events,
        message?.content?.events,
        message?.events,
      ];
      return candidates.find((events) => Array.isArray(events)) || [];
    }

    function channelForEvent(role, event, index) {
      const channels = timerChannels[role] || [];
      const eventId = event.id || "pin-" + (event.ch ?? index);
      return channels.find((channel) => channel.id === eventId) || {
        role,
        id: eventId,
        name: event.id || "pin " + (event.ch ?? index),
        pin: event.ch,
        type: event.type || "gpio",
        default_editor: "cycle",
      };
    }

    function twoStepDurations(event) {
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (pattern.length !== 2) return null;
      const on = Number(pattern[0].dur);
      const off = Number(pattern[1].dur);
      const onValue = Number(pattern[0].val);
      const offValue = Number(pattern[1].val);
      if (!Number.isFinite(on) || !Number.isFinite(off) || on <= 0 || off <= 0 || onValue <= 0 || offValue !== 0) return null;
      return {on, off, total: on + off};
    }

    function chooseUnit(seconds) {
      if (seconds % 3600 === 0) return {value: seconds / 3600, unit: "hours"};
      if (seconds % 60 === 0) return {value: seconds / 60, unit: "minutes"};
      return {value: seconds, unit: "seconds"};
    }

    function unitMultiplier(unit) {
      if (unit === "hours") return 3600;
      if (unit === "minutes") return 60;
      return 1;
    }

    function secondsToTimeInput(seconds) {
      const normalized = ((seconds % 86400) + 86400) % 86400;
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
    }

    function clockValuesForEvent(event) {
      const durations = twoStepDurations(event);
      if (!durations || durations.total !== 86400) return {on: "06:00", off: "18:00"};
      const cycleT = Number(event.cycle_t ?? event.current_t ?? 0) || 0;
      const onSeconds = ((hostSecondsNow() - cycleT) % 86400 + 86400) % 86400;
      return {on: secondsToTimeInput(onSeconds), off: secondsToTimeInput(onSeconds + durations.on)};
    }

    function showEditorMessage(message, className, text) {
      message.className = "editor-message" + (className ? " " + className : "");
      message.textContent = text;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function openScheduleEditor(role, event, index) {
      const channel = channelForEvent(role, event, index);
      const durations = twoStepDurations(event) || {on: 60, off: 60, total: 120};
      const onUnit = chooseUnit(durations.on);
      const offUnit = chooseUnit(durations.off);
      const clock = clockValuesForEvent(event);
      timerEditorPanel.hidden = false;
      timerEditorPanel.dataset.role = role;
      timerEditorPanel.dataset.channelId = channel.id;
      timerEditorPanel.innerHTML = `
        <form id="timer-schedule-form">
          <div class="timer-top"><strong>Edit ${escapeHtml(channel.name)}</strong><span class="editor-note">${escapeHtml(role)} / pin ${escapeHtml(channel.pin ?? "?")} / ${escapeHtml(channel.type || "gpio")}</span></div>
          <div class="editor-row">
            <label>Set as
              <select name="mode">
                <option value="cycle">Cycle set</option>
                <option value="clock_window">24h set</option>
              </select>
            </label>
          </div>
          <div class="editor-row cycle-fields">
            <label>On for <input name="onValue" type="number" min="1" step="1" value="${onUnit.value}"></label>
            <label>Unit <select name="onUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
            <label>Off for <input name="offValue" type="number" min="1" step="1" value="${offUnit.value}"></label>
            <label>Unit <select name="offUnit"><option value="seconds">seconds</option><option value="minutes">minutes</option><option value="hours">hours</option></select></label>
            <label>Start at <input name="startAtSeconds" type="number" min="0" step="1" value="0"></label>
            <span class="editor-note">Seconds into the cycle. Use a value near the end of a step to test the next change.</span>
          </div>
          <div class="editor-row clock-fields">
            <label>On at <input name="onTime" type="time" value="${clock.on}"></label>
            <label>Off at <input name="offTime" type="time" value="${clock.off}"></label>
            <span class="editor-note">Applies using the host clock.</span>
          </div>
          <div class="editor-row">
            <button type="submit">Apply schedule</button>
            <button type="button" name="cancel">Close</button>
            <span class="editor-message" aria-live="polite"></span>
          </div>
        </form>
      `;
      const form = document.getElementById("timer-schedule-form");
      form.elements.mode.value = channel.default_editor === "clock_window" ? "clock_window" : "cycle";
      form.elements.onUnit.value = onUnit.unit;
      form.elements.offUnit.value = offUnit.unit;
      syncEditorMode(form);
      form.elements.mode.addEventListener("change", () => syncEditorMode(form));
      form.elements.cancel.addEventListener("click", () => { timerEditorPanel.hidden = true; });
      form.addEventListener("submit", submitScheduleEditor);
    }

    function syncEditorMode(form) {
      const clock = form.elements.mode.value === "clock_window";
      form.querySelector(".cycle-fields").hidden = clock;
      form.querySelector(".clock-fields").hidden = !clock;
    }

    async function submitScheduleEditor(event) {
      event.preventDefault();
      const form = event.currentTarget;
      const message = form.querySelector(".editor-message");
      showEditorMessage(message, "", "Saving...");
      const mode = form.elements.mode.value;
      const body = {mode};
      if (mode === "cycle") {
        body.on_seconds = Number(form.elements.onValue.value) * unitMultiplier(form.elements.onUnit.value);
        body.off_seconds = Number(form.elements.offValue.value) * unitMultiplier(form.elements.offUnit.value);
        body.start_at_seconds = Number(form.elements.startAtSeconds.value);
      } else {
        body.on_time = form.elements.onTime.value;
        body.off_time = form.elements.offTime.value;
      }
      try {
        const response = await fetch(`/api/timers/${encodeURIComponent(timerEditorPanel.dataset.role)}/channels/${encodeURIComponent(timerEditorPanel.dataset.channelId)}/schedule`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(body),
        });
        const text = await response.text();
        let parsed = null;
        try { parsed = JSON.parse(text); } catch (error) {}
        if (!response.ok) {
          throw new Error(parsed?.detail || text || `${response.status} ${response.statusText}`);
        }
        showEditorMessage(message, "editor-success", "Schedule applied. Waiting for report...");
      } catch (error) {
        showEditorMessage(message, "editor-error", String(error.message || error));
      }
    }

    function renderTimerStatus() {
      timerBoard.replaceChildren();
      let rendered = 0;
      for (const role of timerRoles) {
        const message = timerMessages.get(role);
        const events = timerEventsFromMessage(message);
        for (const [index, event] of events.entries()) {
          const channel = channelForEvent(role, event, index);
          const step = currentTimerStep(event);
          const value = Number(step?.step?.val ?? event.current_value ?? 0);
          const isOn = value > 0;
          const percent = step ? Math.max(0, Math.min(100, (step.elapsed / step.duration) * 100)) : 0;
          const card = document.createElement("div");
          card.className = "timer-card";
          const top = document.createElement("div");
          top.className = "timer-top";
          const name = document.createElement("span");
          name.className = "timer-name";
          name.textContent = role + " / " + channel.name;
          const badge = document.createElement("span");
          badge.className = "timer-value " + (isOn ? "on" : "off");
          badge.textContent = isOn ? "ON" : "OFF";
          top.append(name, badge);
          const meta = document.createElement("div");
          meta.className = "timer-meta";
          meta.textContent = "pin " + (event.ch ?? "?") + " | " + (event.type || "timer") + " | value " + value + " | changes at " + (step ? formatChangeLabel(step.remaining) : "?");
          const bar = document.createElement("div");
          bar.className = "timer-bar";
          const fill = document.createElement("div");
          fill.className = "timer-fill" + (isOn ? "" : " off");
          fill.style.width = percent + "%";
          bar.append(fill);
          const actions = document.createElement("div");
          actions.className = "timer-actions";
          const edit = document.createElement("button");
          edit.type = "button";
          edit.textContent = "Edit schedule";
          edit.addEventListener("click", () => openScheduleEditor(role, event, index));
          actions.append(edit);
          card.append(top, meta, bar, actions);
          timerBoard.append(card);
          rendered += 1;
        }
      }
      if (!rendered) {
        timerBoard.textContent = timerRoles.length ? "Waiting for timer reports..." : "No timers configured in data/config.json.";
      }
    }

    function stopTimerStreams() {
      for (const source of timerEventSources.values()) {
        source.close();
      }
      timerEventSources.clear();
      timerStatus.textContent = "Not streaming.";
    }

    function startTimerStreams() {
      stopTimerStreams();
      timerMessages.clear();
      renderTimerStatus();
      if (!timerRoles.length) {
        timerStatus.textContent = "No timers configured.";
        return;
      }
      timerStatus.textContent = `${timerRoles.length} pico board${timerRoles.length === 1 ? "" : "s"}: ${timerRoles.join(", ")}`;
      for (const role of timerRoles) {
        const source = new EventSource(`/api/timers/${encodeURIComponent(role)}?stream=true`);
        timerEventSources.set(role, source);
        for (const eventName of ["snapshot", "status", "report"]) {
          source.addEventListener(eventName, (event) => {
            timerMessages.set(role, JSON.parse(event.data));
            renderTimerStatus();
          });
        }
        source.onerror = () => { timerStatus.textContent = "Stream error or reconnecting..."; };
      }
    }

    window.addEventListener("beforeunload", stopTimerStreams);
    refreshHostClock();
    setInterval(refreshHostClock, 30000);
    setInterval(tickPageRefresh, 1000);
    startTimerStreams();
  </script>
</body>
</html>"""
    return (
        template.replace("__TIME_FORMAT__", json.dumps(time_format))
        .replace("__ROLES__", json.dumps(roles))
        .replace("__CHANNELS__", json.dumps(channels_by_role or {}))
        .replace("__HOST_SECONDS__", json.dumps(host_seconds_since_midnight))
    )


def render_timer_test_page(roles: list[str], default_role: str, default_payload: str, time_format: str) -> str:
    role_options = "\n".join(f'<option value="{html.escape(role)}"></option>' for role in roles)
    default_get_curl = f"curl http://localhost:8000/api/timers/{default_role}"
    default_stream_curl = f"curl -N 'http://localhost:8000/api/timers/{default_role}?stream=true'"
    default_put_curl = "\n".join([
        f"curl -X PUT 'http://localhost:8000/api/timers/{default_role}' " + chr(92),
        "  -H 'content-type: application/json' " + chr(92),
        "  --data-binary @- <<'JSON'",
        default_payload,
        "JSON",
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Timer API test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.4; }}
    fieldset {{ border: 1px solid #ccc; margin: 1rem 0 1.5rem; padding: 1rem; max-width: 980px; }}
    legend {{ font-weight: 700; }}
    label {{ display: block; margin: .6rem 0; }}
    input, textarea {{ box-sizing: border-box; padding: .35rem; }}
    textarea {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; min-height: 28rem; width: min(100%, 980px); }}
    button {{ border: 1px solid #222; border-radius: 6px; margin: .25rem .25rem .25rem 0; padding: .45rem .7rem; background: #fff; }}
    .row {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: .75rem 0; }}
    .radio-row label {{ display: inline-block; margin-right: 1rem; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    #put-curl-command, #stream-curl-command {{ white-space: pre-wrap; }}
    #stream-result {{ max-height: 18rem; white-space: pre-wrap; }}
    .status-board {{ display: grid; gap: .75rem; margin: .75rem 0; max-width: 980px; }}
    .timer-card {{ border: 1px solid #ccc; border-radius: 6px; padding: .75rem; }}
    .timer-top {{ align-items: baseline; display: flex; gap: .75rem; justify-content: space-between; }}
    .timer-name {{ font-weight: 700; }}
    .timer-value {{ border-radius: 6px; padding: .15rem .45rem; }}
    .timer-value.on {{ background: #d9f7d9; }}
    .timer-value.off {{ background: #eee; }}
    .timer-meta {{ color: #555; font-size: .9rem; margin: .25rem 0 .5rem; }}
    .timer-bar {{ background: #eee; border-radius: 6px; height: .65rem; overflow: hidden; }}
    .timer-fill {{ background: #3b7f4a; height: 100%; width: 0; }}
    .timer-fill.off {{ background: #888; }}
  </style>
</head>
<body>
  <nav><a href="/">Plamp</a> | <a href="/settings">Settings</a></nav>
  <h1>Timer API test</h1>

  <h2>GET</h2>
  <fieldset>
    <legend>Read timer state</legend>
    <label>Role
      <input id="get-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>
    <datalist id="timer-roles">{role_options}</datalist>
    <pre id="get-curl-command">{html.escape(default_get_curl)}</pre>
    <button id="get-state" type="button">GET current state</button>
    <div><span id="get-status">Ready.</span></div>
    <pre id="get-result">GET response will appear here.</pre>
  </fieldset>

  <fieldset>
    <legend>GET stream timer events</legend>
    <pre id="stream-curl-command">{html.escape(default_stream_curl)}</pre>
    <button id="start-stream" type="button">Start GET stream</button>
    <button id="stop-stream" type="button">Stop GET stream</button>
    <div><span id="stream-status">Not streaming.</span></div>
    <div id="timer-status-board" class="status-board">Start the GET stream to see timer status.</div>
    <pre id="stream-result">GET stream events will appear here.</pre>
  </fieldset>

  <h2>PUT</h2>
  <fieldset>
    <legend>Target</legend>
    <label>Role
      <input id="put-role" list="timer-roles" value="{html.escape(default_role)}">
    </label>
  </fieldset>

  <fieldset>
    <legend>Generate 5s pin test</legend>
    <label>Test pin <input id="test-pin" type="number" min="0" max="29" value="25"></label>
    <button id="generate-quick" type="button">Generate pin test</button>
  </fieldset>

  <fieldset>
    <legend>Generate pump/lights</legend>
    <div class="row">
      <label>Pump pin <input id="pump-pin" type="number" min="0" max="29" value="15"></label>
      <label>Pump on minutes <input id="pump-on" type="number" min="1" value="5"></label>
      <label>Pump off minutes <input id="pump-off" type="number" min="1" value="30"></label>
      <label>Lights pin <input id="lights-pin" type="number" min="0" max="29" value="2"></label>
      <label>Lights on <input id="lights-on" type="time" step="1" value="06:00:00"></label>
      <label>Lights off <input id="lights-off" type="time" step="1" value="18:00:00"></label>
    </div>
    <button id="generate-pump-lights" type="button">Generate pump/lights</button>
  </fieldset>

  <label>JSON payload
    <textarea id="payload">{html.escape(default_payload)}</textarea>
  </label>

  <h3>PUT curl</h3>
  <pre id="put-curl-command">{html.escape(default_put_curl)}</pre>
  <button id="put-state" type="button">PUT</button>
  <div><span id="put-status">Ready.</span></div>
  <pre id="put-result">PUT response will appear here.</pre>

  <script>
    const payload = document.getElementById("payload");
    const getRoleInput = document.getElementById("get-role");
    const putRoleInput = document.getElementById("put-role");
    const clockTimeFormat = {json.dumps(time_format)};
    let timerEventSource = null;

    function getRole() {{
      return getRoleInput.value.trim();
    }}

    function putRole() {{
      return putRoleInput.value.trim();
    }}

    function secondsSinceMidnight() {{
      const now = new Date();
      return now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    }}

    function timeToSeconds(value) {{
      const [h, m, s] = value.split(":").map(Number);
      return h * 3600 + m * 60 + (s || 0);
    }}

    function currentTForWindow(start, stop) {{
      const startSeconds = timeToSeconds(start);
      const stopSeconds = timeToSeconds(stop);
      let onDur = (stopSeconds - startSeconds + 86400) % 86400;
      if (onDur === 0) onDur = 86400;
      let offDur = 86400 - onDur;
      if (offDur === 0) offDur = 1;
      return (secondsSinceMidnight() - startSeconds + onDur + offDur) % (onDur + offDur);
    }}

    function doubleQuote(value) {{
      return JSON.stringify(value);
    }}

    function getCurlCommand() {{
      return "curl " + doubleQuote(`${{window.location.origin}}/api/timers/${{encodeURIComponent(getRole())}}`);
    }}

    function streamCurlCommand() {{
      return "curl -N " + doubleQuote(`${{window.location.origin}}/api/timers/${{encodeURIComponent(getRole())}}?stream=true`);
    }}

    function putCurlCommand() {{
      const url = `${{window.location.origin}}/api/timers/${{encodeURIComponent(putRole())}}`;
      const slash = String.fromCharCode(92);
      const newline = String.fromCharCode(10);
      return [
        "curl -X PUT " + doubleQuote(url) + " " + slash,
        "  -H " + doubleQuote("content-type: application/json") + " " + slash,
        "  --data-binary @- <<'JSON'",
        payload.value,
        "JSON",
      ].join(newline);
    }}

    function updateCurl() {{
      document.getElementById("get-curl-command").textContent = getCurlCommand();
      document.getElementById("stream-curl-command").textContent = streamCurlCommand();
      document.getElementById("put-curl-command").textContent = putCurlCommand();
    }}

    function setPayload(state) {{
      payload.value = JSON.stringify(state, null, 2);
      document.getElementById("put-status").textContent = "Payload generated. Edit it, then PUT.";
      document.getElementById("put-result").textContent = "";
      updateCurl();
    }}

    async function getState() {{
      const getStatus = document.getElementById("get-status");
      const getResult = document.getElementById("get-result");
      getStatus.textContent = "";
      getResult.textContent = "";
      if (!window.confirm(`GET /api/timers/${{getRole()}}?`)) {{
        getStatus.textContent = "Cancelled.";
        return;
      }}
      getStatus.textContent = "Loading...";
      try {{
        const response = await fetch(`/api/timers/${{encodeURIComponent(getRole())}}`);
        const text = await response.text();
        let display = text;
        if (response.ok) {{
          const parsed = JSON.parse(text);
          display = JSON.stringify(parsed, null, 2);
          payload.value = display;
          putRoleInput.value = getRole();
          updateCurl();
        }}
        getStatus.textContent = `${{response.status}} ${{response.statusText}}`;
        getResult.textContent = display;
      }} catch (error) {{
        getStatus.textContent = "Request failed.";
        getResult.textContent = String(error);
      }}
    }}

    function formatChangeTime(secondsFromNow) {{
      const when = new Date(Date.now() + secondsFromNow * 1000);
      if (clockTimeFormat === "24h") {{
        return when.toLocaleTimeString([], {{hour: "2-digit", minute: "2-digit", hour12: false}});
      }}
      return when.toLocaleTimeString([], {{hour: "numeric", minute: "2-digit"}});
    }}

    function currentTimerStep(event) {{
      const pattern = Array.isArray(event.pattern) ? event.pattern : [];
      if (!pattern.length) return null;
      const durations = pattern.map((step) => Number(step.dur));
      if (durations.some((duration) => !Number.isFinite(duration) || duration <= 0)) return null;
      const total = durations.reduce((sum, duration) => sum + duration, 0);
      let cycleT = Number(event.cycle_t ?? event.elapsed_t ?? event.current_t ?? 0);
      if (!Number.isFinite(cycleT)) cycleT = 0;
      if (Number(event.reschedule ?? 1)) {{
        cycleT = ((cycleT % total) + total) % total;
      }} else {{
        cycleT = Math.min(Math.max(cycleT, 0), total);
      }}
      let start = 0;
      for (let index = 0; index < pattern.length; index += 1) {{
        const end = start + durations[index];
        if (cycleT < end || index === pattern.length - 1) {{
          return {{step: pattern[index], elapsed: Math.max(0, cycleT - start), duration: durations[index], remaining: Math.max(0, end - cycleT)}};
        }}
        start = end;
      }}
      return null;
    }}

    function timerEventsFromMessage(message) {{
      const candidates = [
        message?.report?.content?.events,
        message?.last_report?.content?.events,
        message?.content?.events,
        message?.events,
      ];
      return candidates.find((events) => Array.isArray(events)) || [];
    }}

    function renderTimerStatus(message) {{
      const events = timerEventsFromMessage(message);
      const board = document.getElementById("timer-status-board");
      if (!events.length) return;
      board.replaceChildren();
      for (const [index, event] of events.entries()) {{
        const step = currentTimerStep(event);
        const value = Number(step?.step?.val ?? event.current_value ?? 0);
        const isOn = value > 0;
        const percent = step ? Math.max(0, Math.min(100, (step.elapsed / step.duration) * 100)) : 0;

        const card = document.createElement("div");
        card.className = "timer-card";

        const top = document.createElement("div");
        top.className = "timer-top";
        const name = document.createElement("span");
        name.className = "timer-name";
        name.textContent = event.id || "pin " + (event.ch ?? index);
        const badge = document.createElement("span");
        badge.className = "timer-value " + (isOn ? "on" : "off");
        badge.textContent = isOn ? "ON" : "OFF";
        top.append(name, badge);

        const meta = document.createElement("div");
        meta.className = "timer-meta";
        meta.textContent = "pin " + (event.ch ?? "?") + " | " + (event.type || "timer") + " | value " + value + " | changes at " + (step ? formatChangeLabel(step.remaining) : "?");

        const bar = document.createElement("div");
        bar.className = "timer-bar";
        const fill = document.createElement("div");
        fill.className = "timer-fill" + (isOn ? "" : " off");
        fill.style.width = percent + "%";
        bar.append(fill);

        card.append(top, meta, bar);
        board.append(card);
      }}
    }}

    function appendStreamEvent(eventName, data) {{
      const streamResult = document.getElementById("stream-result");
      const timestamp = new Date().toLocaleTimeString();
      let display = data;
      try {{
        const parsed = JSON.parse(data);
        renderTimerStatus(parsed);
        display = JSON.stringify(parsed, null, 2);
      }} catch (error) {{
      }}
      streamResult.textContent += `[${{timestamp}}] ${{eventName}}\n${{display}}\n\n`;
      if (streamResult.textContent.length > 20000) {{
        streamResult.textContent = streamResult.textContent.slice(-20000);
      }}
      streamResult.scrollTop = streamResult.scrollHeight;
    }}

    function stopTimerStream() {{
      if (timerEventSource) {{
        timerEventSource.close();
        timerEventSource = null;
      }}
      document.getElementById("stream-status").textContent = "Not streaming.";
    }}

    function startTimerStream() {{
      stopTimerStream();
      const role = getRole();
      const streamStatus = document.getElementById("stream-status");
      const streamResult = document.getElementById("stream-result");
      streamResult.textContent = "";
      streamStatus.textContent = `Connecting to /api/timers/${{role}}?stream=true...`;
      timerEventSource = new EventSource(`/api/timers/${{encodeURIComponent(role)}}?stream=true`);
      timerEventSource.onopen = () => {{
        streamStatus.textContent = `Streaming ${{role}}.`;
      }};
      for (const eventName of ["snapshot", "status", "report", "error", "keepalive"]) {{
        timerEventSource.addEventListener(eventName, (event) => appendStreamEvent(eventName, event.data));
      }}
      timerEventSource.onerror = () => {{
        streamStatus.textContent = "Stream error or reconnecting...";
      }};
    }}

    async function putState() {{
      const putStatus = document.getElementById("put-status");
      const putResult = document.getElementById("put-result");
      putStatus.textContent = "";
      putResult.textContent = "";
      const url = `/api/timers/${{encodeURIComponent(putRole())}}`;
      if (!window.confirm(`PUT ${{url}}?`)) {{
        putStatus.textContent = "Cancelled.";
        return;
      }}
      let parsed;
      try {{
        parsed = JSON.parse(payload.value);
      }} catch (error) {{
        putStatus.textContent = "Invalid JSON.";
        putResult.textContent = String(error);
        return;
      }}
      putStatus.textContent = "Saving...";
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 30000);
      try {{
        const response = await fetch(url, {{
          method: "PUT",
          headers: {{"content-type": "application/json"}},
          body: JSON.stringify(parsed),
          signal: controller.signal,
        }});
        const text = await response.text();
        let display = text;
        try {{
          display = JSON.stringify(JSON.parse(text), null, 2);
        }} catch (error) {{
        }}
        putStatus.textContent = `${{response.status}} ${{response.statusText}}`;
        putResult.textContent = display;
      }} catch (error) {{
        putStatus.textContent = "Request failed.";
        putResult.textContent = String(error);
      }} finally {{
        window.clearTimeout(timeout);
      }}
    }}

    document.getElementById("generate-quick").addEventListener("click", () => {{
      setPayload({{
        report_every: 10,
        events: [{{
          id: "test_pin",
          type: "gpio",
          ch: Number(document.getElementById("test-pin").value),
          current_t: 0,
          reschedule: 1,
          pattern: [{{val: 1, dur: 5}}, {{val: 0, dur: 5}}],
        }}],
      }});
    }});

    document.getElementById("generate-pump-lights").addEventListener("click", () => {{
      const lightsOn = document.getElementById("lights-on").value;
      const lightsOff = document.getElementById("lights-off").value;
      let lightsOnDur = (timeToSeconds(lightsOff) - timeToSeconds(lightsOn) + 86400) % 86400;
      if (lightsOnDur === 0) lightsOnDur = 86400;
      let lightsOffDur = 86400 - lightsOnDur;
      if (lightsOffDur === 0) lightsOffDur = 1;
      setPayload({{
        report_every: 10,
        events: [
          {{
            id: "pump",
            type: "gpio",
            ch: Number(document.getElementById("pump-pin").value),
            current_t: 0,
            reschedule: 1,
            pattern: [
              {{val: 1, dur: Number(document.getElementById("pump-on").value) * 60}},
              {{val: 0, dur: Number(document.getElementById("pump-off").value) * 60}},
            ],
          }},
          {{
            id: "lights",
            type: "gpio",
            ch: Number(document.getElementById("lights-pin").value),
            current_t: currentTForWindow(lightsOn, lightsOff),
            reschedule: 1,
            pattern: [{{val: 1, dur: lightsOnDur}}, {{val: 0, dur: lightsOffDur}}],
          }},
        ],
      }});
    }});

    document.getElementById("get-state").addEventListener("click", getState);
    document.getElementById("start-stream").addEventListener("click", startTimerStream);
    document.getElementById("stop-stream").addEventListener("click", stopTimerStream);
    document.getElementById("put-state").addEventListener("click", putState);
    getRoleInput.addEventListener("input", updateCurl);
    putRoleInput.addEventListener("input", updateCurl);
    payload.addEventListener("input", updateCurl);
    updateCurl();
  </script>
</body>
</html>"""
