(function () {
  const galleryButton = document.getElementById("camera-show-gallery");
  const ribbonButton = document.getElementById("camera-show-ribbon");
  const gallery = document.getElementById("camera-gallery");
  const ribbon = document.getElementById("camera-ribbon");
  const rows = document.getElementById("camera-ribbon-rows");
  const status = document.getElementById("camera-ribbon-status");
  if (!galleryButton || !ribbonButton || !gallery || !ribbon || !rows || !status) return;

  let ribbonAt = null;
  let loaded = false;
  let loading = false;
  let pending = false;

  galleryButton.addEventListener("click", () => show("gallery"));
  ribbonButton.addEventListener("click", () => show("ribbon"));

  function show(which) {
    const ribbonOn = which === "ribbon";
    gallery.hidden = ribbonOn;
    ribbon.hidden = !ribbonOn;
    galleryButton.setAttribute("aria-pressed", ribbonOn ? "false" : "true");
    ribbonButton.setAttribute("aria-pressed", ribbonOn ? "true" : "false");
    if (ribbonOn && !loaded) {
      loaded = true;
      refresh();
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
    const url = ribbonAt ? `/api/camera/ribbon?at=${encodeURIComponent(ribbonAt)}` : "/api/camera/ribbon";
    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("ribbon unavailable");
        return response.json();
      })
      .then((data) => render(data))
      .catch(() => {
        status.textContent = "Ribbon unavailable.";
      })
      .finally(() => {
        loading = false;
        if (pending) pump();
      });
  }

  function render(data) {
    ribbonAt = data.at;
    status.textContent = data.empty ? "No pictures yet." : "";
    rows.replaceChildren();
    for (const row of data.rows || []) {
      const line = document.createElement("div");
      line.className = "ribbon-row";
      const label = document.createElement("span");
      label.textContent = row.label || "";
      const frames = document.createElement("div");
      frames.className = "ribbon-frames";
      for (const frame of row.frames || []) {
        frames.appendChild(frameView(row, frame));
      }
      attachDrag(frames, row.scale);
      line.append(label, frames);
      rows.appendChild(line);
    }
  }

  function frameView(row, frame) {
    const el = document.createElement("div");
    el.className = `ribbon-frame ${frame.role || "outer"}`;
    if (frame.thumb_url) {
      const img = document.createElement("img");
      img.src = frame.thumb_url;
      img.alt = frame.label || row.label || "Capture";
      el.appendChild(img);
    }
    if (row.scale === "hours" && frame.role === "center") {
      const picks = document.createElement("div");
      picks.className = "ribbon-picks";
      picks.append(pickButton("day", "this day", frame), pickButton("week", "this week", frame));
      el.appendChild(picks);
    }
    if (frame.label) {
      const caption = document.createElement("div");
      caption.className = "ribbon-caption";
      caption.textContent = frame.label;
      el.appendChild(caption);
    }
    return el;
  }

  function pickButton(scale, text, frame) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.disabled = !frame.capture_id;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      if (!frame.capture_id) return;
      fetch("/api/camera/ribbon/picks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scale, at: frame.at, capture_id: frame.capture_id }),
      }).then((response) => {
        if (response.ok) refresh();
      });
    });
    return button;
  }

  function attachDrag(frames, scale) {
    let origin = 0;
    const stepPx = 36;
    frames.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      origin = event.clientX;
      frames.setPointerCapture(event.pointerId);
    });
    frames.addEventListener("pointermove", (event) => {
      if (!frames.hasPointerCapture(event.pointerId)) return;
      const steps = Math.trunc((event.clientX - origin) / stepPx);
      if (steps === 0) return;
      origin += steps * stepPx;
      move(scale, -steps);
    });
  }

  function move(scale, delta) {
    if (!ribbonAt) return;
    const unit = scale === "weeks" ? 7 * 86400000 : scale === "days" ? 86400000 : 3600000;
    ribbonAt = new Date(Date.parse(ribbonAt) + delta * unit).toISOString();
    refresh();
  }
})();
