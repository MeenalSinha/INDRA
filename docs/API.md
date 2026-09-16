# INDRA — API Reference

Auto-generated interactive docs are always the source of truth: **`/docs`**
(Swagger UI) and **`/redoc`** once the backend is running. This file is a
human-readable index with notes on auth and mode-dependent behavior that
the OpenAPI schema alone doesn't convey.

## Auth model

Two independent, both-off-by-default layers (see `security/auth.py` and
`security/jwt_auth.py`):

- **`X-Admin-Token` header** (`REQUIRE_ADMIN_TOKEN=true`) — single shared
  token, simplest possible gate.
- **JWT bearer token with roles** (`REQUIRE_JWT_AUTH=true`) — `POST
  /api/auth/login` with a demo account (see `.env.example`) returns a
  token; admin-action routes require `Depends(require_role("ADMIN"))`.
  ANALYST and VIEWER roles exist and are enforced by the same rank
  comparison; only ADMIN currently gates any route (matching "ADMIN can
  verify/reject/escalate; ANALYST can investigate; VIEWER is read-only" —
  investigation and read endpoints have no role gate at all, which *is*
  ANALYST/VIEWER access).

Both were live-tested together in the upgrade audit: no token → 401,
VIEWER token → 403, ADMIN token → 200, on the same endpoint.

## Endpoints

```
GET  /api/health                        System status: api/db/cache/streaming/ai/websocket,
                                         reports_per_min, events_per_min, avg_processing_latency_ms,
                                         stream_queue_depth
GET  /api/events                        List (event_type, state, city, severity, verification_status,
                                         q, date_from, date_to, limit, offset)
GET  /api/events/nearby                 Radius search (lat, lng, radius_km) -- real ST_DWithin in
                                         Live Mode, haversine in Demo Mode
GET  /api/events/bbox                   Bounding-box search
GET  /api/events/{id}                   Detail incl. fusion_breakdown, timeline, report_ids
GET  /api/events/{id}/evidence          Evidence panel counts
POST /api/events/{id}/verify            [admin] -> VERIFIED
POST /api/events/{id}/reject            [admin] -> REJECTED
POST /api/events/{id}/request-evidence  [admin] -> UNDER_REVIEW
POST /api/events/{id}/escalate          [admin] bump severity one level
POST /api/events/{id}/severity          [admin] set severity directly

GET  /api/reports                       List (event_type, state, city, source_type, duplicate_status,
                                         verification_status, q, date_from, date_to, limit, offset)
GET  /api/reports/{id}                  Detail incl. media
POST /api/reports                       Ingest -- runs the full pipeline synchronously
POST /api/reports/{id}/duplicate        [admin] mark as duplicate
POST /api/reports/{id}/link/{event_id}  Manually link a report to an event

POST /api/media/upload                  Real file upload (content-type/size/empty validated)

GET  /api/analytics/summary             Dashboard metric cards
GET  /api/analytics/event-distribution  Donut chart data
GET  /api/analytics/reports-trend       Trend line data (days param)
GET  /api/analytics/by-state
GET  /api/analytics/verification-rate
GET  /api/analytics/source-contribution

GET  /api/alerts                        (level, acknowledged filters)
POST /api/alerts/{id}/acknowledge       [admin]

GET  /api/sources                       Source reliability dashboard
GET  /api/datasets
GET  /api/audit-logs
GET  /api/search?q=
GET  /api/admin/overview

POST /api/auth/login                    {username, password} -> {access_token, role}
GET  /api/auth/demo-credentials         Lists the demo account usernames/roles (not passwords)

POST /api/demo/start | pause | reset    Judge Mode controls
GET  /api/demo/status

WS   /ws/events                         Live event stream (report.received, report.classified,
                                         duplicates.detected, event.updated, event.verified,
                                         event.rejected, alert.created, demo.stage, demo.reset)
```

## Response format

Consistent shapes: list endpoints return `{"total": int, "items": [...]}`;
detail endpoints return the object directly; errors return FastAPI's
standard `{"detail": "..."}` with the appropriate status code (404 for
missing resources, 401/403 for auth failures, 429 for rate limiting, 415/
413/400 for upload validation failures — all live-tested, not assumed).
