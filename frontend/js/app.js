const PAGES = {
  dashboard: Dashboard,
  map: MapPage,
  events: EventsPage,
  reports: ReportsPage,
  analytics: AnalyticsPage,
  alerts: AlertsPage,
  datasets: DatasetsPage,
  admin: AdminPage,
};

let currentPage = "dashboard";
let unackCount = 0;

async function navigate(page) {
  if (!PAGES[page]) return;
  currentPage = page;
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.page === page));
  await PAGES[page].mount();
}

function refreshCurrentPage() {
  PAGES[currentPage].mount();
}

function openInvestigation(eventId) {
  Investigation.open(eventId);
}

function setupSidebarNav() {
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.page));
  });
}

function setupSearch() {
  const input = document.getElementById("global-search");
  const results = document.getElementById("search-results");
  let debounce;

  input.addEventListener("input", () => {
    clearTimeout(debounce);
    const q = input.value.trim();
    if (!q) { results.classList.add("hidden"); return; }
    debounce = setTimeout(async () => {
      const data = await Api.search(q);
      const groups = [];
      if (data.events.length) groups.push(`<div class="sr-group-title">Events</div>` + data.events.map((e) => `<div class="sr-item" data-type="event" data-id="${e.id}"><b>${escapeHtml(e.title)}</b> — ${escapeHtml(e.event_code)}</div>`).join(""));
      if (data.reports.length) groups.push(`<div class="sr-group-title">Reports</div>` + data.reports.map((r) => `<div class="sr-item" data-type="report" data-id="${r.id}">${escapeHtml((r.text || "").slice(0, 70) || "(no text)")}</div>`).join(""));
      if (data.sources.length) groups.push(`<div class="sr-group-title">Sources</div>` + data.sources.map((s) => `<div class="sr-item">${escapeHtml(s.name)}</div>`).join(""));
      results.innerHTML = groups.length ? groups.join("") : `<div class="sr-empty">No matches for "${escapeHtml(q)}"</div>`;
      results.classList.remove("hidden");
      results.querySelectorAll('[data-type="event"]').forEach((el) => el.addEventListener("click", () => {
        results.classList.add("hidden"); input.value = ""; openInvestigation(el.dataset.id);
      }));
    }, 250);
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) results.classList.add("hidden");
  });
}

async function refreshNotifDot() {
  const data = await Api.alerts({ acknowledged: false });
  unackCount = data.items.length;
  document.getElementById("notif-dot").classList.toggle("hidden", unackCount === 0);
}

function setupNotifBell() {
  document.getElementById("notif-btn").addEventListener("click", () => navigate("alerts"));
}

function setupGlobalSocketHandlers() {
  IndraSocket.on((msg) => {
    if (msg.type === "alert.created") {
      toast(`Critical alert: ${msg.payload.title}`);
      refreshNotifDot();
    }
    if (msg.type === "demo.stage") {
      toast(msg.payload.label);
    }
  });
}

window.IndraApp = { navigate, openInvestigation, refreshCurrentPage };

document.addEventListener("DOMContentLoaded", async () => {
  setupSidebarNav();
  setupSearch();
  setupNotifBell();
  setupGlobalSocketHandlers();
  refreshNotifDot();
  setInterval(refreshNotifDot, 20000);
  await navigate("dashboard");
});
