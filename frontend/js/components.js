function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function severityBadge(severity) {
  const cls = "badge-" + (severity || "low").toLowerCase();
  return `<span class="badge ${cls}">${escapeHtml(severity)}</span>`;
}

function statusBadge(status) {
  const cls = "badge-" + (status || "unverified").toLowerCase();
  const label = (status || "UNVERIFIED").replace(/_/g, " ");
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function duplicateBadge(status) {
  const cls = "badge-" + (status || "unique").toLowerCase();
  const label = (status || "UNIQUE").replace(/_/g, " ");
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function timeAgo(isoString) {
  if (!isoString) return "";
  const then = new Date(isoString + (isoString.endsWith("Z") ? "" : "Z"));
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function formatDateTime(d) {
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }) + " IST";
}

const EVENT_TYPE_COLORS = {
  "Urban Flooding": "#2563eb",
  "Heavy Rainfall": "#2f6fd6",
  "Thunderstorm": "#7c5cd6",
  "Lightning": "#8a5cd6",
  "Heatwave": "#d6392f",
  "Fog": "#64748b",
  "Dust Storm": "#c9820a",
  "Strong Winds": "#0e9488",
  "Hailstorm": "#2f9fd6",
  "Cyclone": "#b91c5c",
  "Other": "#94a3b8",
};

function eventColor(type) {
  return EVENT_TYPE_COLORS[type] || "#94a3b8";
}

function thumbGradient(type) {
  const c = eventColor(type);
  return `linear-gradient(135deg, ${c}33, ${c}88)`;
}

function sourceIconClass(sourceType) {
  if (sourceType === "citizen" || sourceType === "citizen_verified") return "citizen";
  if (sourceType === "social") return "social";
  if (sourceType === "weather_api" || sourceType === "government") return "weather_api";
  return "news";
}

function toast(message) {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function openModal(innerHtml) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-overlay" id="modal-overlay">
      <div class="modal-panel" style="position:relative;">
        <button class="modal-close" id="modal-close-btn">
          <svg width="15" height="15" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
        ${innerHtml}
      </div>
    </div>`;
  document.getElementById("modal-close-btn").onclick = closeModal;
  document.getElementById("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") closeModal();
  });
}

function closeModal() {
  document.getElementById("modal-root").innerHTML = "";
}

function confidencePct(c) {
  return Math.round((c || 0) * 100);
}
