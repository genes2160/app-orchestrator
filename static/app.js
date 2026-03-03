const $apps = document.getElementById("apps");
const $logs = document.getElementById("logs");
const $logsTitle = document.getElementById("logs-title");
const $btnLogsRefresh = document.getElementById("btn-logs-refresh");

const $btnRefresh = document.getElementById("btn-refresh");
const $btnAdd = document.getElementById("btn-add");
const $btnImport = document.getElementById("btn-import");

const $backdrop = document.getElementById("modal-backdrop");
const $modal = document.getElementById("modal");
const $modalTitle = document.getElementById("modal-title");

const $fName = document.getElementById("f-name");
const $fPath = document.getElementById("f-path");
const $fEntry = document.getElementById("f-entry");
const $fHost = document.getElementById("f-host");
const $fPort = document.getElementById("f-port");
const $fArgs = document.getElementById("f-args");
const $fEnabled = document.getElementById("f-enabled");
const $formHint = document.getElementById("form-hint");

const $btnModalClose = document.getElementById("btn-modal-close");
const $btnCancel = document.getElementById("btn-cancel");
const $btnSave = document.getElementById("btn-save");
const $btnDelete = document.getElementById("btn-delete");

let selectedAppId = null;
let selectedAppName = null;
let editingApp = null; // full object
const $search = document.getElementById("search-input");
const $searchCount = document.getElementById("search-count");
let currentApps = [];


const $loader = document.getElementById("loading-overlay");
const $loaderText = document.getElementById("loader-text");

function showLoader(text = "Working…") {
  if ($loaderText) $loaderText.textContent = text;
  $loader.hidden = false;
  document.body.style.pointerEvents = "none"; // prevent double-clicks
}

function hideLoader() {
  $loader.hidden = true;
  document.body.style.pointerEvents = "";
}

function badge(status) {
  let dot = "mid";
  let text = status;

  if (status === "running") dot = "ok";
  if (status === "stopped") dot = "bad";
  if (status === "starting") dot = "mid";

  return `
    <span class="badge">
      <span class="dot ${dot}"></span>
      <span>${text}</span>
    </span>
  `;
}

async function api(path, method = "GET", body = null) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : null
  });

  let data = null;
  try { data = await res.json(); } catch (_) {}

  if (!res.ok) {
    // backend may return {errors:[...]}
    const detail = data && (data.detail || data.message);
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || data || `${res.status} ${res.statusText}`));
  }
  return data;
}

function openModal(mode, appObj = null) {
  editingApp = appObj;

  $formHint.textContent = "";
  $btnDelete.hidden = !appObj;

  if (mode === "add") {
    $modalTitle.textContent = "Add App";
    $fName.value = "";
    $fPath.value = "";
    $fEntry.value = "";
    $fHost.value = "127.0.0.1";
    $fPort.value = "";
    $fArgs.value = "";
    $fEnabled.checked = true;
  } else {
    $modalTitle.textContent = "Edit App";
    $fName.value = appObj.name;
    $fPath.value = appObj.path;
    $fEntry.value = appObj.entry;
    $fHost.value = appObj.host;
    $fPort.value = appObj.port;
    $fArgs.value = appObj.args || "";
    $fEnabled.checked = !!appObj.enabled;
  }

  // Prevent edit while running (UI hint; backend also enforces)
  const isRunningish = appObj && (appObj.status === "running" || appObj.status === "starting");
  if (isRunningish) {
    $formHint.textContent = "Stop this app before editing (manager enforces this).";
  }

  document.body.classList.add("modal-open"); // NEW
  $backdrop.hidden = false;
  $modal.hidden = false;
}

function closeModal() {
  document.body.classList.remove("modal-open"); // NEW
  $backdrop.hidden = true;
  $modal.hidden = true;
  editingApp = null;
}

function row(appObj) {
  const openUrl = `http://${appObj.host}:${appObj.port}/`;
  const isRunning = appObj.status === "running";
  const isStarting = appObj.status === "starting";
  const runningish = isRunning || isStarting;

  const startDisabled = runningish || !appObj.enabled;
  const stopDisabled = !runningish;
  const editDisabled = runningish; // ✅ prevent edit while running
  const deleteDisabled = runningish;

  return `
    <div class="row">
      <div>
        <strong>${appObj.name}</strong><br/>
        <span class="muted" style="font-size:12px;">${appObj.entry}</span><br/>
        <span class="muted" style="font-size:12px;">${appObj.path}</span>
      </div>

      <div>${badge(appObj.status)}</div>

      <div>${appObj.port}</div>

      <div>
        <span class="${appObj.enabled ? "" : "muted"}">
          ${appObj.enabled ? "✅ Yes" : "⛔ No"}
        </span>
      </div>

      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="btn primary" ${startDisabled ? "disabled" : ""} data-action="start" data-id="${appObj.id}">▶ Start</button>
        <button class="btn danger" ${stopDisabled ? "disabled" : ""} data-action="stop" data-id="${appObj.id}">■ Stop</button>
        <button class="btn warn" ${!appObj.enabled ? "disabled" : ""} data-action="restart" data-id="${appObj.id}">↻ Restart</button>
        <button class="btn" data-action="logs" data-id="${appObj.id}" data-name="${appObj.name}">🧾 Logs</button>
        <button class="btn" ${editDisabled ? "disabled" : ""} data-action="edit" data-id="${appObj.id}">✏ Edit</button>
        <button class="btn danger" ${deleteDisabled ? "disabled" : ""} data-action="delete" data-id="${appObj.id}">🗑</button>
      </div>

      <div>
        ${isRunning ? `<a class="link" href="${openUrl}" target="_blank">Open</a>` : `<span class="muted">—</span>`}
      </div>
    </div>
  `;
}

