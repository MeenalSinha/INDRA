from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..interfaces import ISpatialStore
from ..utils import haversine_km

class PostgisSpatialStore(ISpatialStore):
    """
    Real PostGIS integration for Live Mode using ST_DWithin and ST_MakePoint.
    """
    def sync_report_geom(self, db: Session, report_id: int, lat: float, lng: float) -> None:
        if lat is None or lng is None:
            return
        db.execute(
            text("UPDATE reports SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) WHERE id = :id"),
            {"lng": lng, "lat": lat, "id": report_id},
        )

    def sync_event_geom(self, db: Session, event_id: int, lat: float, lng: float) -> None:
        if lat is None or lng is None:
            return
        db.execute(
            text("UPDATE events SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) WHERE id = :id"),
            {"lng": lng, "lat": lat, "id": event_id},
        )

    def events_within_radius(self, db: Session, lat: float, lng: float, radius_km: float) -> tuple[int, List["models.Event"]]: # type: ignore
        from ... import models
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
        
        ids = [r[0] for r in rows]
        if not ids:
            return 0, []
            
        events_by_id = {e.id: e for e in db.query(models.Event).filter(models.Event.id.in_(ids)).all()}
        ordered = [events_by_id[i] for i in ids if i in events_by_id]
        return len(ordered), ordered


class FallbackSpatialStore(ISpatialStore):
    """
    Fallback implementation using Haversine math for SQLite (Demo Mode).
    """
    def sync_report_geom(self, db: Session, report_id: int, lat: float, lng: float) -> None:
        pass  # No-op in SQLite

    def sync_event_geom(self, db: Session, event_id: int, lat: float, lng: float) -> None:
        pass  # No-op in SQLite

    def events_within_radius(self, db: Session, lat: float, lng: float, radius_km: float) -> tuple[int, List["models.Event"]]: # type: ignore
        from ... import models
        candidates = db.query(models.Event).filter(models.Event.latitude.isnot(None)).all()
        within = [e for e in candidates if haversine_km(lat, lng, e.latitude, e.longitude) <= radius_km]
        within.sort(key=lambda e: haversine_km(lat, lng, e.latitude, e.longitude))
        return len(within), within
