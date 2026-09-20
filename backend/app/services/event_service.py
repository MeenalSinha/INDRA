import datetime as dt
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from .. import models
from ..repositories import event_repo, report_repo
from ..geo.utils import haversine_km
from ..core import config

class EventService:
    @staticmethod
    def list_events(
        db: Session, 
        event_type: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        severity: Optional[str] = None,
        verification_status: Optional[str] = None,
        q: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[int, List[models.Event]]:
        d_from = dt.datetime.fromisoformat(date_from) if date_from else None
        d_to = dt.datetime.fromisoformat(date_to) if date_to else None
        
        return event_repo.list_events(
            db,
            event_type=event_type,
            severity=severity,
            verification_status=verification_status,
            state=state,
            date_from=d_from,
            date_to=d_to,
            q=q,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_event(db: Session, event_id: int) -> Optional[models.Event]:
        return event_repo.get_with_reports(db, event_id)

    @staticmethod
    def get_events_nearby(db: Session, lat: float, lng: float, radius_km: float = 50) -> tuple[int, List[models.Event]]:
        if config.IS_POSTGRES:
            from ..geo.postgis import events_within_radius_postgis
            ids = events_within_radius_postgis(db, lat, lng, radius_km)
            events_by_id = {e.id: e for e in db.query(models.Event).filter(models.Event.id.in_(ids)).all()}
            ordered = [events_by_id[i] for i in ids if i in events_by_id]
            return len(ordered), ordered

        candidates = db.query(models.Event).filter(models.Event.latitude.isnot(None)).all()
        within = [e for e in candidates if haversine_km(lat, lng, e.latitude, e.longitude) <= radius_km]
        within.sort(key=lambda e: haversine_km(lat, lng, e.latitude, e.longitude))
        return len(within), within

    @staticmethod
    def get_events_bbox(db: Session, min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> tuple[int, List[models.Event]]:
        rows = (
            db.query(models.Event)
            .filter(models.Event.latitude >= min_lat, models.Event.latitude <= max_lat)
            .filter(models.Event.longitude >= min_lng, models.Event.longitude <= max_lng)
            .all()
        )
        return len(rows), rows

    @staticmethod
    def get_event_evidence(db: Session, event_id: int) -> Optional[dict]:
        e = event_repo.get_with_reports(db, event_id)
        if not e:
            return None
            
        report_ids = [er.report_id for er in e.event_reports]
        reports = report_repo.model
        reports = db.query(models.Report).filter(models.Report.id.in_(report_ids)).all()
        media = db.query(models.Media).filter(models.Media.report_id.in_(report_ids)).all()
        weather = (
            db.query(models.WeatherObservation)
            .filter(models.WeatherObservation.city == e.city)
            .order_by(models.WeatherObservation.timestamp.desc())
            .limit(10).all()
        )
        return {
            "reports": len(reports),
            "independent_sources": len({r.source_name for r in reports}),
            "images": len(media),
            "weather_observations": len(weather),
            "media": [{"url": m.media_url, "category": m.detected_category, "confidence": m.analysis_confidence} for m in media],
        }

event_service = EventService()
