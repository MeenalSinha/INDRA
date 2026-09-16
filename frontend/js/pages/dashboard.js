const Dashboard = (() => {
  let map = null;
  let markersLayer = null;
  let donutChart = null;
  let trendChart = null;
  let liveFeedItems = [];

  function iconSvg(name) {
    const icons = {
      reports: '<path d="M12 3v13M12 16l-4-4M12 16l4-4M4 21h16" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
      shield: '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
      alert: '<path d="M12 3 2 20h20L12 3Z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M12 10v4M12 17h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
      users: '<circle cx="9" cy="8" r="3.2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 9a3 3 0 1 0 0-6M22 20c0-2.8-1.9-5.1-4.5-5.8" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/>',
    };
    return icons[name] || "";
  }

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Welcome to INDRA</h1>
          <p class="page-subtitle">Real-time insights. Verified information. A safer India.</p>
        </div>
        <div class="page-header-right">
          <div class="system-status">
            <span class="status-dot"></span>
            System Online
            <span class="status-sub">All services operational</span>
          </div>
          <div class="datetime-chip" id="header-datetime">${formatDateTime(new Date())}</div>
        </div>
      </div>

      <div class="metric-grid" id="metric-grid">
        ${["reports","shield","alert","users"].map(() => `
          <div class="card metric-card"><div class="skeleton" style="width:42px;height:42px;border-radius:10px;"></div>
          <div style="flex:1"><div class="skeleton" style="width:70px;height:18px;margin-bottom:6px;"></div><div class="skeleton" style="width:100px;height:12px;"></div></div></div>
        `).join("")}
      </div>

      <div class="dashboard-grid">
        <div class="card map-card">
          <div class="section-header">
            <div>
              <h2 class="section-title">Live Weather Events — India</h2>
              <p class="section-subtitle">Real-time view of verified and emerging weather events</p>
            </div>
            <select class="map-select" id="dashboard-map-range">
              <option>Last 24 hours</option>
              <option>Last 7 days</option>
              <option>All time</option>
            </select>
          </div>
          <div style="position:relative;">
            <div id="dashboard-map" class="map-canvas"></div>
            <div class="map-legend" style="position:absolute; top:14px; right:14px; z-index:400;">
              ${["Urban Flooding","Heavy Rainfall","Thunderstorm","Strong Winds","Fog"].map(t => `
                <div class="legend-row"><span class="legend-dot" style="background:${eventColor(t)}"></span>${t}</div>
              `).join("")}
              <button class="view-all" data-nav="events">View all events →</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="section-header" style="padding:20px 22px 10px;">
            <div>
              <h2 class="section-title">Recent Weather Events</h2>
            </div>
            <button class="section-link" data-nav="events">View All →</button>
          </div>
          <div id="recent-events-list"></div>
        </div>
      </div>

      <div class="dashboard-bottom-grid">
        <div class="card chart-card">
          <h2 class="section-title">Event Distribution</h2>
          <div class="donut-wrap">
            <div class="donut-canvas-wrap">
              <canvas id="event-donut"></canvas>
              <div class="donut-center">
                <div class="donut-center-value" id="donut-total">0</div>
                <div class="donut-center-label">Events</div>
              </div>
            </div>
            <div class="legend-list" id="donut-legend"></div>
          </div>
        </div>

        <div class="card chart-card">
          <div class="section-header">
            <h2 class="section-title">Reports Trend</h2>
            <select class="map-select" id="trend-range"><option value="7">Last 7 days</option><option value="14">Last 14 days</option></select>
          </div>
          <div class="chart-canvas-wrap"><canvas id="trend-chart"></canvas></div>
        </div>

        <div class="card">
          <div class="section-header" style="padding:18px 20px 8px;">
            <h2 class="section-title">Live Reports Feed</h2>
            <button class="section-link" data-nav="reports">View All →</button>
          </div>
          <div id="live-feed-list" style="max-height:260px; overflow-y:auto;"></div>
        </div>
      </div>
    `;
  }

  function renderMetricCard(icon, colorClass, value, label, changePct, changeLabel) {
    const up = changePct >= 0;
    return `
      <div class="card metric-card">
        <div class="metric-icon ${colorClass}"><svg width="20" height="20" viewBox="0 0 24 24">${iconSvg(icon)}</svg></div>
        <div>
          <div class="metric-value">${value}</div>
          <div class="metric-label">${label}</div>
        </div>
        <div class="metric-trend-row">
          <div class="metric-trend ${up ? "up" : "down"}">${up ? "↑" : "↓"} ${Math.abs(changePct).toFixed(0)}%</div>
          <div class="metric-trend-sub">${changeLabel}</div>
        </div>
      </div>`;
  }

  async function loadMetrics() {
    const s = await Api.summary();
    const grid = document.getElementById("metric-grid");
    if (!grid) return;
    grid.innerHTML =
      renderMetricCard("reports", "blue", s.total_reports.toLocaleString(), "Total Reports", s.total_reports_change_pct, "last 24h") +
      renderMetricCard("shield", "teal", s.verified_events.toLocaleString(), "Verified Events", s.verified_events_change_pct, "last 24h") +
      renderMetricCard("alert", "red", s.critical_events.toLocaleString(), "Critical Events", s.critical_events_change, "last 24h") +
      renderMetricCard("users", "purple", s.citizen_reports.toLocaleString(), "Citizen Reports", s.citizen_reports_change_pct, "last 24h");
  }

  function initMap() {
    if (map) { map.remove(); }
    map = L.map("dashboard-map", { zoomControl: true, attributionControl: false }).setView([22.5, 80], 4.4);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", { maxZoom: 18 }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
  }

  async function loadMapEvents() {
    const data = await Api.events({ limit: 60 });
    markersLayer.clearLayers();
    data.items.forEach((e) => {
      if (e.latitude == null || e.longitude == null) return;
      const color = eventColor(e.event_type);
      const radius = e.severity === "CRITICAL" ? 10 : e.severity === "HIGH" ? 8 : e.severity === "MODERATE" ? 6.5 : 5.5;
      const marker = L.circleMarker([e.latitude, e.longitude], {
        radius, color: "#fff", weight: 1.5, fillColor: color, fillOpacity: 0.9,
      }).addTo(markersLayer);
      marker.bindPopup(`<b>${escapeHtml(e.title)}</b><br>${escapeHtml(e.severity)} · ${confidencePct(e.confidence)}% confidence<br>${e.report_count} reports`);
      marker.on("click", () => window.IndraApp.openInvestigation(e.id));
    });
  }

  async function loadRecentEvents() {
    const data = await Api.events({ limit: 5 });
    const list = document.getElementById("recent-events-list");
    if (!list) return;
    if (!data.items.length) { list.innerHTML = `<div class="empty-state">No events yet.</div>`; return; }
    list.innerHTML = data.items.map((e) => `
      <div class="event-row" data-event-id="${e.id}">
        <div class="event-thumb" style="background:${thumbGradient(e.event_type)}"></div>
        <div class="event-row-body">
          <div class="event-row-top">
            <div class="event-row-title">${escapeHtml(e.city || "Unknown")}, ${escapeHtml(e.state || "")}</div>
          </div>
          <div class="event-row-type">${escapeHtml(e.event_type)}</div>
          <div style="display:flex; align-items:center; gap:6px; margin-top:6px;">
            ${severityBadge(e.severity)} ${statusBadge(e.verification_status)}
          </div>
          <div class="event-row-time">${timeAgo(e.last_updated)}</div>
        </div>
      </div>
    `).join("");
    list.querySelectorAll(".event-row").forEach((row) => {
      row.addEventListener("click", () => window.IndraApp.openInvestigation(row.dataset.eventId));
    });
  }

  async function loadDonut() {
    const data = await Api.eventDistribution();
    const items = data.items.filter((i) => i.event_type).sort((a, b) => b.count - a.count);
    const total = items.reduce((a, b) => a + b.count, 0);
    document.getElementById("donut-total").textContent = total;
    const legend = document.getElementById("donut-legend");
    legend.innerHTML = items.map((i) => `
      <div class="legend-list-row">
        <span class="legend-dot" style="background:${eventColor(i.event_type)}"></span>
        <span class="lbl">${escapeHtml(i.event_type)}</span>
        <span class="val">${i.count}</span>
      </div>`).join("");

    if (donutChart) donutChart.destroy();
    const ctx = document.getElementById("event-donut");
    donutChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: items.map((i) => i.event_type),
        datasets: [{ data: items.map((i) => i.count), backgroundColor: items.map((i) => eventColor(i.event_type)), borderWidth: 2, borderColor: "#fff" }],
      },
      options: { cutout: "72%", plugins: { legend: { display: false }, tooltip: { enabled: true } } },
    });
  }

  async function loadTrend(days) {
    const data = await Api.reportsTrend(days || 7);
    if (trendChart) trendChart.destroy();
    const ctx = document.getElementById("trend-chart");
    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.items.map((i) => i.date),
        datasets: [{
          data: data.items.map((i) => i.count), borderColor: "#2f6fd6", backgroundColor: "rgba(47,111,214,0.08)",
          fill: true, tension: 0.35, pointRadius: 3, pointBackgroundColor: "#2f6fd6",
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, grid: { color: "#edf0f5" } }, x: { grid: { display: false } } },
      },
    });
  }

  function feedIcon(sourceType) {
    if (sourceType === "citizen" || sourceType === "citizen_verified") return "C";
    if (sourceType === "social") return "S";
    if (sourceType === "weather_api" || sourceType === "government") return "W";
    return "N";
  }

  function pushFeedItem(item) {
    liveFeedItems.unshift(item);
    liveFeedItems = liveFeedItems.slice(0, 25);
    renderFeed();
  }

  function renderFeed() {
    const list = document.getElementById("live-feed-list");
    if (!list) return;
    if (!liveFeedItems.length) { list.innerHTML = `<div class="empty-state">Waiting for live activity…</div>`; return; }
    list.innerHTML = liveFeedItems.map((f) => `
      <div class="feed-item">
        <div class="feed-icon ${sourceIconClass(f.source_type)}">${feedIcon(f.source_type)}</div>
        <div class="feed-body">
          <span class="feed-source">${escapeHtml(f.source)}</span><span class="feed-time">${f.time}</span>
          <div class="feed-text">${escapeHtml(f.text)}</div>
        </div>
      </div>`).join("");
  }

  async function loadInitialFeed() {
    const data = await Api.reports({ limit: 6 });
    liveFeedItems = data.items.map((r) => ({
      source: r.source, source_type: r.source_type, text: r.text || "(no text)",
      time: new Date(r.timestamp + "Z").toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
    }));
    renderFeed();
  }

  function onSocketMessage(msg) {
    if (msg.type === "report.received") {
      pushFeedItem({
        source: msg.payload.source, source_type: msg.payload.source_type, text: msg.payload.text || "(no text)",
        time: new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
      });
    }
    if (["event.updated", "event.verified", "event.rejected"].includes(msg.type)) {
      loadMetrics(); loadRecentEvents(); loadMapEvents(); loadDonut();
    }
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    document.querySelectorAll("[data-nav]").forEach((el) => el.addEventListener("click", () => window.IndraApp.navigate(el.dataset.nav)));
    initMap();
    await Promise.all([loadMetrics(), loadMapEvents(), loadRecentEvents(), loadDonut(), loadTrend(7), loadInitialFeed()]);
    document.getElementById("trend-range").addEventListener("change", (e) => loadTrend(Number(e.target.value)));
    IndraSocket.on(onSocketMessage);
  }

  return { mount };
})();
