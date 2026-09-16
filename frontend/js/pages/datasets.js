const DatasetsPage = (() => {
  function render() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Datasets</h1>
          <p class="page-subtitle">Source datasets backing INDRA's analysis and demo scenarios</p>
        </div>
        <button class="btn btn-primary" id="load-demo-btn">Load Demo Dataset</button>
      </div>
      <div id="datasets-grid" style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px;"></div>
    `;
  }

  async function loadDatasets() {
    const data = await Api.datasets();
    const grid = document.getElementById("datasets-grid");
    grid.innerHTML = data.items.map((d) => `
      <div class="card dataset-card">
        <div class="dataset-title">${escapeHtml(d.name)}</div>
        <div style="font-size:12.5px; color:var(--ink-soft);">${escapeHtml(d.description)}</div>
        <div class="dataset-meta-row"><span>Source</span><b>${escapeHtml(d.source)}</b></div>
        <div class="dataset-meta-row"><span>Date range</span><b>${escapeHtml(d.date_range)}</b></div>
        <div class="dataset-meta-row"><span>Records</span><b>${d.record_count.toLocaleString()}</b></div>
        <div class="dataset-meta-row"><span>Coverage</span><b>${escapeHtml(d.geographic_coverage)}</b></div>
        <div class="dataset-meta-row"><span>Last updated</span><b>${timeAgo(d.last_updated)}</b></div>
        <div style="margin-top:4px;">${d.event_types.map((t) => `<span class="badge badge-low" style="margin-right:4px;">${escapeHtml(t)}</span>`).join("")}</div>
      </div>
    `).join("");
  }

  async function mount() {
    document.getElementById("page-container").innerHTML = render();
    await loadDatasets();
    document.getElementById("load-demo-btn").addEventListener("click", async () => {
      toast("Reloading demo dataset…");
      await Api.demoReset();
      toast("Demo dataset reloaded");
      loadDatasets();
    });
  }

  return { mount };
})();
