(() => {
  const loadStatus = document.getElementById("system-load-status");
  const actionStatus = document.getElementById("system-action-status");
  const logsNode = document.getElementById("system-logs");
  const actionButtons = ["system-restart", "system-reinstall", "system-upgrade"].map((id) => document.getElementById(id));
  const controls = [...actionButtons, document.getElementById("system-load-logs")];

  function valueText(value, fallback = "-") {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function setControlsDisabled(disabled) {
    for (const control of controls) control.disabled = disabled;
  }

  function replaceMessage(body, columns, message) {
    body.replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns;
    cell.textContent = message;
    row.append(cell);
    body.append(row);
  }

  function appendCells(body, values, firstHeader = false) {
    const row = document.createElement("tr");
    values.forEach((value, index) => {
      const cell = document.createElement(firstHeader && index === 0 ? "th" : "td");
      if (firstHeader && index === 0) cell.scope = "row";
      cell.textContent = valueText(value);
      row.append(cell);
    });
    body.append(row);
  }

  function renderFacts(bodyId, facts) {
    const body = document.getElementById(bodyId);
    body.replaceChildren();
    for (const [label, value] of facts) appendCells(body, [label, value], true);
  }

  function relativeTimeLabel(value) {
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) return "";
    const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (seconds < 60) return "just now";
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
    }
    if (seconds < 86400) {
      const hours = Math.floor(seconds / 3600);
      return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    }
    const days = Math.floor(seconds / 86400);
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  function gitDirtyText(software) {
    if (software.git_dirty === null || software.git_dirty === undefined) return "unknown";
    if (!software.git_dirty) return "no";
    const files = Array.isArray(software.git_dirty_files) ? software.git_dirty_files.filter(Boolean) : [];
    const preview = files.slice(0, 2).join(", ");
    const suffix = files.length > 2 ? `${preview ? ", " : ""}...` : "";
    return preview || suffix ? `yes: ${preview}${suffix}` : "yes";
  }

  function cameraName(item) {
    if (item.connector) return String(item.connector);
    if (item.index !== null && item.index !== undefined) return `cam${item.index}`;
    return valueText(item.key).replace(/[^A-Za-z0-9_-]+/g, "_");
  }

  function cameraModel(item) {
    const rawModel = String(item.model || "");
    const sensor = String(item.sensor || rawModel.split("_", 1)[0]).toLowerCase();
    const wide = String(item.lens || "").toLowerCase().includes("wide") || rawModel.toLowerCase().includes("wide");
    const models = {
      imx708: wide ? "Camera Module 3 Wide" : "Camera Module 3",
      imx219: "Camera Module 2",
      ov5647: "Camera Module 1",
      imx477: "HQ Camera",
      imx296: "Global Shutter Camera",
    };
    return models[sensor] || rawModel || "-";
  }

  function renderHardware(system) {
    const detected = system.detected && typeof system.detected === "object" ? system.detected : {};
    const picos = Array.isArray(detected.picos) ? detected.picos : [];
    const picoBody = document.getElementById("system-picos");
    picoBody.replaceChildren();
    if (!picos.length) replaceMessage(picoBody, 4, "No peripherals found.");
    for (const item of picos) appendCells(picoBody, [item.port, item.usb_device, item.serial, `${valueText(item.vendor_id)}:${valueText(item.product_id)}`]);

    const cameras = Array.isArray(detected.cameras) ? detected.cameras : [];
    const cameraBody = document.getElementById("system-cameras");
    cameraBody.replaceChildren();
    if (!cameras.length) replaceMessage(cameraBody, 5, "No Raspberry Pi cameras found.");
    for (const item of cameras) appendCells(cameraBody, [cameraName(item), cameraModel(item), item.sensor, item.lens, item.path]);
  }

  function renderMonitors(monitors) {
    const body = document.getElementById("system-monitors");
    body.replaceChildren();
    const entries = monitors && typeof monitors === "object" ? Object.entries(monitors).sort(([left], [right]) => left.localeCompare(right)) : [];
    if (!entries.length) replaceMessage(body, 7, "No controller workers found.");
    for (const [role, worker] of entries) {
      appendCells(body, [role, worker.serial, worker.state, worker.connected ? "yes" : "no", worker.port, worker.last_seen, worker.last_error]);
    }
  }

  function renderSystem(system) {
    const host = system.host && typeof system.host === "object" ? system.host : {};
    const hostTime = system.host_time && typeof system.host_time === "object" ? system.host_time : {};
    const software = system.software && typeof system.software === "object" ? system.software : {};
    const tools = system.tools && typeof system.tools === "object" ? system.tools : {};
    const paths = system.paths && typeof system.paths === "object" ? system.paths : {};
    const storage = system.storage && typeof system.storage === "object" ? system.storage : {};
    const log = system.log && typeof system.log === "object" ? system.log : {};
    const worker = system.camera_worker && typeof system.camera_worker === "object" ? system.camera_worker : {};
    const hostname = String(host.hostname || "");
    document.getElementById("system-heading").textContent = `${hostname || "Plamp"} System`;
    document.querySelector("#host-clock span").textContent = valueText(hostTime.display);

    const osDisplay = `${valueText(software.os_name, "unknown")} ${valueText(software.os_version, "unknown")}; arch ${valueText(software.os_arch, "unknown")}`;
    const userDisplay = `${valueText(software.user_name, "unknown")}; sudoer ${software.user_is_sudoer ? "yes" : "no"}; serial ${software.user_has_serial_access ? "yes" : "no"}; video ${software.user_has_video_access ? "yes" : "no"}`;
    renderFacts("system-info", [
      ["Hostname", hostname], ["Host time", hostTime.display], ["Operating system", osDisplay], ["User name", userDisplay], ["Computer hardware model", valueText(host.hardware_model, "unknown")],
    ]);

    const commitTime = valueText(software.git_commit_timestamp, "unknown");
    const relativeCommitTime = relativeTimeLabel(software.git_commit_timestamp);
    const mpremotePath = valueText(software.mpremote_path, "not found");
    const mpremoteVersion = String(software.mpremote_version || "").replace(/^mpremote\s+/, "").trim();
    renderFacts("system-software", [
      ["Git commit", software.git_short_commit || software.git_commit || "unknown"],
      ["Git branch", valueText(software.git_branch, "unknown")],
      ["Git commit time", relativeCommitTime ? `${commitTime} (${relativeCommitTime})` : commitTime],
      ["Git dirty", gitDirtyText(software)],
      ["mpremote", mpremoteVersion ? `${mpremotePath} version ${mpremoteVersion}` : mpremotePath],
      ["pyserial", ["-", "unknown"].includes(valueText(tools.pyserial)) ? valueText(tools.pyserial) : `version ${tools.pyserial}`],
    ]);

    renderFacts("system-storage", [
      ["Root folder", `${paths.repo_root || software.path || "-"} (PLAMP_ROOT)`],
      ["Data dir", `${paths.data_dir || "-"} (PLAMP_DATA_DIR)`],
      ["Free disk space", storage.free], ["Used disk space", storage.used], ["Total disk space", storage.total], ["Log file", log.path],
    ]);
    renderFacts("system-camera-worker", [
      ["State", worker.state], ["Available", "available" in worker ? worker.available : "-"], ["Queue depth", worker.queue_depth ?? 0],
      ["Last capture", worker.last_capture_at], ["Last error", worker.last_error], ["Scheduled cameras", Array.isArray(worker.scheduled_cameras) && worker.scheduled_cameras.length ? worker.scheduled_cameras.join(", ") : "-"],
    ]);
    renderHardware(system);
    renderMonitors(system.monitors);
  }

  async function loadLogs() {
    logsNode.textContent = "Loading...";
    try {
      const response = await fetch("/api/logs?lines=200");
      const data = await PlampWeb.responseJson(response, "logs");
      logsNode.textContent = data.content || "No log entries.";
    } catch (error) {
      logsNode.textContent = `Log load failed: ${error.message || String(error)}`;
    }
  }

  async function runAction(path, label) {
    for (const button of actionButtons) button.disabled = true;
    actionStatus.textContent = `${label}...`;
    actionStatus.classList.remove("error");
    try {
      const response = await fetch(path, {method: "POST"});
      const text = await response.text();
      let data = {};
      try { data = JSON.parse(text); } catch (error) { data = {}; }
      if (!response.ok) {
        actionStatus.textContent = `${label} failed: ${data.detail || `${response.status} ${response.statusText}`}`;
        actionStatus.classList.add("error");
        return;
      }
      actionStatus.textContent = data.message || "Request accepted.";
    } catch (error) {
      actionStatus.textContent = `${label} result unconfirmed: ${error.message || String(error)}`;
      actionStatus.classList.add("error");
    } finally {
      for (const button of actionButtons) button.disabled = false;
    }
  }

  document.getElementById("system-restart").addEventListener("click", () => runAction("/api/system/restart", "Restart"));
  document.getElementById("system-reinstall").addEventListener("click", () => runAction("/api/system/reinstall", "Reinstall"));
  document.getElementById("system-upgrade").addEventListener("click", () => runAction("/api/system/upgrade", "Upgrade"));
  document.getElementById("system-load-logs").addEventListener("click", loadLogs);

  async function bootstrapSystem() {
    try {
      const [, system] = await Promise.all([
        PlampWeb.bootstrapShell({activePath: "/system", headingSuffix: "System"}),
        PlampWeb.loadSystem(),
      ]);
      renderSystem(system);
      setControlsDisabled(false);
      actionStatus.textContent = "Ready.";
      loadStatus.textContent = "System information loaded.";
    } catch (error) {
      setControlsDisabled(true);
      loadStatus.textContent = `System setup failed: ${error.message || String(error)}`;
      loadStatus.classList.add("error");
      actionStatus.textContent = "Unavailable.";
    }
  }

  bootstrapSystem();
})();
