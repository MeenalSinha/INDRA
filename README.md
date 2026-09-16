# INDRA — Intelligent National Disaster & Weather Platform

**From fragmented weather reports to verified, actionable weather events.**

Team Sixth Sense · Smart India Hackathon 2026

For a full audit trail of what was actually tested (real bugs found and
fixed, live-executed golden scenario, performance measurements, honest
limitations) rather than a self-reported feature list, see
[`docs/INDRA_AUDIT.md`](docs/INDRA_AUDIT.md).

---

## 1. What this is

India receives weather information from many disconnected sources —
government/IMD feeds, weather APIs, social media, citizen reports, images,
news. INDRA fuses these fragmented, duplicated, noisy reports into a single
structured, confidence-scored **Weather Event** through an actual working
pipeline:

```
COLLECT → UNDERSTAND (AI classification, geo-clustering) → FUSE (event
fusion engine) → VERIFY (human-in-the-loop) → ACT (live command center,
alerts)
```

This is a **working, runnable prototype** — every screen is backed by a
real database, a real API, a real ML/fusion pipeline, and real WebSocket
updates. Nothing on the dashboard is hardcoded UI text; it all comes from
`GET` requests to the backend below.

**Confidence and accuracy figures shown in the demo (e.g. "94%") are
illustrative outputs of the fusion algorithm on demo data, not claimed
real-world benchmark accuracy.**

---

## 2. Quick start

### Option A — one command, no Docker (fastest way to see it running)