async function refresh() {
  const list = await api("/apps");
  list.sort((a, b) => a.name.localeCompare(b.name));

  currentApps = list;
  renderApps(list);

  if (selectedAppId) {
    $logsTitle.textContent = `Viewing: ${selectedAppName}`;
    $btnLogsRefresh.disabled = false;
  } else {
    $logsTitle.textContent = "Select an app…";
    $btnLogsRefresh.disabled = true;
  }
}
function renderApps(list) {
  if (!list.length) {
    $apps.innerHTML = `
      <div style="padding:20px; text-align:center; color:var(--muted);">
        No apps match your search.
      </div>
    `;
    return;
  }

  $apps.innerHTML = list.map(row).join("");
}
function filterApps(query) {
  query = query.toLowerCase().trim();

  if (!query) {
    renderApps(currentApps);
    $searchCount.textContent = "";
    return;
  }

  const filtered = currentApps.filter(app =>
    app.name.toLowerCase().includes(query) ||
    app.path.toLowerCase().includes(query) ||
    app.entry.toLowerCase().includes(query) ||
    String(app.port).includes(query)
  );

  renderApps(filtered);

  $searchCount.textContent = `${filtered.length} result${filtered.length !== 1 ? "s" : ""}`;
}
$search.addEventListener("input", (e) => {
  filterApps(e.target.value);
});
async function loadLogs(appId, name) {
  selectedAppId = appId;
  selectedAppName = name;

  $logsTitle.textContent = `Viewing: ${name}`;
  $btnLogsRefresh.disabled = false;

  const data = await api(`/apps/${appId}/logs`);
  const lines = data.lines || [];

  if (!lines.length) {
    $logs.textContent = "No logs yet.";
    $logs.classList.add("muted");
    return;
  }

  $logs.classList.remove("muted");
  $logs.textContent = lines.join("\n");
  $logs.scrollTop = $logs.scrollHeight;
}

function collectForm() {
  return {
    name: $fName.value.trim(),
    path: $fPath.value.trim(),
    entry: $fEntry.value.trim(),
    host: ($fHost.value || "127.0.0.1").trim(),
    port: Number($fPort.value),
    args: $fArgs.value.trim() ? $fArgs.value.trim() : null,
    enabled: !!$fEnabled.checked
  };
}

function showValidationError(err) {
  // backend returns 422 with {"errors":[{field,message}]}
  try {
    const parsed = JSON.parse(err.message);
    if (parsed && parsed.errors && Array.isArray(parsed.errors)) {
      const msg = parsed.errors.map(e => `${e.field}: ${e.message}`).join(" • ");
      $formHint.textContent = msg;
      return;
    }
  } catch (_) {}
  $formHint.textContent = err.message || String(err);
}

// Table actions
$apps.addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;

  const action = btn.dataset.action;
  const id = btn.dataset.id ? Number(btn.dataset.id) : null;

  try {
    if (action === "start") {
      showLoader("Starting app…");
      const res = await api(`/apps/${id}/start`, "POST");
      if (res.logs && res.logs.length) {
        $logsTitle.textContent = `Startup logs`;
        $logs.classList.remove("muted");
        $logs.textContent = res.logs.join("\n");
      }
    }

    if (action === "stop") {
      showLoader("Stopping app…");
      await api(`/apps/${id}/stop`, "POST");
    }
    if (action === "restart") {
      showLoader("Restarting app…");
      await api(`/apps/${id}/restart`, "POST");
    }

    if (action === "logs") {
      await loadLogs(id, btn.dataset.name);
      return;
    }

    if (action === "edit") {
      const list = await api("/apps");
      const appObj = list.find(x => x.id === id);
      openModal("edit", appObj);
      return;
    }

    if (action === "delete") {
      if (!confirm("Delete this app definition?")) return;
      await api(`/apps/${id}`, "DELETE");
    }

    await refresh();
    if (selectedAppId) await loadLogs(selectedAppId, selectedAppName);
  } catch (err) {
    alert(err.message || String(err));
  } finally {
    hideLoader();
  }
});

// Header buttons
$btnRefresh.addEventListener("click", () => refresh().catch(e => alert(e.message || String(e))));

$btnAdd.addEventListener("click", () => openModal("add"));

$btnImport.addEventListener("click", async () => {
  try {
    const res = await api("/apps/import-yaml", "POST", {});
    alert(`Imported ${res.count} app(s).`);
    await refresh();
  } catch (e) {
    alert(e.message || String(e));
  }
});

// Modal controls
$btnModalClose.addEventListener("click", closeModal);
$btnCancel.addEventListener("click", closeModal);
$backdrop.addEventListener("click", closeModal);

$btnSave.addEventListener("click", async () => {
  $formHint.textContent = "";
  try {
    const payload = collectForm();

    if (!editingApp) {
      await api("/apps", "POST", payload);
      closeModal();
      await refresh();
      return;
    }

    // UI prevents edits while running; backend enforces too.
    await api(`/apps/${editingApp.id}`, "PUT", payload);
    closeModal();
    await refresh();
  } catch (err) {
    showValidationError(err);
  }
});

$btnDelete.addEventListener("click", async () => {
  if (!editingApp) return;

  if (!confirm("Delete this app definition?")) return;
  try {
    await api(`/apps/${editingApp.id}`, "DELETE");
    closeModal();
    await refresh();
  } catch (e) {
    alert(e.message || String(e));
  }
});

$btnLogsRefresh.addEventListener("click", async () => {
  if (!selectedAppId) return;
  try { await loadLogs(selectedAppId, selectedAppName); } catch (e) { alert(e.message || String(e)); }
});

// Auto refresh every 3s
// setInterval(() => refresh().catch(() => {}), 3000);

refresh().catch((e) => alert(e.message || String(e)));
