# INDRA FINAL AUDIT BASELINE

## Repository Structure
- `backend/`: FastAPI Python backend (SQLite/PostgreSQL compatible, Redpanda/Kafka & MinIO integrations).
- `frontend/`: React + Vite frontend (dashboard, map, event investigation).
- `docker/`: Dockerfiles for backend/frontend and Redpanda configurations.
- `docs/`: Audits, limitations, setup docs.
- `docker-compose.yml`: Infrastructure orchestration (Redpanda, MinIO, Backend, Frontend).

## Current Architecture
- **Backend:** FastAPI, SQLAlchemy (SQLite by default, Postgres for prod), SentenceTransformers (default TF-IDF with optional `ML_BACKEND=transformers`), HTTPX (external polling), smtplib (email alerts).
- **Frontend:** React, React Router, TailwindCSS, Mapbox/Leaflet (via react-leaflet).
- **Infrastructure:** `docker-compose.yml` provides Redpanda (streaming) and MinIO (object storage).
- **Modes:** "Demo Mode" (in-process event bus and local disk storage) vs "Live Mode" (Kafka + MinIO).

## Current Startup Commands
- Backend local: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend local: `cd frontend && npm run dev`
- Full compose: `docker compose up --build`

## Current Services
- `indra_backend`: FastAPI app
- `indra_frontend`: React/Vite server
- `indra_redpanda`: Kafka-compatible streaming engine
- `indra_minio`: S3-compatible object storage

## Current Tests
- Backend tests exist in `backend/tests/`:
  - `test_api.py` (API flows, Demo mode, alerts, fusion)
  - `test_ml_pipeline.py` (Clustering and feature extraction)
  - `test_new_features.py` (Verification workflows, RBAC)
  - `test_users_and_email.py` (User DB, passwords, email alerts)

## Current Test Result
- Passed: 45
- Failed: 0
- Command: `cd backend && $env:PYTHONPATH="." && pytest`

## Current Known Limitations
The most recent gaps documented in `docs/LIMITATIONS.md` were addressed in the previous iteration (Kafka integration, MinIO integration, RBAC tables, Email notifications, and SQLite Connection Pool performance). Remaining limitations primarily involve UI polish and removal of synthetic/AI-generated wording to make the prototype feel concrete and grounded.

## Current Demo Flow
- Patna Flood Scenario (Judge Mode) triggers via `/api/demo/start`. Simulates sequential citizen reports, weather events, clustering, fusion, verification, and alerting over time.
