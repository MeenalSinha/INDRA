# INDRA — Pre-Upgrade Baseline

Recorded before any upgrade work in this pass, per the upgrade prompt's
own requirement to understand the system before changing it. This
reflects the state of the repository as delivered after the previous
audit round (`docs/INDRA_AUDIT.md`).

## Current architecture

- **Backend:** FastAPI, single process, SQLAlchemy ORM.
- **Database:** SQLite (`indra_demo.db`), plain float lat/lng columns, no
  PostGIS, no spatial indexes, no formal migrations
  (`Base.metadata.create_all()` + a hand-rolled `ensure_schema()` that
  `ALTER TABLE ADD COLUMN`s anything missing).
- **Streaming/cache:** in-process `asyncio.Queue`-based pub/sub
  (`realtime/pubsub.py`), fanned out to WebSocket clients. No Redis, no
  Kafka/Redpanda.
- **Object storage:** local disk (`storage.py`), no MinIO.
- **Auth:** single shared `ADMIN_TOKEN` via `X-Admin-Token` header,
  enforcement toggleable, no roles, no login flow.
- **Frontend:** hand-written HTML/CSS/vanilla JS SPA (no build step),
  Leaflet for maps, Chart.js for charts, native WebSocket client with
  reconnect backoff. Matches the approved visual direction.
- **Rate limiting:** in-memory per-IP sliding window.

## Current features (all verified working as of the last audit)

Multi-source ingestion, data processing/normalization, weather event
classification (lexicon-based), duplicate detection (TF-IDF + haversine +
time window), source reliability scoring, anomaly detection (Isolation
Forest + rule fallback), geospatial clustering (DBSCAN, haversine metric),
event fusion engine (6-factor weighted confidence), severity engine
(explainable reasons), verification workflow (5 states + audit log),
alerts, analytics, Live Map, Reports/Events pages, Event Investigation
screen, Admin Panel, WebSocket live updates, Demo Mode, Judge Mode
(Patna Flood scenario), demo reset, auto-generated OpenAPI docs at `/docs`.

## Current tests (baseline run, this session)

```
$ cd backend && python -m pytest tests/ -q
31 passed, 658 warnings in 2.30s
```

31 tests across `test_api.py`, `test_ml_pipeline.py`, `test_new_features.py`.

## Current known limitations (from the last audit)

- No PostgreSQL/PostGIS/Redis/Kafka instance had been integration-tested
  (none was available in that session).
- Docker Compose had not been run end-to-end (no Docker daemon).
- Demo Mode re-runs full DBSCAN clustering over all same-type reports
  within a rolling 12-hour window on every single insert — measured
  ~10x per-request latency growth (17ms → 140-220ms) between 100 and
  ~4,000 concentrated same-type reports. Judge Mode (125 reports) and
  normal interactive use are unaffected.
- Source adapters are pipeline adapters, not live external API pollers
  (by design — no external credentials required for the core demo).
- No explicit database indexes beyond primary/foreign keys.
- Single-token admin auth, no roles, no login UI.

## Current startup procedure

```bash
cd backend && pip install -r requirements.txt
FRONTEND_DIST=../frontend uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Seeds itself automatically on first run against a local SQLite file.

## Current Demo Mode / Judge Mode behavior

Demo Mode is the default and only mode exercised previously (SQLite +
in-process bus). Judge Mode (`POST /api/demo/start|pause|reset`) drives
the Patna Flood scenario through the real `ingest_report()` pipeline —
confirmed in the last audit to correctly produce a fresh CRITICAL event,
distinct from the pre-seeded historical Patna example, that a human admin
can genuinely verify.

## Environment check performed before starting this upgrade

- `docker --version` → not available in this sandbox (unchanged from
  last audit).
- `apt-get install postgresql postgresql-contrib postgis
  postgresql-16-postgis-3 redis-server` → **succeeded**. This is new
  information relative to the last audit, which assumed no such
  infrastructure was reachable — it was simply never attempted via apt
  before. This baseline document exists specifically to record that this
  upgrade pass is starting from a position where real Postgres+PostGIS
  and real Redis are actually available to build and test against, which
  materially changes what "implemented" can honestly mean for this round.
- Kafka/Redpanda and MinIO remain **not installable** in this sandbox:
  neither ships as an Ubuntu apt package, and their upstream binary
  distributions are not on the network allowlist available to this
  environment (only apt mirrors, PyPI, npm, and GitHub release assets/
  crates.io are reachable). These remain genuinely deferred, not
  attempted-and-hidden.
