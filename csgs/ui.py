from __future__ import annotations


def render_ui() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSGS Explorer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --surface: #ffffff;
      --surface-alt: #eef6f3;
      --border: #d8dee4;
      --text: #172026;
      --muted: #5d6975;
      --primary: #1565c0;
      --primary-strong: #0d47a1;
      --accent: #2e7d59;
      --danger: #b42318;
      --focus: #f5b642;
      --shadow: 0 1px 2px rgba(16, 24, 40, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    a { color: var(--primary); }
    button, input, select, textarea {
      font: inherit;
    }
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 2px;
    }
    .shell {
      min-height: 100dvh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
      font-weight: 650;
    }
    .status {
      min-height: 22px;
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      gap: 0;
      min-height: 0;
    }
    aside {
      border-right: 1px solid var(--border);
      background: var(--surface);
      padding: 16px;
      overflow: auto;
    }
    section {
      min-width: 0;
      padding: 16px;
      overflow: auto;
    }
    .field {
      display: grid;
      gap: 6px;
      margin-bottom: 12px;
    }
    label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      text-transform: uppercase;
    }
    input, select, textarea {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 9px 11px;
    }
    textarea {
      min-height: 110px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    button {
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      padding: 9px 12px;
      cursor: pointer;
      box-shadow: var(--shadow);
    }
    button.primary {
      background: var(--primary);
      border-color: var(--primary);
      color: white;
    }
    button.primary:hover {
      background: var(--primary-strong);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      min-height: 72px;
    }
    .metric span {
      color: var(--muted);
      display: block;
      font-size: 12px;
      font-weight: 650;
      text-transform: uppercase;
    }
    .metric strong {
      display: block;
      margin-top: 4px;
      font-size: 18px;
      line-height: 1.3;
      word-break: break-word;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: var(--surface-alt);
    }
    .panel-head h2 {
      margin: 0;
      font-size: 14px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      background: #fbfcfd;
    }
    tr[data-selected="true"] {
      background: #eef4ff;
    }
    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }
    .muted {
      color: var(--muted);
    }
    .empty {
      padding: 30px 14px;
      color: var(--muted);
      text-align: center;
    }
    .detail {
      margin-top: 14px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
      gap: 14px;
      align-items: start;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      background: #101820;
      color: #eef6f3;
      padding: 12px;
      min-height: 140px;
      overflow: auto;
    }
    .error {
      color: var(--danger);
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--border); }
      .summary { grid-template-columns: 1fr 1fr; }
      .detail { grid-template-columns: 1fr; }
    }
    @media (max-width: 520px) {
      header { align-items: flex-start; flex-direction: column; }
      .status { text-align: left; }
      .row, .summary { grid-template-columns: 1fr; }
      th:nth-child(3), td:nth-child(3) { display: none; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <h1>CSGS Explorer</h1>
      <div id="status" class="status" role="status" aria-live="polite"></div>
    </header>
    <main>
      <aside>
        <div class="field">
          <label for="token">Token</label>
          <input id="token" type="password" autocomplete="current-password">
        </div>
        <div class="field">
          <label for="project">Project</label>
          <input id="project" placeholder="github:owner/repo">
        </div>
        <div class="field">
          <label for="group">Group</label>
          <input id="group" placeholder="market-research">
        </div>
        <div class="field">
          <label for="text">Text</label>
          <input id="text" placeholder="summary text">
        </div>
        <div class="field">
          <label for="session">Session</label>
          <input id="session" placeholder="S_...">
        </div>
        <div class="actions">
          <button id="saveToken">Save Token</button>
          <button id="search" class="primary">Search</button>
          <button id="clear">Clear</button>
        </div>
      </aside>
      <section>
        <div class="summary">
          <div class="metric"><span>Entries</span><strong id="entryCount">0</strong></div>
          <div class="metric"><span>Project</span><strong id="projectMetric">-</strong></div>
          <div class="metric"><span>Session</span><strong id="sessionMetric">-</strong></div>
          <div class="metric"><span>Mode</span><strong id="modeMetric">Idle</strong></div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <h2>Entries</h2>
            <span id="resultLabel" class="muted">No query</span>
          </div>
          <div style="overflow:auto">
            <table>
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Summary</th>
                  <th>Project</th>
                  <th>Session</th>
                </tr>
              </thead>
              <tbody id="entries">
                <tr><td colspan="4" class="empty">No entries loaded</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="detail">
          <div class="panel">
            <div class="panel-head">
              <h2>Selected Entry</h2>
              <button id="trace">Trace</button>
            </div>
            <pre id="raw">{}</pre>
          </div>
          <div class="panel">
            <div class="panel-head"><h2>Lineage</h2></div>
            <pre id="lineage"></pre>
          </div>
        </div>
      </section>
    </main>
  </div>
  <script>
    const state = { entries: [], selected: null };
    const $ = (id) => document.getElementById(id);
    const status = (text, isError = false) => {
      $("status").textContent = text;
      $("status").className = isError ? "status error" : "status";
    };
    const tokenFromUrl = new URLSearchParams(location.search).get("token");
    if (tokenFromUrl) {
      localStorage.setItem("csgsToken", tokenFromUrl);
      history.replaceState(null, "", location.pathname);
    }
    $("token").value = localStorage.getItem("csgsToken") || "";

    function headers() {
      const token = $("token").value.trim();
      return token ? { Authorization: `Bearer ${token}` } : {};
    }

    async function request(path) {
      const response = await fetch(path, { headers: headers() });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const contentType = response.headers.get("content-type") || "";
      return contentType.includes("application/json") ? response.json() : response.text();
    }

    function queryPath() {
      const project = $("project").value.trim();
      const group = $("group").value.trim();
      const text = $("text").value.trim();
      const session = $("session").value.trim();
      if (session) return `/api/entries?session_id=${encodeURIComponent(session)}`;
      if (group) return `/api/entries?group=${encodeURIComponent(group)}`;
      if (project && !text) return `/api/entries?project=${encodeURIComponent(project)}`;
      const params = new URLSearchParams();
      if (project) params.set("project", project);
      if (text) params.set("text", text);
      return `/api/search?${params.toString()}`;
    }

    function normalizeRows(payload) {
      if (!Array.isArray(payload)) return [];
      return payload.map((item) => {
        if (item.summary !== undefined && item.session_id !== undefined) return item;
        return {
          id: item.id,
          project_id: item.project,
          session_id: item.id,
          summary: item.summary || "",
          created_at: item.created_at,
          raw_session: item,
        };
      });
    }

    function renderEntries() {
      $("entryCount").textContent = String(state.entries.length);
      $("projectMetric").textContent = $("project").value.trim() || "-";
      $("sessionMetric").textContent = $("session").value.trim() || "-";
      const body = $("entries");
      body.innerHTML = "";
      if (!state.entries.length) {
        body.innerHTML = '<tr><td colspan="4" class="empty">No matching entries</td></tr>';
        $("raw").textContent = "{}";
        $("lineage").textContent = "";
        return;
      }
      for (const entry of state.entries) {
        const row = document.createElement("tr");
        row.dataset.selected = state.selected && state.selected.id === entry.id ? "true" : "false";
        row.innerHTML = `
          <td class="mono">${escapeHtml(entry.created_at || "")}</td>
          <td>${escapeHtml(entry.summary || "")}</td>
          <td class="mono">${escapeHtml(entry.project_id || entry.project || "")}</td>
          <td class="mono">${escapeHtml(entry.session_id || entry.id || "")}</td>
        `;
        row.addEventListener("click", () => selectEntry(entry));
        body.appendChild(row);
      }
    }

    function selectEntry(entry) {
      state.selected = entry;
      $("raw").textContent = JSON.stringify(entry, null, 2);
      $("lineage").textContent = "";
      renderEntries();
    }

    async function search() {
      $("search").disabled = true;
      $("modeMetric").textContent = "Loading";
      status("Loading");
      try {
        const payload = await request(queryPath());
        state.entries = normalizeRows(payload);
        state.selected = state.entries[0] || null;
        $("resultLabel").textContent = queryPath();
        $("modeMetric").textContent = "Ready";
        if (state.selected) $("raw").textContent = JSON.stringify(state.selected, null, 2);
        renderEntries();
        status("Ready");
      } catch (error) {
        $("modeMetric").textContent = "Error";
        status(error.message, true);
      } finally {
        $("search").disabled = false;
      }
    }

    async function trace() {
      const sessionId = state.selected && (state.selected.session_id || state.selected.id);
      if (!sessionId) return;
      status("Loading trace");
      try {
        $("lineage").textContent = await request(`/api/sessions/${encodeURIComponent(sessionId)}/trace`);
        status("Ready");
      } catch (error) {
        status(error.message, true);
      }
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    $("saveToken").addEventListener("click", () => {
      localStorage.setItem("csgsToken", $("token").value.trim());
      status("Token saved");
    });
    $("search").addEventListener("click", search);
    $("clear").addEventListener("click", () => {
      for (const id of ["project", "group", "text", "session"]) $(id).value = "";
      state.entries = [];
      state.selected = null;
      $("modeMetric").textContent = "Idle";
      $("resultLabel").textContent = "No query";
      renderEntries();
      status("");
    });
    $("trace").addEventListener("click", trace);
  </script>
</body>
</html>
"""
