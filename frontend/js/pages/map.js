const MapPage = (() => {
  let map = null;
  let markersLayer = null;
  let heatLayer = null;
  let allEvents = [];

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Live Map</h1>
          <p class="page-subtitle">Full geospatial view of verified and emerging weather events across India</p>
        </div>
      </div>

      <div class="filter-bar">
        <select class="filter-select" id="flt-event-type"><option value="">All event types</option></select>
        <select class="filter-select" id="flt-state"><option value="">All states</option></select>
        <select class="filter-select" id="flt-severity">
          <option value="">All severities</option>
          <option>CRITICAL</option><option>HIGH</option><option>MODERATE</option><option>LOW</option>
        </select>
        <select class="filter-select" id="flt-verification">
          <option value="">All verification statuses</option>
          <option value="VERIFIED">Verified</option><option value="PROBABLE">Probable</option>
          <option value="UNDER_REVIEW">Under Review</option><option value="REJECTED">Rejected</option>
          <option value="UNVERIFIED">Unverified</option>
        </select>
        <button class="btn btn-outline" id="toggle-heatmap">Toggle Heatmap</button>
      </div>

      <div class="card" style="padding:16px;">
        <div id="live-map" style="height:620px; border-radius:9px;"></div>
      </div>
    `;
  }

  function initMap() {
    map = L.map("live-map").setView([22.5, 80], 4.6);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", { maxZoom: 18 }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
  }

  function renderMarkers(events) {
    markersLayer.clearLayers();
    events.forEach((e) => {
      if (e.latitude == null) return;
      const radius = e.severity === "CRITICAL" ? 11 : e.severity === "HIGH" ? 9 : e.severity === "MODERATE" ? 7 : 6;
      const marker = L.circleMarker([e.latitude, e.longitude], {
        radius, color: "#fff", weight: 1.5, fillColor: eventColor(e.event_type), fillOpacity: 0.9,
      }).addTo(markersLayer);
      marker.bindPopup(`
        <div style="min-width:200px; font-family:Inter,sans-serif;">
          <b>${escapeHtml(e.title)}</b><br>
          <span style="font-size:12px;color:#7c879c">${escapeHtml(e.event_code)}</span><br>
          ${severityBadge(e.severity)} ${statusBadge(e.verification_status)}<br><br>
          Confidence: <b>${confidencePct(e.confidence)}%</b><br>
          Reports: <b>${e.report_count}</b><br>
          First detected: ${new Date(e.start_time + "Z").toLocaleTimeString("en-IN")}<br><br>
          <button class="btn btn-primary" style="width:100%;" onclick="window.IndraApp.openInvestigation(${e.id})">Investigate Event</button>
        </div>
      `);
    });
  }

  function populateFilterOptions(events) {
    const typeSel = document.getElementById("flt-event-type");
    const stateSel = document.getElementById("flt-state");
    if (typeSel.options.length <= 1) {
      [...new Set(events.map((e) => e.event_type))].sort().forEach((t) => {
        typeSel.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`);
      });
    }
    if (stateSel.options.length <= 1) {
      [...new Set(events.map((e) => e.state).filter(Boolean))].sort().forEach((s) => {
        stateSel.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`);
      });
    }
  }

  function applyFilters() {
    const type = document.getElementById("flt-event-type").value;
    const state = document.getElementById("flt-state").value;
    const severity = document.getElementById("flt-severity").value;
    const verification = document.getElementById("flt-verification").value;
    const filtered = allEvents.filter((e) =>
      (!type || e.event_type === type) &&
      (!state || e.state === state) &&
      (!severity || e.severity === severity) &&
      (!verification || e.verification_status === verification)
    );
    renderMarkers(filtered);
  }

  async function loadEvents() {
    const data = await Api.events({ limit: 300 });
    allEvents = data.items;
    populateFilterOptions(allEvents);
    renderMarkers(allEvents);
  }

  let heatOn = false;
  let heatLayerInstance = null;
  function toggleHeatmap() {
    heatOn = !heatOn;
    if (heatOn) {
      markersLayer.clearLayers();
      const points = allEvents.filter((e) => e.latitude != null).map((e) => {
        const intensity = e.severity === "CRITICAL" ? 1.0 : e.severity === "HIGH" ? 0.7 : e.severity === "MODERATE" ? 0.45 : 0.25;
        return [e.latitude, e.longitude, intensity * Math.min(2, Math.log2((e.report_count || 1) + 1))];
      });
      heatLayerInstance = L.heatLayer(points, { radius: 32, blur: 24, maxZoom: 8 }).addTo(map);
    } else {
      if (heatLayerInstance) { map.removeLayer(heatLayerInstance); heatLayerInstance = null; }
      renderMarkers(allEvents);
    }
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    initMap();
    await loadEvents();
    ["flt-event-type", "flt-state", "flt-severity", "flt-verification"].forEach((id) => {
      document.getElementById(id).addEventListener("change", applyFilters);
    });
    document.getElementById("toggle-heatmap").addEventListener("click", toggleHeatmap);
    IndraSocket.on((msg) => {
      if (["event.updated", "event.verified", "event.rejected"].includes(msg.type)) loadEvents();
    });
  }

  return { mount };
})();