```bash
cd backend
pip install -r requirements.txt
FRONTEND_DIST=../frontend uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/** — the backend serves the frontend directly
and the API on the same origin. The database seeds itself automatically on
first run (SQLite file, no setup).

### Option B — Docker Compose (full target architecture)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API docs (Swagger/OpenAPI): http://localhost:8000/docs
- Postgres+PostGIS, Redis, Redpanda, MinIO are started alongside the
  backend so the full architecture is present and reachable. The backend
  runs in **Demo Mode** (SQLite + in-process streaming) by default even in
  Compose — see [Demo Mode vs Live Mode](#7-demo-mode-vs-live-mode) to
  point it at the real services instead.

### Running tests

```bash
cd backend
pytest tests/ -v
```

17 tests cover the classifier, duplicate detection, spatial clustering,
source reliability, severity engine, and the full API including the
fusion workflow end-to-end (`test_ingest_report_creates_event_via_fusion`).

---

## 3. Judge Mode

Open the **Admin Panel → Overview** tab (or call the API directly) and use
**Start Demo**. This drives the "Patna Flood" scenario through the exact
same `/api/reports` ingestion pipeline used by real reports — citizen
reports, social media, a weather observation, image evidence, and a burst
of corroborating reports all get classified, deduplicated, geo-clustered,
and fused live, ending in a CRITICAL, high-confidence event you can
verify from the Investigation screen. **Reset** wipes the database and
reseeds a clean baseline so the demo can be repeated for the next judge.

```
POST /api/demo/start   → begins the live scenario
POST /api/demo/pause   → pause / resume
POST /api/demo/reset   → clean-slate reseed
GET  /api/demo/status  → { running, paused, processed, total }
```

---

## 4. Project structure

```
indra/
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI app, routing, CORS, static serving
│   │   ├── config.py              All env-driven configuration
│   │   ├── database.py            SQLAlchemy engine/session
│   │   ├── models.py              Relational schema (reports, events, ...)
│   │   ├── schemas.py             Pydantic request/response models
│   │   ├── seed.py                Seeds 9 scenarios on first run
│   │   ├── ml/
│   │   │   ├── classifier.py      Weather event classification
│   │   │   ├── embeddings.py      TF-IDF semantic similarity
│   │   │   ├── duplicate.py       Duplicate/near-duplicate detection
│   │   │   ├── reliability.py     Source trust scoring
│   │   │   ├── anomaly.py         Isolation Forest + rule fallback
│   │   │   └── image.py           Image evidence analysis abstraction
│   │   ├── geo/
│   │   │   ├── utils.py           Haversine distance
│   │   │   └── clustering.py      DBSCAN spatial clustering
│   │   ├── fusion/
│   │   │   ├── engine.py          THE event fusion engine
│   │   │   └── severity.py        Explainable severity scoring
│   │   ├── verification/
│   │   │   └── service.py         Verify/reject/escalate + audit log
│   │   ├── ingestion/
│   │   │   └── adapters.py        Source adapters + the ingest_report() pipeline
│   │   ├── realtime/
│   │   │   ├── pubsub.py          In-process bus (Kafka/Redis stand-in)
│   │   │   └── manager.py         WebSocket fan-out
│   │   ├── demo/
│   │   │   ├── scenarios.py       9 seeded scenarios + Patna Flood timeline
│   │   │   └── simulator.py       Judge Mode controller
│   │   └── api/                   REST route modules
│   ├── tests/                     pytest suite (17 tests)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html                 App shell (sidebar, topbar, page mount point)
│   ├── css/styles.css             Design tokens + all styling
│   ├── js/
│   │   ├── api.js                 Fetch wrapper for every endpoint
│   │   ├── ws.js                  WebSocket client with reconnect backoff
│   │   ├── components.js          Badges, toasts, modal, formatting helpers
│   │   ├── app.js                 Router, global search, notifications
│   │   └── pages/                 dashboard, map, events, reports,
│   │                               investigation, analytics, alerts,
│   │                               datasets, admin
│   ├── Dockerfile
│   └── nginx.conf                 Serves static files, proxies /api + /ws
├── data/seed/                     (seed data lives in demo/scenarios.py;
│                                    this folder is for externally supplied
│                                    datasets loaded via the Datasets page)
├── docs/architecture.md           Mermaid diagrams, Demo vs Live Mode table
├── docs/INDRA_AUDIT.md            Full audit report: bugs found/fixed, test evidence, scores
├── docker-compose.yml             backend, frontend, postgres, redis,
│                                    redpanda, minio
├── .env.example
├── LICENSE
└── README.md
```

---

## 5. Tech stack

| Layer | Technology |
|---|---|
| Frontend | HTML/CSS/JS (no build step), Leaflet (map), Chart.js (charts), native WebSocket |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, WebSockets |
| Database | SQLite (Demo Mode) / PostgreSQL+PostGIS (Live Mode) |
| Cache / real-time state | In-process asyncio bus (Demo) / Redis (Live) |
| Streaming | Same in-process bus (Demo) / Redpanda or Kafka (Live) |
| Object storage | URL/category reference (Demo) / MinIO (Live) |
| AI/ML | scikit-learn (TF-IDF, DBSCAN, Isolation Forest), transparent lexicon classifier |
| Spatial | Haversine distance + DBSCAN (Demo) / PostGIS `ST_DWithin` (Live) |
| DevOps | Docker, Docker Compose |

We use a frontend without a Node/React build pipeline by deliberate
choice: it keeps "one command, no external dependencies" true for both the
combined-process quick start and the full Docker Compose stack, while
remaining a real SPA wired to live APIs and WebSockets — not a static
mockup.

---

## 6. Why event fusion is the core differentiator

A naive system would show every incoming report as its own pin on a map.
INDRA instead runs each report through:

1. **Classification** — lexicon + scoring classifier (`ml/classifier.py`)
   assigns an event type and confidence, explainable down to which terms
   matched.
2. **Duplicate detection** — TF-IDF cosine similarity + haversine distance
   + time window (`ml/duplicate.py`) flags near-duplicates without ever
   deleting the original report.
3. **Geo-spatial clustering** — DBSCAN (`geo/clustering.py`) groups nearby
   reports of the same type into spatial clusters.
4. **Fusion** — `fusion/engine.py` combines semantic similarity, geo
   proximity, time proximity, weather agreement, source reliability, and
   independent evidence into one itemized confidence score and creates or
   updates a single `Event` row.
5. **Severity** — `fusion/severity.py` produces LOW/MODERATE/HIGH/CRITICAL
   with a human-readable list of *why* ("127 reports received", "Weather
   observation confirms anomaly vs local baseline").
6. **Verification** — an admin reviews the evidence panel and
   verifies/rejects/escalates; every action is written to
   `VerificationAction` and `AuditLog`.

Every one of the above is real, tested code — see
`backend/tests/test_ml_pipeline.py` and
`backend/tests/test_api.py::test_ingest_report_creates_event_via_fusion`.

---

## 7. Demo Mode vs Live Mode

See [`docs/architecture.md`](docs/architecture.md) for the full table and
diagrams. In short: everything defaults to a fully local, credential-free
Demo Mode (SQLite + in-process streaming + local scikit-learn models).
Setting `DATABASE_URL`, `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, and
`MINIO_*` env vars (see `.env.example`) switches the backend to the real
Postgres+PostGIS / Redis / Redpanda / MinIO services in
`docker-compose.yml` without any code changes to the API or frontend.

---

## 8. API reference

Full interactive docs are auto-generated by FastAPI at **`/docs`**
(Swagger UI) and **`/redoc`** once the backend is running. Key endpoints:

