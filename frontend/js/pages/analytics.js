const AnalyticsPage = (() => {
  let charts = [];

  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Analytics</h1>
          <p class="page-subtitle">Aggregate patterns across events, reports and sources</p>
        </div>
      </div>

      <div class="metric-grid" id="analytics-metrics"></div>

      <div class="dashboard-bottom-grid" style="margin-bottom:18px;">
        <div class="card chart-card">
          <h2 class="section-title">Events by State</h2>
          <div class="chart-canvas-wrap"><canvas id="chart-by-state"></canvas></div>
        </div>
        <div class="card chart-card">
          <h2 class="section-title">Events by Type</h2>
          <div class="chart-canvas-wrap"><canvas id="chart-by-type"></canvas></div>
        </div>
        <div class="card chart-card">
          <h2 class="section-title">Source Contribution</h2>
          <div class="chart-canvas-wrap"><canvas id="chart-by-source"></canvas></div>
        </div>
      </div>

      <div class="card chart-card">
        <h2 class="section-title">Reports Over Time (14 days)</h2>
        <div class="chart-canvas-wrap"><canvas id="chart-reports-trend"></canvas></div>
      </div>
    `;
  }

  function destroyCharts() { charts.forEach((c) => c.destroy()); charts = []; }

  function bar(id, labels, data, color, horizontal) {
    const c = new Chart(document.getElementById(id), {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: color, borderRadius: 5, maxBarThickness: 28 }] },
      options: {
        indexAxis: horizontal ? "y" : "x",
        plugins: { legend: { display: false } },
        scales: { x: { grid: { color: "#edf0f5" } }, y: { grid: { display: false } } },
      },
    });
    charts.push(c);
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    destroyCharts();

    const [rate, byState, dist, source, trend] = await Promise.all([
      Api.verificationRate(), Api.byState(), Api.eventDistribution(), Api.sourceContribution(), Api.reportsTrend(14),
    ]);

    document.getElementById("analytics-metrics").innerHTML = `
      <div class="card metric-card"><div><div class="metric-value">${rate.verification_rate_pct}%</div><div class="metric-label">Verification Rate</div></div></div>
      <div class="card metric-card"><div><div class="metric-value">${rate.average_confidence}%</div><div class="metric-label">Average Confidence</div></div></div>
      <div class="card metric-card"><div><div class="metric-value">${rate.duplicate_rate_pct}%</div><div class="metric-label">Duplicate Rate</div></div></div>
      <div class="card metric-card"><div><div class="metric-value">${rate.total}</div><div class="metric-label">Total Events Tracked</div></div></div>
    `;

    bar("chart-by-state", byState.items.map((i) => i.state), byState.items.map((i) => i.count), "#2f6fd6", true);
    bar("chart-by-type", dist.items.map((i) => i.event_type), dist.items.map((i) => i.count), dist.items.map((i) => eventColor(i.event_type)));
    bar("chart-by-source", source.items.map((i) => i.source_type), source.items.map((i) => i.count), "#0e9488");

    const c = new Chart(document.getElementById("chart-reports-trend"), {
      type: "line",
      data: { labels: trend.items.map((i) => i.date), datasets: [{ data: trend.items.map((i) => i.count), borderColor: "#2f6fd6", backgroundColor: "rgba(47,111,214,0.08)", fill: true, tension: 0.35 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#edf0f5" } }, x: { grid: { display: false } } } },
    });
    charts.push(c);
  }

  return { mount };
})();
