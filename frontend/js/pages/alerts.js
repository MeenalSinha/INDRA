const AlertsPage = (() => {
  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Alerts</h1>
          <p class="page-subtitle">Critical weather events and system alerts requiring attention</p>
        </div>
      </div>
      <div id="alerts-list"></div>
    `;
  }

  function alertIcon() {
    return `<svg width="18" height="18" viewBox="0 0 24 24"><path d="M12 3 2 20h20L12 3Z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M12 10v4M12 17h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
  }

  async function loadAlerts() {
    const data = await Api.alerts({});
    const list = document.getElementById("alerts-list");
    if (!data.items.length) { list.innerHTML = `<div class="card"><div class="empty-state">No active alerts. All clear.</div></div>`; return; }
    list.innerHTML = data.items.map((a) => `
      <div class="card alert-card level-${a.level}">
        <div class="alert-icon">${alertIcon()}</div>
        <div style="flex:1;">
          <div style="display:flex; align-items:center; gap:8px;">
            <b style="font-size:14px;">${escapeHtml(a.title)}</b>
            <span class="badge badge-${a.level === "CRITICAL" ? "critical" : a.level === "HIGH" || a.level === "WARNING" ? "high" : "low"}">${a.level}</span>
            ${a.acknowledged ? '<span class="badge badge-verified">ACKNOWLEDGED</span>' : ""}
          </div>
          <div style="font-size:13px; color:var(--ink-soft); margin-top:4px;">${escapeHtml(a.message)}</div>
          <div style="font-size:11.5px; color:var(--muted); margin-top:6px;">${timeAgo(a.created_at)}</div>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${a.event_id ? `<button class="btn btn-outline" data-investigate="${a.event_id}">Investigate</button>` : ""}
          ${!a.acknowledged ? `<button class="btn btn-outline" data-ack="${a.id}">Acknowledge</button>` : ""}
        </div>
      </div>
    `).join("");

    list.querySelectorAll("[data-investigate]").forEach((btn) => btn.addEventListener("click", () => window.IndraApp.openInvestigation(btn.dataset.investigate)));
    list.querySelectorAll("[data-ack]").forEach((btn) => btn.addEventListener("click", async () => { await Api.acknowledgeAlert(btn.dataset.ack); loadAlerts(); }));
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    await loadAlerts();
    IndraSocket.on((msg) => { if (msg.type === "alert.created") loadAlerts(); });
  }

  return { mount };
})();
