const EventsPage = (() => {
  let allEvents = [];

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Events</h1>
          <p class="page-subtitle">All detected weather events, fused from multi-source reports</p>
        </div>
      </div>

      <div class="filter-bar">
        <input class="filter-input" id="evt-search" placeholder="Search by event, location or event ID..." />
        <select class="filter-select" id="evt-flt-type"><option value="">All event types</option></select>
        <select class="filter-select" id="evt-flt-state"><option value="">All states</option></select>
        <select class="filter-select" id="evt-flt-severity">
          <option value="">All severities</option><option>CRITICAL</option><option>HIGH</option><option>MODERATE</option><option>LOW</option>
        </select>
        <select class="filter-select" id="evt-flt-status">
          <option value="">All statuses</option><option value="VERIFIED">Verified</option><option value="PROBABLE">Probable</option>
          <option value="UNDER_REVIEW">Under Review</option><option value="REJECTED">Rejected</option><option value="UNVERIFIED">Unverified</option>
        </select>
      </div>

      <div class="card">
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Event</th><th>Type</th><th>Location</th><th>Severity</th><th>Confidence</th>
              <th>Reports</th><th>Status</th><th>First Seen</th><th>Last Updated</th>
            </tr></thead>
            <tbody id="events-tbody"></tbody>
          </table>
        </div>
      </div>
    `;
  }

  function populateFilters(events) {
    const typeSel = document.getElementById("evt-flt-type");
    const stateSel = document.getElementById("evt-flt-state");
    [...new Set(events.map((e) => e.event_type))].sort().forEach((t) =>
      typeSel.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`));
    [...new Set(events.map((e) => e.state).filter(Boolean))].sort().forEach((s) =>
      stateSel.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`));
  }

  function renderRows(events) {
    const tbody = document.getElementById("events-tbody");
    if (!events.length) { tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state">No events match these filters.</div></td></tr>`; return; }
    tbody.innerHTML = events.map((e) => `
      <tr data-id="${e.id}">
        <td><div class="cell-title">${escapeHtml(e.title)}</div><div class="cell-sub">${escapeHtml(e.event_code)}</div></td>
        <td>${escapeHtml(e.event_type)}</td>
        <td>${escapeHtml(e.city || "—")}, ${escapeHtml(e.state || "")}</td>
        <td>${severityBadge(e.severity)}</td>
        <td>${confidencePct(e.confidence)}%</td>
        <td>${e.report_count}</td>
        <td>${statusBadge(e.verification_status)}</td>
        <td>${new Date(e.start_time + "Z").toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</td>
        <td>${timeAgo(e.last_updated)}</td>
      </tr>`).join("");
    tbody.querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => window.IndraApp.openInvestigation(tr.dataset.id)));
  }

  function applyFilters() {
    const q = document.getElementById("evt-search").value.toLowerCase();
    const type = document.getElementById("evt-flt-type").value;
    const state = document.getElementById("evt-flt-state").value;
    const severity = document.getElementById("evt-flt-severity").value;
    const status = document.getElementById("evt-flt-status").value;
    const filtered = allEvents.filter((e) =>
      (!type || e.event_type === type) && (!state || e.state === state) &&
      (!severity || e.severity === severity) && (!status || e.verification_status === status) &&
      (!q || (e.title + e.event_code + (e.city || "")).toLowerCase().includes(q))
    );
    renderRows(filtered);
  }

  async function loadEvents() {
    const data = await Api.events({ limit: 500 });
    allEvents = data.items;
    populateFilters(allEvents);
    renderRows(allEvents);
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    await loadEvents();
    ["evt-flt-type", "evt-flt-state", "evt-flt-severity", "evt-flt-status"].forEach((id) =>
      document.getElementById(id).addEventListener("change", applyFilters));
    document.getElementById("evt-search").addEventListener("input", applyFilters);
    IndraSocket.on((msg) => {
      if (["event.updated", "event.verified", "event.rejected"].includes(msg.type)) loadEvents();
    });
  }

  return { mount };
})();
