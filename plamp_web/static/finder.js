(function () {
  const buttons = {
    gallery: document.getElementById("camera-show-gallery"),
    finder: document.getElementById("camera-show-finder"),
    ribbon: document.getElementById("camera-show-ribbon"),
  };
  const panels = {
    gallery: document.getElementById("camera-gallery"),
    finder: document.getElementById("camera-finder"),
    ribbon: document.getElementById("camera-ribbon"),
  };
  const lines = document.getElementById("camera-finder-lines");
  const status = document.getElementById("camera-finder-status");
  const detail = document.getElementById("camera-finder-detail");
  const nowButton = document.getElementById("camera-finder-now");
  if (!buttons.gallery || !buttons.finder || !panels.finder || !lines || !status) return;

  let finderAt = null;
  let loaded = false;
  let loading = false;
  let pending = false;
  let following = false;
  let followTimer = null;

  buttons.gallery.addEventListener("click", () => show("gallery"));
  buttons.finder.addEventListener("click", () => show("finder"));
  if (buttons.ribbon) buttons.ribbon.addEventListener("click", () => show("ribbon"));
  if (nowButton) nowButton.addEventListener("click", toggleNow);

  function toggleNow() {
    following = !following;
    if (nowButton) nowButton.setAttribute("aria-pressed", following ? "true" : "false");
    if (followTimer) window.clearInterval(followTimer);
    followTimer = null;
    if (!following) return;
    finderAt = null;
    refresh();
    followTimer = window.setInterval(() => {
      finderAt = null;
      refresh();
    }, 60000);
  }

  function leaveNow() {
    if (!following) return;
    following = false;
    if (nowButton) nowButton.setAttribute("aria-pressed", "false");
    if (followTimer) window.clearInterval(followTimer);
    followTimer = null;
  }

  function show(which) {
    for (const name of Object.keys(panels)) {
      if (!panels[name]) continue;
      panels[name].hidden = name !== which;
      if (buttons[name]) buttons[name].setAttribute("aria-pressed", name === which ? "true" : "false");
    }
    if (which === "finder" && !loaded) {
      loaded = true;
      refresh();
    }
    if (which === "ribbon") window.dispatchEvent(new Event("plamp-ribbon-show"));
  }

  function refresh() {
    pending = true;
    if (!loading) pump();
  }

  function pump() {
    if (!pending) return;
    pending = false;
    loading = true;
    const url = finderAt && !following ? `/api/camera/finder?at=${encodeURIComponent(finderAt)}` : "/api/camera/finder";
    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("finder unavailable");
        return response.json();
      })
      .then((data) => render(data))
      .catch(() => {
        status.textContent = "Finder unavailable.";
      })
      .finally(() => {
        loading = false;
        if (pending) pump();
      });
  }

  function render(data) {
    if (!following) finderAt = data.at;
    if (detail) detail.textContent = data.detail || "";
    status.textContent = data.empty ? "No pictures yet." : "";
    lines.replaceChildren();
    for (const line of data.lines || []) lines.appendChild(lineView(line));
  }

  function lineView(line) {
    const box = document.createElement("div");
    box.className = `finder-line ${line.scale}`;
    const frames = document.createElement("div");
    frames.className = "finder-frames";
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = String(Math.max(0, (line.frames || []).length - 1));
    slider.value = String(line.index || 0);
    slider.disabled = !(line.frames || []).length;
    slider.addEventListener("input", () => {
      leaveNow();
      paint(frames, line, Number(slider.value));
    });
    slider.addEventListener("change", () => {
      leaveNow();
      const frame = (line.frames || [])[Number(slider.value)];
      if (!frame) return;
      finderAt = frame.at;
      refresh();
    });
    const label = document.createElement("span");
    const range = document.createElement("div");
    range.className = "finder-range";
    range.append(slider);
    const controls = document.createElement("div");
    controls.className = "finder-slider";
    controls.append(label, range);
    box.append(frames, controls);
    requestAnimationFrame(() => paint(frames, line, Number(slider.value)));
    return box;
  }

  function frameLabel(line, frame) {
    if (!frame) return line.label || "";
    return frame.slider_label || frame.label || line.label || "";
  }

  function paint(frames, line, index) {
    const items = line.frames || [];
    const label = frames.parentElement.querySelector(".finder-slider span");
    if (label) label.textContent = frameLabel(line, items[index]);
    if (line.scale === "hours" && detail && items[index] && items[index].detail) detail.textContent = items[index].detail;
    const height = line.scale === "hours" ? 168 : line.scale === "days" ? 104 : 56;
    const width = frames.clientWidth || 640;
    const frameWidth = height * 16 / 9;
    let count = Math.max(1, Math.floor((width + 6) / (frameWidth + 6)));
    let start = index - Math.floor(count / 2);
    start = Math.max(0, Math.min(start, Math.max(0, items.length - count)));
    frames.replaceChildren();
    items.slice(start, start + count).forEach((frame, offset) => {
      const absolute = start + offset;
      const el = document.createElement("div");
      el.className = "finder-frame" + (absolute === index ? " selected" : "");
      if (frame.thumb_url) {
        const img = document.createElement("img");
        img.src = frame.thumb_url;
        img.alt = frameLabel(line, frame) || line.scale;
        el.appendChild(img);
      }
      el.addEventListener("click", () => {
        const slider = frames.parentElement.querySelector("input[type=range]");
        slider.value = String(absolute);
        slider.dispatchEvent(new Event("change"));
      });
      frames.appendChild(el);
    });
  }
})();
