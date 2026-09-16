const AdminPage = (() => {
  const TABS = ["Overview", "Pending Verification", "Suspicious Reports", "Duplicate Reports", "Critical Events", "Source Reliability", "Audit Logs", "System Health"];
  let activeTab = "Overview";
  let pollHandle = null;

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Admin Panel</h1>
          <p class="page-subtitle">Verification queue, source trust, audit trail and Judge Mode controls</p>
        </div>
      </div>
      <div class="admin-tabs" id="admin-tabs">
        ${TABS.map((t) => `<button class="admin-tab ${t === activeTab ? "active" : ""}" data-tab="${t}">${t}</button>`).join("")}
      </div>
      <div id="admin-tab-content"></div>
    `;
  }

  function judgeModeCard(status) {
    const running = status.running;
    const pct = status.total ? Math.round((status.processed / status.total) * 100) : 0;
    return `
      <div class="card card-pad" style="margin-bottom:18px;">
        <div class="section-header">
          <div>
            <h2 class="section-title">Judge Mode — Patna Flood Scenario</h2>
            <p class="section-subtitle">Runs the full pipeline live: citizen reports → social reports → weather observation → image evidence → AI classification → duplicate grouping → geospatial clustering → fusion → CRITICAL event → admin verification.</p>
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:14px; margin-top:14px; flex-wrap:wrap;">
          <button class="btn btn-primary" id="judge-start" ${running ? "disabled" : ""}>Start Demo</button>
          <button class="btn btn-outline" id="judge-pause" ${!running ? "disabled" : ""}>${status.paused ? "Resume" : "Pause"}</button>
          <button class="btn btn-outline" id="judge-reset">Reset</button>
          <div style="flex:1; min-width:180px;">
            <div class="breakdown-bar-track"><div class="breakdown-bar-fill" style="width:${pct}%; background:var(--teal);"></div></div>
          </div>
          <div style="font-size:12.5px; color:var(--ink-soft); white-space:nowrap;">${status.processed} / ${status.total || "—"} reports processed</div>
        </div>
      </div>
    `;
  }

  async function renderOverview() {
    const [overview, status] = await Promise.all([Api.adminOverview(), Api.demoStatus()]);
    return judgeModeCard(status) + `
      <div class="metric-grid">
        <div class="card overview-tile"><div class="overview-tile-value">${overview.pending_verification}</div><div class="overview-tile-label">Pending Verification</div></div>
        <div class="card overview-tile"><div class="overview-tile-value">${overview.suspicious_reports}</div><div class="overview-tile-label">Suspicious Reports</div></div>
        <div class="card overview-tile"><div class="overview-tile-value">${overview.duplicate_reports}</div><div class="overview-tile-label">Duplicate Reports</div></div>
        <div class="card overview-tile"><div class="overview-tile-value">${overview.critical_events}</div><div class="overview-tile-label">Critical Events</div></div>
      </div>
    `;
  }

  async function renderEventQueue(filterFn, emptyMsg) {
    const data = await Api.events({ limit: 300 });
    const rows = data.items.filter(filterFn);
    if (!rows.length) return `<div class="card"><div class="empty-state">${emptyMsg}</div></div>`;
    return `<div class="card"><div class="table-wrap"><table class="data-table">
      <thead><tr><th>Event</th><th>Location</th><th>Severity</th><th>Confidence</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows.map((e) => `
        <tr data-id="${e.id}">
          <td><div class="cell-title">${escapeHtml(e.title)}</div><div class="cell-sub">${escapeHtml(e.event_code)}</div></td>
          <td>${escapeHtml(e.city || "—")}, ${escapeHtml(e.state || "")}</td>
          <td>${severityBadge(e.severity)}</td>
          <td>${confidencePct(e.confidence)}%</td>
          <td>${statusBadge(e.verification_status)}</td>
          <td><button class="btn btn-outline" data-investigate="${e.id}">Investigate</button></td>
        </tr>`).join("")}</tbody></table></div></div>`;
  }

  async function renderSuspiciousReports() {
    const data = await Api.reports({ limit: 300 });
    const rows = data.items.filter((r) => r.classification_confidence != null && r.classification_confidence < 0.5);
    if (!rows.length) return `<div class="card"><div class="empty-state">No suspicious (low-confidence) reports right now.</div></div>`;
    return `<div class="card"><div class="table-wrap"><table class="data-table">
      <thead><tr><th>Source</th><th>Text</th><th>Classification</th><th>Confidence</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${escapeHtml(r.source)}</td><td>${escapeHtml(r.text || "—")}</td><td>${escapeHtml(r.event_type || "—")}</td><td>${confidencePct(r.classification_confidence)}%</td></tr>`).join("")}</tbody>
    </table></div></div>`;
  }

  async function renderDuplicateReports() {
    const data = await Api.reports({ limit: 300 });
    const rows = data.items.filter((r) => r.duplicate_status === "LIKELY_DUPLICATE");
    if (!rows.length) return `<div class="card"><div class="empty-state">No duplicate reports detected right now.</div></div>`;
    return `<div class="card"><div class="table-wrap"><table class="data-table">
      <thead><tr><th>Report</th><th>Text</th><th>Duplicate of</th><th>Location</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>#${r.id}</td><td>${escapeHtml(r.text || "—")}</td><td>#${r.duplicate_of_report_id ?? "—"}</td><td>${escapeHtml(r.city || "—")}</td></tr>`).join("")}</tbody>
    </table></div></div>`;
  }

  async function renderSourceReliability() {
    const data = await Api.sources();
    return `<div class="card"><div class="table-wrap"><table class="data-table">
      <thead><tr><th>Source</th><th>Type</th><th>Trust Level</th><th>Reliability Score</th><th>Verification History</th></tr></thead>
      <tbody>${data.items.map((s) => `
        <tr><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.source_type)}</td>
        <td><span class="badge ${s.trust_level === "HIGH TRUST" ? "badge-verified" : s.trust_level === "MEDIUM TRUST" ? "badge-moderate" : "badge-low"}">${escapeHtml(s.trust_level)}</span></td>
        <td>${confidencePct(s.reliability_score)}%</td><td>${s.verification_history_count}</td></tr>`).join("")}</tbody>
    </table></div></div>`;
  }

  async function renderAuditLogs() {
    const data = await Api.auditLogs(200);
    if (!data.items.length) return `<div class="card"><div class="empty-state">No audit records yet.</div></div>`;
    return `<div class="card"><div class="table-wrap"><table class="data-table">
      <thead><tr><th>Actor</th><th>Action</th><th>Target</th><th>Details</th><th>Time</th></tr></thead>
      <tbody>${data.items.map((a) => `
        <tr><td>${escapeHtml(a.actor)}</td><td>${escapeHtml(a.action)}</td><td>${escapeHtml(a.target_type)} #${a.target_id ?? "—"}</td>
        <td style="font-size:12px; color:var(--muted);">${escapeHtml(a.details.reason || a.details.new_state || "—")}</td>
        <td>${timeAgo(a.created_at)}</td></tr>`).join("")}</tbody>
    </table></div></div>`;
  }

  async function renderSystemHealth() {
    const h = await Api.health();
    const row = (label, val) => `
      <div class="card overview-tile"><div style="display:flex;align-items:center;gap:8px;"><span class="status-dot"></span><b style="font-size:13px;">${label}</b></div><div style="font-size:12px;color:var(--muted); margin-top:4px;">${val}</div></div>`;
    return `<div class="metric-grid">
      ${row("API", h.api)}${row("Database", h.database + " — " + h.mode)}${row("Cache", h.cache)}${row("Streaming", h.streaming)}
      ${row("AI Engine", h.ai_engine)}${row("WebSocket", h.websocket)}
    </div>
    <div class="metric-grid" style="margin-top:16px;">
      <div class="card overview-tile"><div class="overview-tile-value">${h.reports_per_min}</div><div class="overview-tile-label">Reports / min</div></div>
      <div class="card overview-tile"><div class="overview-tile-value">${h.events_per_min}</div><div class="overview-tile-label">Events updated / min</div></div>
      <div class="card overview-tile"><div class="overview-tile-value">${h.avg_processing_latency_ms} ms</div><div class="overview-tile-label">Avg processing latency</div></div>
      <div class="card overview-tile"><div class="overview-tile-value">${h.stream_queue_depth}</div><div class="overview-tile-label">Stream queue depth</div></div>
    </div>
    <div class="card card-pad" style="margin-top:16px;">
      <h3 class="section-title" style="margin-bottom:8px;">Totals</h3>
      <div style="font-size:13px; color:var(--ink-soft);">Reports processed: <b>${h.reports_total}</b> &nbsp;·&nbsp; Events tracked: <b>${h.events_total}</b></div>
    </div>`;
  }

  async function renderTabContent() {
    const content = document.getElementById("admin-tab-content");
    content.innerHTML = `<div class="empty-state">Loading…</div>`;
    let html = "";
    if (activeTab === "Overview") html = await renderOverview();
    else if (activeTab === "Pending Verification") html = await renderEventQueue((e) => ["UNDER_REVIEW", "PROBABLE", "UNVERIFIED"].includes(e.verification_status), "Nothing pending verification.");
    else if (activeTab === "Suspicious Reports") html = await renderSuspiciousReports();
    else if (activeTab === "Duplicate Reports") html = await renderDuplicateReports();
    else if (activeTab === "Critical Events") html = await renderEventQueue((e) => e.severity === "CRITICAL", "No critical events right now.");
    else if (activeTab === "Source Reliability") html = await renderSourceReliability();
    else if (activeTab === "Audit Logs") html = await renderAuditLogs();
    else if (activeTab === "System Health") html = await renderSystemHealth();
    content.innerHTML = html;

    content.querySelectorAll("[data-investigate]").forEach((btn) => btn.addEventListener("click", () => window.IndraApp.openInvestigation(btn.dataset.investigate)));
    content.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => window.IndraApp.openInvestigation(tr.dataset.id)));

    if (activeTab === "Overview") {
      document.getElementById("judge-start").addEventListener("click", async () => { await Api.demoStart(); toast("Judge Mode started"); pollJudgeMode(); });
      document.getElementById("judge-pause").addEventListener("click", async () => { await Api.demoPause(); pollJudgeMode(); });
      document.getElementById("judge-reset").addEventListener("click", async () => { await Api.demoReset(); toast("Demo reset to clean state"); renderTabContent(); });
    }
  }

  function pollJudgeMode() {
    if (pollHandle) clearInterval(pollHandle);
    pollHandle = setInterval(async () => {
      if (activeTab !== "Overview") { clearInterval(pollHandle); return; }
      const status = await Api.demoStatus();
      const wrap = document.querySelector("#admin-tab-content .card-pad");
      if (wrap) wrap.outerHTML = judgeModeCard(status);
      document.getElementById("judge-start").addEventListener("click", async () => { await Api.demoStart(); toast("Judge Mode started"); pollJudgeMode(); });
      document.getElementById("judge-pause").addEventListener("click", async () => { await Api.demoPause(); pollJudgeMode(); });
      document.getElementById("judge-reset").addEventListener("click", async () => { await Api.demoReset(); toast("Demo reset to clean state"); renderTabContent(); clearInterval(pollHandle); });
      if (!status.running) clearInterval(pollHandle);
    }, 1500);
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    document.querySelectorAll("#admin-tabs .admin-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.dataset.tab;
        document.querySelectorAll("#admin-tabs .admin-tab").forEach((b) => b.classList.toggle("active", b === btn));
        renderTabContent();
      });
    });
    await renderTabContent();
    IndraSocket.on((msg) => {
      if (msg.type.startsWith("event.") || msg.type === "demo.reset") renderTabContent();
    });
  }

  return { mount };
})();