```
GET  /api/health                        System status for all subsystems
GET  /api/events                        List events (filterable incl. date_from/date_to)
GET  /api/events/nearby                 Radius search (lat, lng, radius_km)
GET  /api/events/bbox                   Bounding-box search
GET  /api/events/{id}                   Event detail incl. fusion breakdown
GET  /api/events/{id}/evidence          Evidence panel data
POST /api/events/{id}/verify            Verify an event            [admin]
POST /api/events/{id}/reject            Reject an event            [admin]
POST /api/events/{id}/request-evidence  Request more evidence      [admin]
POST /api/events/{id}/escalate          Escalate severity          [admin]
POST /api/events/{id}/severity          Set severity directly      [admin]
GET  /api/reports                       List reports (filterable incl. date_from/date_to)
POST /api/reports                       Ingest a new report (runs the full pipeline)
POST /api/reports/{id}/duplicate        Mark a report as a duplicate [admin]
POST /api/media/upload                  Upload image/video evidence (validated)
GET  /api/analytics/summary             Dashboard metric cards
GET  /api/analytics/event-distribution  Donut chart data
GET  /api/analytics/reports-trend       Trend line data
GET  /api/alerts                        Active alerts
POST /api/alerts/{id}/acknowledge       Acknowledge an alert        [admin]
GET  /api/sources                       Source reliability dashboard
GET  /api/datasets                      Dataset catalogue
GET  /api/audit-logs                    Full audit trail
GET  /api/search?q=                     Global search
POST /api/demo/start | pause | reset    Judge Mode controls
WS   /ws/events                         Live event stream
```

`[admin]` routes go through the `require_admin` dependency
(`security/auth.py`). Enforcement is off by default (`REQUIRE_ADMIN_TOKEN=false`)
so Judge Mode needs no setup; the frontend already sends `X-Admin-Token` on
every admin action, so flipping the env var to `true` works with no
frontend change. The API also carries a basic in-memory rate limiter
(`RATE_LIMIT_PER_MINUTE`, default 300/min per client) on all `/api/*` routes.

---

## 9. Security notes

- No secrets are committed; `ADMIN_TOKEN` and all service credentials are
  environment variables (`.env.example`).
- CORS origins are configurable via `CORS_ORIGINS`.
- Input is validated at the Pydantic schema layer; malformed reports
  (missing GPS, missing timestamp) are normalized rather than crashing the
  pipeline (`ingestion/adapters.py::normalize_payload`).
- Admin authentication is abstracted behind `ADMIN_TOKEN` so a real
  identity provider can be dropped in for production without touching the
  verification workflow.

---

## 10. Future scope

- Swap the four Demo Mode ML functions for production models behind their
  existing signatures (see `docs/architecture.md` table).
- Real adapters for IMD/government APIs, social platform APIs, and SMS
  gateways behind the existing `ingestion/adapters.py` adapter classes.
- SMS/email alert delivery (the alert engine already emits structured
  alerts; only the delivery channel is new).
- Role-based admin authentication in place of the current token
  abstraction.
- Move event reclustering off the synchronous request path (background
  worker + debounced re-fusion) if bulk historical dataset import becomes
  a real requirement — see Limitations below.

## 11. Limitations

Found and documented via a full audit (`docs/INDRA_AUDIT.md`) rather than
assumed:

- **No PostgreSQL/PostGIS/Redis/Kafka instance has been integration-tested
  against this codebase.** The Demo Mode substitutes (SQLite + Python
  haversine + in-process pub/sub) are real, working, tested code — not
  stubs — but the Live Mode env-var swap path itself has not been run
  against live instances of those services.
- **Docker Compose has not been run end-to-end** in the environment this
  was built in (no Docker daemon available there). The compose file and
  both Dockerfiles are reviewed for correctness but not execution-verified.
  If you hit an issue running `docker compose up --build`, please file it.
- **Demo Mode's event clustering re-runs on every single insert** and
  does not scale gracefully past a few thousand same-event-type reports
  ingested via sequential individual API calls (measured: ~17ms/report at
  100 reports, growing to ~140-220ms/report at ~4,000 concentrated
  reports). Judge Mode (125 reports) and normal interactive use are
  unaffected — this only matters for bulk historical dataset import,
  which is a Live Mode concern (see Future Scope above).
- **Source adapters are schema/pipeline adapters, not live external API
  pollers** — by design, so the core demo needs no external credentials.
  Real IMD/social API integration is future scope, not present today.
- **No explicit database indexes** beyond primary/foreign keys; not yet a
  measured bottleneck at current data volumes (the real bottleneck is the
  clustering cost above, not query planning).
