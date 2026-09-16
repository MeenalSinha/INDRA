const Investigation = (() => {
  const BREAKDOWN_LABELS = {
    semantic_similarity: "Semantic similarity",
    geo_proximity: "Location consistency",
    time_proximity: "Time consistency",
    weather_agreement: "Weather agreement",
    source_reliability: "Source reliability",
    independent_evidence: "Independent evidence",
  };

  function reasonIcon() {
    return `<svg width="14" height="14" viewBox="0 0 24 24"><path d="M5 12l4 4L19 6" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }

  function renderTimeline(timeline) {
    if (!timeline || !timeline.length) return `<div class="empty-state">No timeline events recorded yet.</div>`;
    return timeline.map((t) => `
      <div class="timeline-item">
        <div class="timeline-dot"></div>
        <div>
          <div class="timeline-time">${new Date(t.time.endsWith("Z") ? t.time : t.time + "Z").toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST</div>
          <div class="timeline-label">${escapeHtml(t.label)}</div>
        </div>
      </div>`).join("");
  }

  function renderBreakdown(breakdown) {
    if (!breakdown || !Object.keys(breakdown).length) return `<div class="empty-state">Fusion breakdown not yet available.</div>`;
    return Object.entries(BREAKDOWN_LABELS).map(([key, label]) => {
      const val = breakdown[key];
      if (val === undefined) return "";
      const pct = Math.round(val * 100);
      return `
        <div class="breakdown-row">
          <div class="breakdown-label">${label}</div>
          <div class="breakdown-bar-track"><div class="breakdown-bar-fill" style="width:${pct}%"></div></div>
          <div class="breakdown-value">${pct}%</div>
        </div>`;
    }).join("");
  }

  function renderReasons(reasons) {
    if (!reasons || !reasons.length) return "";
    return reasons.map((r) => `<div class="reason-chip">${reasonIcon()}<span>${escapeHtml(r)}</span></div>`).join("");
  }

  async function open(eventId) {
    openModal(`<div class="card-pad"><div class="empty-state">Loading investigation…</div></div>`);
    const [event, evidence] = await Promise.all([Api.event(eventId), Api.eventEvidence(eventId)]);
    renderPanel(event, evidence);
  }

  function renderPanel(e, evidence) {
    const disableActions = e.verification_status === "VERIFIED" || e.verification_status === "REJECTED";
    const html = `
      <div class="card-pad">
        <div class="investigation-header">
          <div class="investigation-title-row">
            <div class="investigation-title">${escapeHtml(e.title)}</div>
            ${severityBadge(e.severity)}
            ${statusBadge(e.verification_status)}
          </div>
          <div class="confidence-ring-wrap">
            <div style="text-align:right;">
              <div style="font-size:22px; font-weight:800; color:var(--ink);">${confidencePct(e.confidence)}%</div>
              <div style="font-size:11px; color:var(--muted);">confidence</div>
            </div>
          </div>
        </div>
        <div style="font-size:12.5px; color:var(--muted); margin:-10px 0 18px;">
          ${escapeHtml(e.event_code)} · ${escapeHtml(e.city || "")}, ${escapeHtml(e.state || "")} ·
          First detected ${new Date(e.start_time + "Z").toLocaleTimeString("en-IN")} ·
          Last updated ${new Date(e.last_updated + "Z").toLocaleTimeString("en-IN")}
        </div>

        <div class="evidence-grid">
          <div class="evidence-stat"><div class="evidence-stat-value">${evidence.reports}</div><div class="evidence-stat-label">Reports</div></div>
          <div class="evidence-stat"><div class="evidence-stat-value">${evidence.independent_sources}</div><div class="evidence-stat-label">Independent sources</div></div>
          <div class="evidence-stat"><div class="evidence-stat-value">${evidence.images}</div><div class="evidence-stat-label">Images</div></div>
          <div class="evidence-stat"><div class="evidence-stat-value">${evidence.weather_observations}</div><div class="evidence-stat-label">Weather observations</div></div>
        </div>

        <div class="investigation-grid" style="margin-top:22px;">
          <div>
            <h3 class="section-title" style="margin-bottom:14px;">Event Timeline</h3>
            ${renderTimeline(e.timeline)}
          </div>
          <div>
            <h3 class="section-title" style="margin-bottom:10px;">Confidence Breakdown</h3>
            ${renderBreakdown(e.fusion_breakdown)}
            <div style="border-top:1px solid var(--border-soft); margin-top:14px; padding-top:14px;">
              <h3 class="section-title" style="margin-bottom:8px; font-size:13.5px;">Severity Reasoning</h3>
              ${renderReasons(e.severity_reasons)}
            </div>
          </div>
        </div>

        <div id="investigation-map" style="height:260px; border-radius:9px; margin-top:22px; border:1px solid var(--border-soft);"></div>

        <div style="display:flex; gap:10px; margin-top:22px; flex-wrap:wrap;">
          <button class="btn btn-teal" id="act-verify" ${disableActions ? "disabled" : ""}>Verify Event</button>
          <button class="btn btn-red" id="act-reject" ${disableActions ? "disabled" : ""}>Reject</button>
          <button class="btn btn-outline" id="act-more-evidence" ${disableActions ? "disabled" : ""}>Request More Evidence</button>
          <button class="btn btn-outline" id="act-escalate" ${disableActions ? "disabled" : ""}>Escalate Severity</button>
        </div>
      </div>
    `;
    openModal(html);

    setTimeout(() => {
      if (e.latitude != null) {
        const m = L.map("investigation-map", { zoomControl: false, attributionControl: false }).setView([e.latitude, e.longitude], 11);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png").addTo(m);
        L.circle([e.latitude, e.longitude], {
          radius: (e.affected_area_km2 ? Math.sqrt(e.affected_area_km2 / Math.PI) * 1000 : 2000),
          color: eventColor(e.event_type), fillColor: eventColor(e.event_type), fillOpacity: 0.18,
        }).addTo(m);
        L.circleMarker([e.latitude, e.longitude], { radius: 7, fillColor: eventColor(e.event_type), color: "#fff", weight: 2, fillOpacity: 1 }).addTo(m);
      }
    }, 50);

    const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
    bind("act-verify", () => runAction(() => Api.verifyEvent(e.id, { admin_name: "Sixth Sense Admin", reason: "Corroborated by independent sources" }), "Event verified"));
    bind("act-reject", () => runAction(() => Api.rejectEvent(e.id, { admin_name: "Sixth Sense Admin", reason: "Insufficient corroborating evidence" }), "Event rejected"));
    bind("act-more-evidence", () => runAction(() => Api.requestEvidence(e.id, { admin_name: "Sixth Sense Admin", reason: "Requested additional field evidence" }), "More evidence requested"));
    bind("act-escalate", () => runAction(() => Api.escalateEvent(e.id, { admin_name: "Sixth Sense Admin", reason: "Escalated on review" }), "Severity escalated"));
  }

  async function runAction(fn, message) {
    try {
      await fn();
      toast(message);
      closeModal();
      if (window.IndraApp.refreshCurrentPage) window.IndraApp.refreshCurrentPage();
    } catch (err) {
      toast("Action failed — please try again");
    }
  }

  return { open };
})();
