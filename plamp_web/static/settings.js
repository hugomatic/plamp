(() => {
  const schedulerBlocks = document.getElementById("scheduler-blocks");
  const cameraRows = document.getElementById("camera-rows");
  const loadStatus = document.getElementById("settings-load-status");
  const saveButtons = ["save-controllers", "save-devices", "save-cameras"].map((id) => document.getElementById(id));
  let detectedPicos = [];
  let detectedCameras = [];
  let hiddenControllers = {};
  let repoRootPath = "";

  function cleanObject(value) {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (item !== "" && item !== null && item !== undefined) result[key] = item;
    }
    return result;
  }

  function normalizeCameraKey(value) {
    return String(value || "").trim().replace(/[^A-Za-z0-9_-]+/g, "_");
  }

  function setSaveDisabled(disabled) {
    for (const button of saveButtons) button.disabled = disabled;
  }

  function showLoadStatus(message, error = false) {
    loadStatus.textContent = message;
    loadStatus.classList.toggle("error", error);
  }

  function showLoadError(message) {
    showLoadStatus(message, true);
  }

  function option(value, label, selected) {
    const item = document.createElement("option");
    item.value = value;
    item.textContent = label;
    item.selected = value === selected;
    return item;
  }

  function selectWithOptions(className, items, selected) {
    const select = document.createElement("select");
    select.className = className;
    for (const [value, label] of items) select.append(option(value, label, selected));
    return select;
  }

  function input(className, value = "", attributes = {}) {
    const item = document.createElement("input");
    item.className = className;
    item.value = value === null || value === undefined ? "" : String(value);
    for (const [name, attributeValue] of Object.entries(attributes)) item.setAttribute(name, String(attributeValue));
    return item;
  }

  function cell(child) {
    const td = document.createElement("td");
    td.append(child);
    return td;
  }

  function controllerPayload(controller) {
    if (controller?.payload && typeof controller.payload === "object") return controller.payload;
    return cleanObject({pico_serial: controller?.config?.pico_serial});
  }

  function controllerSettings(controller) {
    const settings = controller?.settings && typeof controller.settings === "object" ? structuredClone(controller.settings) : {};
    if (!settings.label && controller?.config?.label) settings.label = controller.config.label;
    return settings;
  }

  function semanticDevices(controller) {
    const settings = controllerSettings(controller);
    if (settings.devices && typeof settings.devices === "object") return settings.devices;
    const legacy = controller?.devices && typeof controller.devices === "object" ? controller.devices : {};
    const result = {};
    for (const [deviceId, device] of Object.entries(legacy)) {
      const config = device?.config || {};
      const deviceSettings = device?.settings || {};
      result[deviceId] = {
        pin: config.pin,
        label: config.label,
        output_type: config.output_type || "gpio",
        visibility: config.visibility || "visible",
        programming: deviceSettings.programming || "enabled",
        editor: deviceSettings.schedule || {kind: "cycle"},
      };
    }
    return result;
  }

  function picoOptions(selected) {
    const items = [["", "Unassigned"]];
    const seen = new Set();
    for (const pico of detectedPicos) {
      const serial = String(pico?.serial || "");
      if (!serial) continue;
      seen.add(serial);
      items.push([serial, `${serial} ${pico.port || ""}`.trim()]);
    }
    if (selected && !seen.has(selected)) items.push([selected, `${selected} (not detected)`]);
    return items;
  }

  function editorMode(device) {
    if (device?.programming === "disabled") return "disabled";
    if (device?.visibility === "hidden") return "hidden";
    return device?.editor?.kind === "daily_window" ? "clock_window" : "cycle";
  }

  function createControllerRow(controllerId, controller, isNew = false) {
    const row = document.createElement("tr");
    row.className = `controller-row${isNew ? " new-row" : ""}`;
    row.dataset.controllerKey = isNew ? "" : controllerId;
    const payload = controllerPayload(controller);
    const settings = controllerSettings(controller);
    const idInput = input("controller-id", controllerId, {placeholder: "pump_lights"});
    const labelInput = input("controller-label", settings.label || "", {placeholder: "Pump and lights"});
    labelInput.defaultValue = settings.label || "";
    const picoSelect = selectWithOptions("controller-pico-serial", picoOptions(String(payload.pico_serial || "")), String(payload.pico_serial || ""));
    picoSelect.dataset.defaultValue = String(payload.pico_serial || "");
    const typeSelect = selectWithOptions("controller-type", [["pico_scheduler", "pico_scheduler"]], String(controller?.type || "pico_scheduler"));
    const hiddenType = cell(typeSelect);
    hiddenType.hidden = true;
    row.append(cell(idInput), cell(labelInput), cell(picoSelect), hiddenType);
    if (isNew) idInput.addEventListener("input", () => hydrateControllerRowFromHidden(row));
    return row;
  }

  function createDeviceRow(deviceId, device, controllerId, isNew = false) {
    const row = document.createElement("tr");
    row.className = `device-row${isNew ? " new-row" : ""}`;
    row.dataset.deviceId = deviceId;
    row.dataset.deviceController = controllerId;
    row.dataset.deviceEditorJson = JSON.stringify(device?.editor || {});
    const mode = editorMode(device || {});
    row.append(
      cell(input("device-id", deviceId, {placeholder: "pump"})),
      cell(input("device-label", device?.label || "", {placeholder: "Water pump"})),
      cell(input("device-pin", device?.pin, {type: "number", min: 0, max: 29})),
      cell(selectWithOptions("device-type", [["gpio", "gpio"], ["pwm", "pwm"]], device?.output_type || "gpio")),
      cell(selectWithOptions("device-editor", [["cycle", "cycle"], ["clock_window", "clock_window"], ["disabled", "disabled"], ["hidden", "hidden"]], mode)),
    );
    return row;
  }

  function createSchedulerBlock(controllerId, controller, devices, isNew = false) {
    const block = document.createElement("div");
    block.className = `pico-scheduler-block${isNew ? " pico-scheduler-new" : ""}`;
    block.dataset.controllerKey = isNew ? "" : controllerId;
    const controllerTable = document.createElement("table");
    controllerTable.innerHTML = "<thead><tr><th>ID</th><th>Label</th><th>Assigned peripheral</th></tr></thead>";
    const controllerBody = document.createElement("tbody");
    controllerBody.append(createControllerRow(controllerId, controller, isNew));
    controllerTable.append(controllerBody);
    const deviceArea = document.createElement("div");
    deviceArea.className = "subsection-indent";
    const heading = document.createElement("h4");
    heading.textContent = "Devices";
    const deviceTable = document.createElement("table");
    deviceTable.innerHTML = "<thead><tr><th>ID</th><th>Label</th><th>Pin</th><th>Output type</th><th>Editor</th></tr></thead>";
    const deviceBody = document.createElement("tbody");
    for (const [deviceId, device] of devices) deviceBody.append(createDeviceRow(deviceId, device, controllerId));
    deviceBody.append(createDeviceRow("", {}, controllerId, true));
    deviceTable.append(deviceBody);
    deviceArea.append(heading, deviceTable);
    block.append(controllerTable, deviceArea);
    return block;
  }

  function cameraModelLabel(item) {
    const model = String(item?.model || "");
    const sensor = String(item?.sensor || model.split("_", 1)[0]).toLowerCase();
    const wide = String(item?.lens || "").toLowerCase().includes("wide") || model.toLowerCase().includes("wide");
    const labels = {imx708: wide ? "Camera Module 3 Wide" : "Camera Module 3", imx219: "Camera Module 2", ov5647: "Camera Module 1", imx477: "HQ Camera", imx296: "Global Shutter Camera"};
    return labels[sensor] || model || "-";
  }

  function cameraOptions(selected) {
    const items = [["", "Unassigned"]];
    const seen = new Set();
    for (const camera of detectedCameras) {
      const key = normalizeCameraKey(camera?.key);
      if (!key) continue;
      seen.add(key);
      const lens = String(camera?.lens || "").trim();
      items.push([key, `${key} | ${cameraModelLabel(camera)}${lens ? ` | ${lens}` : ""}`]);
    }
    if (selected && !seen.has(selected)) items.push([selected, `${selected} (not detected)`]);
    return items;
  }

  function createCameraRow(cameraId, camera, detectedKey, isNew = false) {
    const row = document.createElement("tr");
    row.className = `camera-row${isNew ? " new-row" : ""}`;
    row.dataset.cameraKey = isNew ? "" : cameraId;
    row.append(
      cell(input("camera-id", cameraId, {placeholder: "rpicam_cam0"})),
      cell(input("camera-label", camera?.label || "", {placeholder: "Tent camera"})),
      cell(selectWithOptions("camera-detected-key", cameraOptions(detectedKey), detectedKey)),
      cell(input("camera-capture-dir", camera?.capture_dir || "", {placeholder: "data/grow/grows/<grow-id>/captures"})),
      cell(input("camera-capture-every-seconds", camera?.capture_every_seconds ?? (isNew ? 0 : ""), {type: "number", min: 0})),
      cell(selectWithOptions("camera-autofocus-mode", [["auto", "auto"], ["continuous", "continuous"], ["manual", "manual"], ["off", "off"]], camera?.autofocus_mode || "auto")),
      cell(input("camera-autofocus-delay-ms", camera?.autofocus_delay_ms, {type: "number", min: 0})),
    );
    return row;
  }

  function cameraMatches(configured) {
    const detectedByKey = new Map(detectedCameras.map((camera) => [normalizeCameraKey(camera?.key), camera]).filter(([key]) => key));
    const unmatched = [...detectedByKey.keys()];
    const matches = {};
    for (const [cameraId, camera] of Object.entries(configured)) {
      const saved = normalizeCameraKey(camera?.detected_key);
      const match = saved && detectedByKey.has(saved) ? saved : (detectedByKey.has(cameraId) ? cameraId : "");
      if (!match) continue;
      matches[cameraId] = match;
      const index = unmatched.indexOf(match);
      if (index >= 0) unmatched.splice(index, 1);
    }
    for (const cameraId of Object.keys(configured)) if (!matches[cameraId] && unmatched.length) matches[cameraId] = unmatched.shift();
    return {matches, unmatched};
  }

  function renderSettings(config, system) {
    schedulerBlocks.replaceChildren();
    cameraRows.replaceChildren();
    const controllers = config?.controllers && typeof config.controllers === "object" ? config.controllers : {};
    const schedulerControllers = Object.fromEntries(Object.entries(controllers).filter(([, controller]) => String(controller?.type || "pico_scheduler") === "pico_scheduler"));
    hiddenControllers = {};
    for (const [controllerId, controller] of Object.entries(schedulerControllers)) {
      const devices = Object.entries(semanticDevices(controller)).sort((left, right) => {
        const leftOrder = Number.isInteger(left[1]?.display_order) ? left[1].display_order : Number.MAX_SAFE_INTEGER;
        const rightOrder = Number.isInteger(right[1]?.display_order) ? right[1].display_order : Number.MAX_SAFE_INTEGER;
        return leftOrder - rightOrder;
      });
      if (devices.length) schedulerBlocks.append(createSchedulerBlock(controllerId, controller, devices));
      else hiddenControllers[controllerId] = structuredClone(controller);
    }
    schedulerBlocks.append(createSchedulerBlock("", {}, [], true));

    const configuredCameras = config?.cameras && typeof config.cameras === "object" ? config.cameras : {};
    const {matches, unmatched} = cameraMatches(configuredCameras);
    for (const [cameraId, camera] of Object.entries(configuredCameras)) cameraRows.append(createCameraRow(cameraId, camera || {}, matches[cameraId] || ""));
    for (const key of unmatched) cameraRows.append(createCameraRow(key, {}, key));
    cameraRows.append(createCameraRow("", {}, "", true));

    const hostname = String(system?.host?.hostname || "");
    document.getElementById("settings-heading").textContent = hostname ? `${hostname} Settings` : "Settings";
  }

  function hydrateControllerRowFromHidden(row) {
    const key = row.querySelector(".controller-id").value.trim();
    const hiddenController = hiddenControllers[key];
    if (!key || !hiddenController || row.dataset.controllerKey) return;
    const payload = controllerPayload(hiddenController);
    const settings = controllerSettings(hiddenController);
    const labelInput = row.querySelector(".controller-label");
    labelInput.value = settings.label || "";
    labelInput.defaultValue = settings.label || "";
    const picoSelect = row.querySelector(".controller-pico-serial");
    picoSelect.value = payload.pico_serial || "";
    picoSelect.dataset.defaultValue = payload.pico_serial || "";
  }

  function collectControllers() {
    const result = structuredClone(hiddenControllers);
    for (const row of document.querySelectorAll(".controller-row")) {
      const key = row.querySelector(".controller-id").value.trim();
      if (!key) continue;
      const oldKey = row.dataset.controllerKey || "";
      const existing = hiddenControllers[key] ? structuredClone(hiddenControllers[key]) : (oldKey && hiddenControllers[oldKey] ? structuredClone(hiddenControllers[oldKey]) : {});
      const hiddenReuse = !oldKey && Object.keys(existing).length > 0;
      const controller = hiddenReuse ? existing : {type: "pico_scheduler", payload: {}, settings: {}};
      if (oldKey && oldKey !== key) delete result[oldKey];
      controller.type = row.querySelector(".controller-type").value;
      controller.payload ||= {};
      controller.settings ||= {};
      const label = row.querySelector(".controller-label").value.trim();
      const serial = row.querySelector(".controller-pico-serial").value;
      if (!hiddenReuse || label !== row.querySelector(".controller-label").defaultValue) controller.settings.label = label;
      if (!hiddenReuse || serial !== row.querySelector(".controller-pico-serial").dataset.defaultValue) controller.payload.pico_serial = serial;
      controller.payload = cleanObject(controller.payload);
      controller.settings = cleanObject(controller.settings);
      result[key] = controller;
    }
    return result;
  }

  function collectControllerDevices() {
    const result = {};
    for (const row of document.querySelectorAll(".device-row")) {
      const key = row.querySelector(".device-id").value.trim();
      if (!key) continue;
      const pinValue = row.querySelector(".device-pin").value;
      if (pinValue === "") throw new Error(`Pin required for device ${key}.`);
      const controller = row.closest(".pico-scheduler-block")?.querySelector(".controller-id")?.value.trim() || row.dataset.deviceController || "";
      if (!controller) throw new Error(`Controller required for device ${key}.`);
      result[controller] ||= {settings: {}};
      const mode = row.querySelector(".device-editor").value;
      const existingEditor = JSON.parse(row.dataset.deviceEditorJson || "{}");
      let editor;
      if (mode === "clock_window") editor = existingEditor.kind === "daily_window" ? existingEditor : {kind: "daily_window", on_time: "06:00", off_time: "18:00"};
      else if (mode === "cycle") editor = existingEditor.kind === "cycle" ? existingEditor : {kind: "cycle"};
      else editor = existingEditor.kind ? existingEditor : {kind: "cycle"};
      result[controller].settings[key] = cleanObject({
        pin: Number(pinValue),
        label: row.querySelector(".device-label").value.trim(),
        display_order: Object.keys(result[controller].settings).length,
        visibility: mode === "hidden" ? "hidden" : "visible",
        programming: mode === "disabled" ? "disabled" : "enabled",
        editor,
        output_type: row.querySelector(".device-type").value,
      });
    }
    return result;
  }

  function normalizeCaptureDirPath(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (!raw.startsWith("/")) return raw.replace(/^\.\//, "");
    const root = String(repoRootPath || "").replace(/\/$/, "");
    if (root && raw.startsWith(`${root}/`)) return raw.slice(root.length + 1);
    if (raw === root) return "";
    throw new Error(`Capture dir must be inside repo root ${root || "reported by the server"} or be relative.`);
  }

  function collectCameras() {
    const result = {};
    for (const row of document.querySelectorAll(".camera-row")) {
      const key = row.querySelector(".camera-id").value.trim();
      if (!key) continue;
      const every = row.querySelector(".camera-capture-every-seconds").value.trim();
      const delay = row.querySelector(".camera-autofocus-delay-ms").value.trim();
      result[key] = cleanObject({
        label: row.querySelector(".camera-label").value.trim(),
        detected_key: row.querySelector(".camera-detected-key").value,
        capture_dir: normalizeCaptureDirPath(row.querySelector(".camera-capture-dir").value),
        capture_every_seconds: every === "" ? null : Number(every),
        autofocus_mode: row.querySelector(".camera-autofocus-mode").value,
        autofocus_delay_ms: delay === "" ? null : Number(delay),
      });
    }
    return result;
  }

  function controllerRenames() {
    const result = {};
    for (const row of document.querySelectorAll(".controller-row")) {
      const oldKey = row.dataset.controllerKey || "";
      const newKey = row.querySelector(".controller-id").value.trim();
      if (oldKey && newKey && oldKey !== newKey) result[oldKey] = newKey;
    }
    return result;
  }

  function collectConfigWithControllerRenames() {
    const controllers = collectControllers();
    const devicesByController = collectControllerDevices();
    for (const [oldKey, newKey] of Object.entries(controllerRenames())) {
      if (devicesByController[oldKey]) {
        devicesByController[newKey] = devicesByController[oldKey];
        delete devicesByController[oldKey];
      }
    }
    for (const [controllerId, devices] of Object.entries(devicesByController)) {
      if (!controllers[controllerId]) throw new Error(`Unknown controller for devices: ${controllerId}.`);
      controllers[controllerId].settings ||= {};
      controllers[controllerId].payload ||= {};
      controllers[controllerId].settings.devices = devices.settings;
      delete controllers[controllerId].payload.devices;
    }
    return {controllers, cameras: collectCameras()};
  }

  async function saveSection(statusId, url, payload) {
    const status = document.getElementById(statusId);
    status.textContent = "Saving...";
    try {
      const response = await fetch(url, {method: "PUT", headers: {"content-type": "application/json"}, body: JSON.stringify(payload)});
      if (!response.ok) {
        status.textContent = `${response.status} ${await response.text()}`;
        return;
      }
      status.textContent = "Saved.";
      window.location.reload();
    } catch (error) {
      status.textContent = error.message || String(error);
    }
  }

  function runSave(statusId, callback) {
    try {
      callback();
    } catch (error) {
      document.getElementById(statusId).textContent = error.message || String(error);
    }
  }

  async function bootstrapSettings() {
    try {
      const [{system}, configResponse] = await Promise.all([
        PlampWeb.bootstrapShell({activePath: "/settings", headingSuffix: "Settings"}),
        fetch("/api/config"),
      ]);
      const configPayload = await PlampWeb.responseJson(configResponse, "config");
      detectedPicos = Array.isArray(system?.detected?.picos) ? system.detected.picos : [];
      detectedCameras = Array.isArray(system?.detected?.cameras) ? system.detected.cameras.map((camera) => ({...camera, key: normalizeCameraKey(camera?.key)})) : [];
      repoRootPath = String(system?.paths?.repo_root || system?.software?.path || "");
      renderSettings(configPayload?.config || {}, system || {});
      setSaveDisabled(false);
      showLoadStatus("Ready.");
      for (const id of ["controllers-status", "devices-status", "cameras-status"]) document.getElementById(id).textContent = "Ready.";
    } catch (error) {
      setSaveDisabled(true);
      showLoadError(`Settings setup failed: ${error.message || String(error)}`);
    }
  }

  document.getElementById("save-controllers").addEventListener("click", () => runSave("controllers-status", () => saveSection("controllers-status", "/api/config", collectConfigWithControllerRenames())));
  document.getElementById("save-devices").addEventListener("click", () => runSave("devices-status", () => saveSection("devices-status", "/api/config", collectConfigWithControllerRenames())));
  document.getElementById("save-cameras").addEventListener("click", () => runSave("cameras-status", () => saveSection("cameras-status", "/api/config/cameras", collectCameras())));
  bootstrapSettings();
})();
