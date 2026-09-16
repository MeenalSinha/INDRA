const ReportsPage = (() => {
  let allReports = [];

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Reports</h1>
          <p class="page-subtitle">Individual incoming reports before and after fusion</p>
        </div>
        <button class="btn btn-primary" id="new-report-btn">Submit Report</button>
      </div>

      <div class="filter-bar">
        <input class="filter-input" id="rpt-search" placeholder="Search report text or location..." />
        <select class="filter-select" id="rpt-flt-type"><option value="">All event types</option></select>
        <select class="filter-select" id="rpt-flt-source"><option value="">All source types</option>
          <option value="citizen">Citizen</option><option value="citizen_verified">Verified Citizen</option>
          <option value="social">Social Media</option><option value="weather_api">Weather API</option>
          <option value="government">Government</option><option value="news">News</option>
        </select>
        <select class="filter-select" id="rpt-flt-dup"><option value="">All duplicate statuses</option>
          <option value="UNIQUE">Unique</option><option value="LIKELY_DUPLICATE">Likely Duplicate</option>
        </select>
      </div>

      <div class="card">
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>Source</th><th>Text</th><th>Location</th><th>Classification</th>
              <th>Confidence</th><th>Duplicate</th><th>Event</th><th>Time</th>
            </tr></thead>
            <tbody id="reports-tbody"></tbody>
          </table>
        </div>
      </div>
    `;
  }

  function populateFilters(reports) {
    const typeSel = document.getElementById("rpt-flt-type");
    [...new Set(reports.map((r) => r.event_type).filter(Boolean))].sort().forEach((t) =>
      typeSel.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`));
  }

  function renderRows(reports) {
    const tbody = document.getElementById("reports-tbody");
    if (!reports.length) { tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">No reports match these filters.</div></td></tr>`; return; }
    tbody.innerHTML = reports.map((r) => `
      <tr data-id="${r.id}">
        <td><div class="cell-title">${escapeHtml(r.source)}</div><div class="cell-sub">${escapeHtml(r.source_type)}</div></td>
        <td style="max-width:280px;"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(r.text || "—")}</div></td>
        <td>${escapeHtml(r.city || "—")}</td>
        <td>${escapeHtml(r.event_type || "Pending")}</td>
        <td>${r.classification_confidence != null ? confidencePct(r.classification_confidence) + "%" : "—"}</td>
        <td>${duplicateBadge(r.duplicate_status)}</td>
        <td>${r.event_id ? `<button class="btn btn-outline" style="padding:5px 10px;" data-open-event="${r.event_id}">View</button>` : "—"}</td>
        <td>${timeAgo(r.timestamp)}</td>
      </tr>`).join("");

    tbody.querySelectorAll("[data-open-event]").forEach((btn) => {
      btn.addEventListener("click", (ev) => { ev.stopPropagation(); window.IndraApp.openInvestigation(btn.dataset.openEvent); });
    });
    tbody.querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => openReportModal(tr.dataset.id)));
  }

  async function openReportModal(id) {
    const r = await Api.report(id);
    openModal(`
      <div class="card-pad">
        <h2 class="section-title" style="margin-bottom:14px;">Report #${r.id}</h2>
        <p style="font-size:14px; margin-bottom:16px;">${escapeHtml(r.text || "(no text provided)")}</p>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:13px; color:var(--ink-soft);">
          <div><b>Source:</b> ${escapeHtml(r.source)} (${escapeHtml(r.source_type)})</div>
          <div><b>Location:</b> ${escapeHtml(r.city || "—")}, ${escapeHtml(r.state || "")}</div>
          <div><b>Classification:</b> ${escapeHtml(r.event_type || "Pending")} (${r.classification_confidence != null ? confidencePct(r.classification_confidence) + "%" : "—"})</div>
          <div><b>Duplicate status:</b> ${duplicateBadge(r.duplicate_status)}</div>
          <div><b>Processing status:</b> ${escapeHtml(r.processing_status)}</div>
          <div><b>Timestamp:</b> ${new Date(r.timestamp + "Z").toLocaleString("en-IN")}</div>
        </div>
        ${r.media && r.media.length ? `
          <div style="margin-top:18px;">
            <b style="font-size:13px;">Media evidence</b>
            ${r.media.map((m) => `<div class="reason-chip">${m.category} — ${confidencePct(m.confidence)}% (${escapeHtml(m.summary)})</div>`).join("")}
          </div>` : ""}
        <div style="display:flex; gap:10px; margin-top:20px;">
          ${r.event_id ? `<button class="btn btn-primary" id="rpt-view-event">View Linked Event</button>` : ""}
        </div>
      </div>
    `);
    if (r.event_id) document.getElementById("rpt-view-event").addEventListener("click", () => window.IndraApp.openInvestigation(r.event_id));
  }

  function applyFilters() {
    const q = document.getElementById("rpt-search").value.toLowerCase();
    const type = document.getElementById("rpt-flt-type").value;
    const source = document.getElementById("rpt-flt-source").value;
    const dup = document.getElementById("rpt-flt-dup").value;
    const filtered = allReports.filter((r) =>
      (!type || r.event_type === type) && (!source || r.source_type === source) &&
      (!dup || r.duplicate_status === dup) &&
      (!q || ((r.text || "") + (r.city || "")).toLowerCase().includes(q))
    );
    renderRows(filtered);
  }

  async function loadReports() {
    const data = await Api.reports({ limit: 500 });
    allReports = data.items;
    populateFilters(allReports);
    renderRows(allReports);
  }

  function openNewReportModal() {
    openModal(`
      <div class="card-pad">
        <h2 class="section-title" style="margin-bottom:14px;">Submit a Report</h2>
        <p class="section-subtitle" style="margin-bottom:16px;">Goes through the real ingestion pipeline — classification, duplicate detection, clustering, and fusion — exactly like any other source.</p>
        <div style="display:flex; flex-direction:column; gap:12px;">
          <select class="filter-select" id="nr-source-type" style="width:100%;">
            <option value="citizen">Citizen Report</option>
            <option value="social">Social Media</option>
            <option value="news">News Source</option>
          </select>
          <textarea id="nr-text" class="filter-input" style="width:100%; min-height:80px;" placeholder="Describe what you're observing..."></textarea>
          <div style="display:flex; gap:12px;">
            <input class="filter-input" id="nr-city" placeholder="City (e.g. Patna)" style="flex:1;" />
            <input class="filter-input" id="nr-state" placeholder="State (e.g. Bihar)" style="flex:1;" />
          </div>
          <input type="file" id="nr-file" accept="image/*,video/mp4" />
          <div id="nr-error" style="color:var(--red); font-size:12.5px; display:none;"></div>
        </div>
        <div style="display:flex; gap:10px; margin-top:20px;">
          <button class="btn btn-primary" id="nr-submit">Submit Report</button>
          <button class="btn btn-outline" id="nr-cancel">Cancel</button>
        </div>
      </div>
    `);
    document.getElementById("nr-cancel").addEventListener("click", closeModal);
    document.getElementById("nr-submit").addEventListener("click", submitNewReport);
  }

  async function submitNewReport() {
    const errEl = document.getElementById("nr-error");
    errEl.style.display = "none";
    const text = document.getElementById("nr-text").value.trim();
    const city = document.getElementById("nr-city").value.trim();
    const state = document.getElementById("nr-state").value.trim();
    const sourceType = document.getElementById("nr-source-type").value;
    const file = document.getElementById("nr-file").files[0];

    if (!text) { errEl.textContent = "Please describe what you're observing."; errEl.style.display = "block"; return; }

    const btn = document.getElementById("nr-submit");
    btn.disabled = true; btn.textContent = "Submitting…";
    try {
      let mediaFields = {};
      if (file) {
        const uploaded = await Api.uploadMedia(file);
        mediaFields = { media_url: uploaded.media_url, media_type: uploaded.media_type, media_category: uploaded.detected_category };
      }
      await Api.createReport({
        source: sourceType === "citizen" ? "Citizen Reporter App" : sourceType === "social" ? "Social Media Monitor" : "News Source",
        source_type: sourceType, text, city: city || undefined, state: state || undefined, ...mediaFields,
      });
      closeModal();
      toast("Report submitted — running through the pipeline");
      loadReports();
    } catch (e) {
      errEl.textContent = "Submission failed — please try again.";
      errEl.style.display = "block";
      btn.disabled = false; btn.textContent = "Submit Report";
    }
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    await loadReports();
    document.getElementById("new-report-btn").addEventListener("click", openNewReportModal);
    ["rpt-flt-type", "rpt-flt-source", "rpt-flt-dup"].forEach((id) => document.getElementById(id).addEventListener("change", applyFilters));
    document.getElementById("rpt-search").addEventListener("input", applyFilters);
    IndraSocket.on((msg) => {
      if (["report.received", "report.classified", "duplicates.detected"].includes(msg.type)) loadReports();
    });
  }

  return { mount };
})();
