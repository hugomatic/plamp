(() => {
  const GITHUB_REPO_URL = "https://github.com/hugomatic/plamp";
  let systemPromise;
  let controllersPromise;

  async function responseJson(response, label) {
    if (!response.ok) throw new Error(`${label}: ${response.status} ${response.statusText}`);
    return response.json();
  }

  function loadSystem() {
    systemPromise ||= fetch("/api/system").then((response) => responseJson(response, "system"));
    return systemPromise;
  }

  function loadControllers() {
    controllersPromise ||= fetch("/api/controllers").then((response) => responseJson(response, "controllers"));
    return controllersPromise;
  }

  function appendNavItem(nav, item) {
    if (nav.childNodes.length) nav.append(" | ");
    nav.append(item);
  }

  function navLink(href, label, activePath) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    if (href === activePath) link.setAttribute("aria-current", "page");
    return link;
  }

  async function bootstrapShell({activePath = location.pathname, headingSuffix = "Plamp"} = {}) {
    const nav = document.querySelector("[data-plamp-nav]");
    if (!nav) throw new Error("page is missing its Plamp navigation element");

    const [systemResult, controllersResult] = await Promise.allSettled([loadSystem(), loadControllers()]);
    const system = systemResult.status === "fulfilled" ? systemResult.value : {};
    const controllerMap = controllersResult.status === "fulfilled"
      && controllersResult.value.controllers
      && typeof controllersResult.value.controllers === "object"
      ? controllersResult.value.controllers
      : {};
    const controllerIds = Object.keys(controllerMap);

    nav.replaceChildren();
    appendNavItem(nav, navLink("/", "Plamp", activePath));
    for (const controllerId of controllerIds) {
      appendNavItem(nav, navLink(`/controllers/${encodeURIComponent(controllerId)}`, controllerId, activePath));
    }
    appendNavItem(nav, navLink("/settings", "Settings", activePath));
    appendNavItem(nav, navLink("/system", "System", activePath));
    appendNavItem(nav, navLink("/api/test", "API test", activePath));

    const revision = String(system?.software?.git_short_commit || system?.software?.git_commit || "unknown");
    if (revision === "unknown") appendNavItem(nav, document.createTextNode("[rev unknown]"));
    else appendNavItem(nav, navLink(`${GITHUB_REPO_URL}/commit/${encodeURIComponent(revision)}`, `[rev ${revision}]`, activePath));

    const hostname = String(system?.host?.hostname || "");
    document.title = hostname ? `${hostname} ${headingSuffix}` : headingSuffix;
    if (systemResult.status === "rejected") nav.dataset.systemError = systemResult.reason?.message || String(systemResult.reason);
    if (controllersResult.status === "rejected") nav.dataset.controllersError = controllersResult.reason?.message || String(controllersResult.reason);
    return {system, controllers: controllerIds};
  }

  window.PlampWeb = {bootstrapShell, loadControllers, loadSystem, responseJson};
})();
