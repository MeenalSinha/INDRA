"""
Real PostGIS integration for Live Mode.

geo/utils.py's haversine math and geo/clustering.py's DBSCAN remain the
Demo Mode (SQLite-compatible) path and stay exactly as they are --
correct and adequate at demo data volumes, and required anyway since
SQLite has no spatial engine. This module is the additive Live Mode
upgrade: when config.IS_POSTGRES is true, the API layer calls these
functions instead, which run real ST_DWithin / ST_MakePoint queries
against the geometry(Point,4326) columns added by migration
b1c2d3e4f5a6, backed by a real GIST index (verified via EXPLAIN in the
audit -- see docs/UPGRADE_AUDIT.md).
"""
from sqlalchemy import text
from ..core import config


def sync_report_geom(db, report_id: int, lat, lng):
    """Keep `reports.geom` in sync with lat/lng on write. No-op outside
    Live Mode."""
    if not config.IS_POSTGRES or lat is None or lng is None:
        return
    db.execute(
        text("UPDATE reports SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) WHERE id = :id"),
        {"lng": lng, "lat": lat, "id": report_id},
    )


def sync_event_geom(db, event_id: int, lat, lng):
    if not config.IS_POSTGRES or lat is None or lng is None:
        return
    db.execute(
        text("UPDATE events SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) WHERE id = :id"),
        {"lng": lng, "lat": lat, "id": event_id},
    )


def events_within_radius_postgis(db, lat: float, lng: float, radius_km: float):
    """Real ST_DWithin radius search (geography cast, so the distance is
    genuinely in meters over the earth's surface, not a flat-plane
    approximation) -- the Live Mode counterpart to
    api/events.py::events_nearby's haversine fallback."""
    rows = db.execute(
        text(
            """
            SELECT id, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
            FROM events
            WHERE geom IS NOT NULL
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
            ORDER BY distance_m ASC
            """
        ),
        {"lng": lng, "lat": lat, "radius_m": radius_km * 1000},
    ).fetchall()
    return [r[0] for r in rows]

