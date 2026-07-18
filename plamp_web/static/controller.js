(() => {
  const loadStatus = document.getElementById("controller-load-status");
  const commandStatus = document.getElementById("command-status");
  const statusBody = document.getElementById("controller-status");
  const pinsBody = document.getElementById("configured-pins");
  const diagnosticsNode = document.getElementById("controller-diagnostics");
  const logNode = document.getElementById("serial-log");
  const pulsePinInput = document.getElementById("pulse-pin");
  const pulseSecondsInput = document.getElementById("pulse-seconds");
  const controls = ["report-now", "pulse-send", "refresh-diagnostics", "refresh-log"].map((id) => document.getElementById(id));
  let controller = "";
  let configuredPins = [];
  let controllerSource = null;

  function controllerIdFromPath() {
    const parts = location.pathname.split("/").filter(Boolean);
    if (parts.length !== 2 || parts[0] !== "controllers") throw new Error("Controller URL must be /controllers/{controller}.");
    const value = decodeURIComponent(parts[1]);
    if (!value) throw new Error("Controller ID is missing from the URL.");
    return value;
  }

  function setControlsDisabled(disabled) {
    for (const control of controls) control.disabled = disabled;
  }

  function setCommandStatus(text, error = false) {
    commandStatus.textContent = text;
    commandStatus.classList.toggle("error", error);
  }

  function addTableMessage(body, columns, message) {
    body.replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns;
    cell.textContent = message;
    row.append(cell);
    body.append(row);
  }

  function addFactRow(key, value) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    const content = document.createElement("td");
    const code = document.createElement("code");
    name.textContent = key;
    code.textContent = value === null || value === undefined ? "-" : String(value);
    content.append(code);
    row.append(name, content);
    statusBody.append(row);
  }

  function renderStatus(telemetry) {
    statusBody.replaceChildren();
    let rendered = 0;
    for (const key of ["state", "connected", "port", "serial", "last_seen", "last_error"]) {
      if (!(key in telemetry)) continue;
      addFactRow(key, telemetry[key]);
      rendered += 1;
    }
    if (!rendered) addTableMessage(statusBody, 2, "No monitor status.");
  }

  function configuredDevices(node) {
    const devices = node?.settings?.devices;
    if (!devices || typeof devices !== "object") return [];
    return Object.entries(devices).sort((left, right) => {
      const leftOrder = Number.isInteger(left[1]?.display_order) ? left[1].display_order : Number.MAX_SAFE_INTEGER;
      const rightOrder = Number.isInteger(right[1]?.display_order) ? right[1].display_order : Number.MAX_SAFE_INTEGER;
      return leftOrder - rightOrder;
    }).map(([id, device]) => ({id, ...device}));
  }

  function renderPins(devices) {
    pinsBody.replaceChildren();
    if (!devices.length) {
      addTableMessage(pinsBody, 7, "No configured pins.");
      return;
    }
    for (const device of devices) {
      const row = document.createElement("tr");
      for (const value of [device.label || device.id, device.id, device.pin, device.output_type || "gpio", device.visibility || "visible", device.programming || "enabled"]) {
        const cell = document.createElement("td");
        cell.textContent = value === null || value === undefined ? "" : String(value);
        row.append(cell);
      }
      const actionCell = document.createElement("td");
      const useButton = document.createElement("button");
      useButton.type = "button";
      useButton.className = "use-pin";
      useButton.textContent = "Use";
      useButton.addEventListener("click", () => {
        pulsePinInput.value = device.pin ?? "";
        pulsePinInput.focus();
      });
      actionCell.append(useButton);
      row.append(actionCell);
      pinsBody.append(row);
    }
  }

  function renderController(node) {
    const telemetry = node?.telemetry && typeof node.telemetry === "object" ? node.telemetry : {};
    configuredPins = configuredDevices(node);
    renderStatus(telemetry);
    renderPins(configuredPins);
    diagnosticsNode.textContent = JSON.stringify(telemetry, null, 2);
    const firstGpio = configuredPins.find((item) => (item.output_type || "gpio") === "gpio");
    if (firstGpio && firstGpio.pin !== undefined && firstGpio.pin !== null && pulsePinInput.value === "") pulsePinInput.value = firstGpio.pin;
  }

  function statusUrl() {
    const params = new URLSearchParams({path: `controllers.${controller}`});
    return `/api/status?${params.toString()}`;
  }

  async function refreshDiagnostics() {
    const response = await fetch(statusUrl());
    const data = await PlampWeb.responseJson(response, "controller status");
    const match = Array.isArray(data) ? data.find((entry) => entry?.path === `controllers.${controller}`) : null;
    if (!match || !match.value) throw new Error(`Controller ${controller} was not found.`);
    renderController(match.value);
    return match.value;
  }

  function logText(entries) {
    if (!Array.isArray(entries) || !entries.length) return "No serial lines captured.";
    return [...entries].reverse().map((entry) => `${entry.at || ""} ${(entry.direction || "?").toUpperCase()} ${entry.text || ""}`.trim()).join("\n");
  }

  async function refreshLog() {
    const response = await fetch(`/api/controllers/${encodeURIComponent(controller)}/serial-log`);
    const data = await PlampWeb.responseJson(response, "serial log");
    logNode.textContent = logText(data.entries);
  }

  function renderStreamEvent(data) {
    const telemetry = data?.telemetry && typeof data.telemetry === "object" ? data.telemetry : data;
    if (!telemetry || typeof telemetry !== "object") return;
    renderStatus(telemetry);
    diagnosticsNode.textContent = JSON.stringify(telemetry, null, 2);
    loadStatus.textContent = "Live controller stream connected.";
    loadStatus.classList.remove("error");
  }

  function startControllerStream() {
    controllerSource?.close();
    controllerSource = new EventSource(`/api/controllers/${encodeURIComponent(controller)}?stream=true`);
    for (const eventName of ["snapshot", "report", "status"]) {
      controllerSource.addEventListener(eventName, (event) => {
        try { renderStreamEvent(JSON.parse(event.data)); }
        catch (error) { setCommandStatus(`Invalid ${eventName} event: ${error.message || String(error)}`, true); }
      });
    }
    controllerSource.onerror = () => {
      loadStatus.textContent = "Stream disconnected; showing last valid report.";
      loadStatus.classList.add("error");
    };
  }

  function pinLabel(pin) {
    const channel = configuredPins.find((item) => Number(item.pin) === Number(pin));
    return channel ? (channel.label || channel.id || "") : "";
  }

  async function postCommand(url, body) {
    setCommandStatus("Sending...");
    const options = {method: "POST"};
    if (body) {
      options.headers = {"content-type": "application/json"};
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    const data = await PlampWeb.responseJson(response, "controller command");
    setCommandStatus(data.message || "Sent.");
    await refreshLog();
  }

  document.getElementById("report-now").addEventListener("click", async () => {
    try { await postCommand(`/api/controllers/${encodeURIComponent(controller)}/commands/report`); }
    catch (error) { setCommandStatus(error.message || String(error), true); }
  });
  document.getElementById("refresh-log").addEventListener("click", async () => {
    try { await refreshLog(); setCommandStatus("Log refreshed."); }
    catch (error) { setCommandStatus(error.message || String(error), true); }
  });
  document.getElementById("refresh-diagnostics").addEventListener("click", async () => {
    try { await refreshDiagnostics(); setCommandStatus("Diagnostics refreshed."); }
    catch (error) { setCommandStatus(error.message || String(error), true); }
  });
  document.getElementById("pulse-send").addEventListener("click", async () => {
    const pin = Number(pulsePinInput.value);
    const seconds = Number(pulseSecondsInput.value);
    if (!Number.isInteger(pin) || pin < 0 || pin > 29) { setCommandStatus("Enter a configured pin number.", true); return; }
    if (!Number.isInteger(seconds) || seconds <= 0) { setCommandStatus("Enter pulse seconds.", true); return; }
    const label = pinLabel(pin);
    const labelText = label ? ` "${label}"` : "";
    if (!window.confirm(`Are you sure you want to pulse pin ${pin}${labelText} for ${seconds} seconds?`)) return;
    try { await postCommand(`/api/controllers/${encodeURIComponent(controller)}/pins/${encodeURIComponent(pin)}/pulse`, {seconds}); }
    catch (error) { setCommandStatus(error.message || String(error), true); }
  });

  async function bootstrapController() {
    try {
      controller = controllerIdFromPath();
      document.getElementById("controller-heading").textContent = `${controller} Pico`;
      await Promise.all([
        PlampWeb.bootstrapShell({activePath: location.pathname, headingSuffix: `${controller} Pico`}),
        refreshDiagnostics(),
        refreshLog(),
      ]);
      setControlsDisabled(false);
      setCommandStatus("Ready.");
      loadStatus.textContent = "Controller loaded.";
      startControllerStream();
    } catch (error) {
      setControlsDisabled(true);
      loadStatus.textContent = `Controller setup failed: ${error.message || String(error)}`;
      loadStatus.classList.add("error");
      setCommandStatus("Unavailable.", true);
    }
  }

  window.addEventListener("beforeunload", () => controllerSource?.close());
  bootstrapController();
})();
