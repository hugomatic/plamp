(function () {
  const buttons = {
    gallery: document.getElementById("camera-show-gallery"),
    finder: document.getElementById("camera-show-finder"),
  };
  const panels = {
    gallery: document.getElementById("camera-gallery"),
    finder: document.getElementById("camera-finder"),
  };
  const lines = document.getElementById("camera-finder-lines");
  const status = document.getElementById("camera-finder-status");
  const detail = document.getElementById("camera-finder-detail");
  const nowButton = document.getElementById("camera-finder-now");
  const fullButton = document.getElementById("camera-finder-full");
  if (!buttons.gallery || !buttons.finder || !panels.finder || !lines || !status) return;

  let finderAt = null;
  let loaded = false;
  let loading = false;
  let pending = false;
  let following = Boolean(nowButton && nowButton.checked);
  let followTimer = null;
  let fullCapture = null;
  const ready = fetch("/api/camera/finder")
    .then((response) => {
      if (!response.ok) throw new Error("finder unavailable");
      return response.json();
    })
    .catch(() => null);

  buttons.gallery.addEventListener("click", () => show("gallery"));
  buttons.finder.addEventListener("click", () => show("finder"));
  if (nowButton) nowButton.addEventListener("change", applyLatest);
  if (fullButton) fullButton.addEventListener("click", openFull);
  window.addEventListener("plamp-capture-saved", () => {
    if (!following || !loaded) return;
    finderAt = null;
    refresh();
  });

  function openFull() {
    if (!fullCapture) return;
    window.open(`/api/camera/captures/${encodeURIComponent(fullCapture)}/image`, "_blank", "noopener");
  }

  function setFull(frame) {
    fullCapture = frame && frame.capture_id ? frame.capture_id : null;
    if (fullButton) fullButton.disabled = !fullCapture;
  }

  function applyLatest() {
    following = Boolean(nowButton && nowButton.checked);
    if (followTimer) window.clearInterval(followTimer);
    followTimer = null;
    if (!following) return;
    finderAt = null;
    refresh();
    followTimer = window.setInterval(() => {
      finderAt = null;
      refresh();
    }, 15000);
  }

  function leaveNow() {
    if (!following && !(nowButton && nowButton.checked)) return;
    following = false;
    if (nowButton) nowButton.checked = false;
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
      status.textContent = "Loading pictures…";
      if (following) {
        followTimer = window.setInterval(() => {
          finderAt = null;
          refresh();
        }, 15000);
      }
      ready.then((data) => {
        if (panels.finder.hidden) return;
        if (data && (following || !finderAt)) render(data);
        else refresh();
      });
    }
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
      if (line.scale === "hours") return;
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

  function lineLayout(scale, frames) {
    const preferred = scale === "hours" ? 168 : scale === "days" ? 104 : 56;
    const gap = 6;
    const style = getComputedStyle(frames);
    const width = Math.max(0, frames.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)) || 640;
    const fit = (height) => Math.max(1, Math.floor((width + gap) / (height * 16 / 9 + gap)));
    if (scale === "hours" && fit(preferred) < 2) {
      return { height: width * 0.72 * 9 / 16, count: 3, peek: true };
    }
    if (scale !== "hours" && fit(preferred) < 3) {
      return { height: ((width - 2 * gap) / 3) * 9 / 16, count: 3, peek: false };
    }
    return { height: preferred, count: fit(preferred), peek: false };
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
    if (line.scale === "hours") setFull(items[index]);
    const layout = lineLayout(line.scale, frames);
    frames.classList.toggle("peek", layout.peek);
    let start = index - Math.floor(layout.count / 2);
    start = Math.max(0, Math.min(start, Math.max(0, items.length - layout.count)));
    frames.replaceChildren();
    items.slice(start, start + layout.count).forEach((frame, offset) => {
      const absolute = start + offset;
      const el = document.createElement("div");
      el.className = "finder-frame" + (absolute === index ? " selected" : "");
      el.style.height = `${layout.height}px`;
      if (frame.thumb_url) {
        const img = document.createElement("img");
        img.src = frame.thumb_url;
        img.alt = frameLabel(line, frame) || line.scale;
        el.appendChild(img);
      }
      el.addEventListener("click", () => {
        if (line.scale === "hours" && absolute === index && frame.capture_id) {
          openFull();
          return;
        }
        const slider = frames.parentElement.querySelector("input[type=range]");
        slider.value = String(absolute);
        slider.dispatchEvent(new Event("change"));
      });
      frames.appendChild(el);
    });
  }
  show("finder");
})();
