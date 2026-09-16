#!/bin/sh
# In LIVE MODE (DATABASE_URL set to a Postgres DSN), run the real Alembic
# migrations before starting the app -- verified this session against a
# real local Postgres+PostGIS instance (empty db -> alembic upgrade head
# -> seed -> working app). In DEMO MODE (DATABASE_URL unset), the app's
# own create_all()/ensure_schema() handle the SQLite file directly, so
# migrations are skipped -- Alembic targets Postgres only.
set -e

case "$DATABASE_URL" in
  postgresql*)
    echo "LIVE MODE detected (Postgres) -- running Alembic migrations..."
    alembic upgrade head
    ;;
  *)
    echo "DEMO MODE (no Postgres DATABASE_URL) -- skipping Alembic, using SQLite directly."
    ;;
esac

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
