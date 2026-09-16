"""add postgis geometry columns

Revision ID: b1c2d3e4f5a6
Revises: 92ad302abd39
Create Date: 2026-09-16

Adds real PostGIS geometry(Point, 4326) columns to reports and events,
backed by a GIST spatial index -- kept alongside the existing lat/lng
float columns (which remain the portable, SQLite-compatible source of
truth) rather than replacing them, so Demo Mode is unaffected. In Live
Mode, geo/postgis.py keeps `geom` in sync with lat/lng on write and uses
it for real ST_DWithin radius queries instead of the Python haversine
fallback.
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "92ad302abd39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_geom ON reports USING GIST (geom)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_geom ON events USING GIST (geom)")
    # Backfill from existing lat/lng for any rows already present (e.g. a
    # database migrated after being seeded).
    op.execute(
        "UPDATE reports SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) "
        "WHERE geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    op.execute(
        "UPDATE events SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) "
        "WHERE geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reports_geom")
    op.execute("DROP INDEX IF EXISTS ix_events_geom")
    op.execute("ALTER TABLE reports DROP COLUMN IF EXISTS geom")
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS geom")
