# INDRA — Demo Guide

## Fastest path to a working demo

```bash
cd backend && pip install -r requirements.txt
FRONTEND_DIST=../frontend uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open **http://localhost:8000/**. Seeds itself automatically (107 reports,
9 events across the 9 scenario types) on first run.

## The 2-3 minute judging story

1. **Dashboard** — point out the metrics are live (`GET /api/analytics/
   summary`), not hardcoded, and the map/recent-events panel already
   shows 9 realistic pre-seeded Indian weather scenarios.
2. **Admin Panel → Overview** — click **Start Demo**. This is Judge Mode:
   it feeds the Patna Flood scenario through the *real* ingestion
   pipeline (same `POST /api/reports` code path a genuine citizen report
   would use), not an animated frontend counter.
3. Watch reports arrive on the **Reports** page or the dashboard's Live
   Reports Feed — classification, duplicate detection, and geo-clustering
   are all visibly happening (`event_type`, `classification_confidence`,
   `duplicate_status` populate on real rows as the run progresses).
4. After ~30 seconds the run completes: a **new** Patna Urban Flooding
   event reaches CRITICAL severity, distinct from the historical seeded
   Patna example already on the dashboard, sitting at PROBABLE — genuinely
   awaiting verification.
5. **Open the Investigation screen** for that event (click it on the map,
   Events table, or Admin → Pending Verification). Show the confidence
   breakdown (six itemized real numbers), the timeline, and the evidence
   panel.
6. **Click Verify.** The event's status changes live; the audit log gets
   a real entry; the alert (exactly one, not a flood of duplicates — see
   `docs/INDRA_AUDIT.md` for why that mattered) is visible on the Alerts
   page.
7. **Reset** (Admin Panel → Overview → Reset) wipes the database and
   reseeds a clean baseline — the demo can be repeated immediately for
   the next judge.

## If asked "is this really doing the work, or is it a mockup?"

Point to:
- `docs/EVENT_FUSION.md` — the six real, weighted factors with their
  actual formulas.
- The Investigation screen's confidence breakdown, which is the literal
  JSON `fusion_breakdown` field from the database, not a display trick.
- `docs/INDRA_AUDIT.md` and `docs/UPGRADE_AUDIT.md` — real bugs found by
  actually running the system, with before/after evidence, not a
  self-reported feature checklist.
- `backend/tests/` — 34 automated tests, several of which specifically
  assert the fusion/verification/alert behavior end-to-end (not just "the
  endpoint returns 200").

## Optional: demo against real PostgreSQL + PostGIS

If the judging environment has Postgres+PostGIS reachable (or you want to
show Live Mode specifically):
```bash
export DATABASE_URL="postgresql+psycopg2://indra:indra_dev_password@localhost:5432/indra"
cd backend && alembic upgrade head
python -c "from app.seed import run_seed; run_seed()"
FRONTEND_DIST=../frontend uvicorn app.main:app --host 0.0.0.0 --port 8000
```
`GET /api/health` will report `"mode": "LIVE (Postgres)"`. The exact same
golden scenario (start → fuse → verify) works identically — this was
live-verified during the upgrade audit, not just documented as possible.
