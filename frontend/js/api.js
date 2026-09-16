// Same-origin by default: works whether the backend serves this frontend
// directly (FRONTEND_DIST) or nginx proxies /api + /ws to the backend
// (Docker Compose) -- both put frontend and API on one origin. Set
// window.INDRA_API_BASE (e.g. in a <script> before this file) only if the
// frontend is opened standalone against a backend on a different origin.
const API_BASE = window.INDRA_API_BASE || "";

async function apiGet(path, params) {
  const url = new URL(API_BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Token": window.INDRA_ADMIN_TOKEN || "demo-admin-token" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

const Api = {
  health: () => apiGet("/api/health"),
  summary: () => apiGet("/api/analytics/summary"),
  eventDistribution: () => apiGet("/api/analytics/event-distribution"),
  reportsTrend: (days) => apiGet("/api/analytics/reports-trend", { days }),
  byState: () => apiGet("/api/analytics/by-state"),
  verificationRate: () => apiGet("/api/analytics/verification-rate"),
  sourceContribution: () => apiGet("/api/analytics/source-contribution"),

  events: (params) => apiGet("/api/events", params),
  event: (id) => apiGet(`/api/events/${id}`),
  eventEvidence: (id) => apiGet(`/api/events/${id}/evidence`),
  verifyEvent: (id, body) => apiPost(`/api/events/${id}/verify`, body),
  rejectEvent: (id, body) => apiPost(`/api/events/${id}/reject`, body),
  requestEvidence: (id, body) => apiPost(`/api/events/${id}/request-evidence`, body),
  escalateEvent: (id, body) => apiPost(`/api/events/${id}/escalate`, body),
  setSeverity: (id, body) => apiPost(`/api/events/${id}/severity`, body),

  reports: (params) => apiGet("/api/reports", params),
  report: (id) => apiGet(`/api/reports/${id}`),
  createReport: (body) => apiPost("/api/reports", body),
  uploadMedia: async (file, declaredCategory) => {
    const form = new FormData();
    form.append("file", file);
    const qs = declaredCategory ? `?declared_category=${encodeURIComponent(declaredCategory)}` : "";
    const res = await fetch(`${API_BASE}/api/media/upload${qs}`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`upload failed: ${res.status}`);
    return res.json();
  },
  markDuplicate: (id, body) => apiPost(`/api/reports/${id}/duplicate`, body),
  linkReportToEvent: (reportId, eventId) => apiPost(`/api/reports/${reportId}/link/${eventId}`, {}),

  alerts: (params) => apiGet("/api/alerts", params),
  acknowledgeAlert: (id) => apiPost(`/api/alerts/${id}/acknowledge`, {}),

  sources: () => apiGet("/api/sources"),
  datasets: () => apiGet("/api/datasets"),
  auditLogs: (limit) => apiGet("/api/audit-logs", { limit }),
  search: (q) => apiGet("/api/search", { q }),
  adminOverview: () => apiGet("/api/admin/overview"),

  demoStart: () => apiPost("/api/demo/start", {}),
  demoPause: () => apiPost("/api/demo/pause", {}),
  demoReset: () => apiPost("/api/demo/reset", {}),
  demoStatus: () => apiGet("/api/demo/status"),
};
