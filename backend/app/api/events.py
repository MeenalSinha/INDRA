from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .. import models, schemas
from ..database import get_db
from ..verification import service as verification_service
from ..realtime import pubsub
from ..security.auth import require_admin
from ..security.jwt_auth import require_role

router = APIRouter(prefix="/api/events", tags=["events"])


def _serialize(e: models.Event, detailed: bool = False):
    base = {
        "id": e.id, "event_code": e.event_code, "event_type": e.event_type, "title": e.title,
        "description": e.description, "severity": e.severity, "severity_reasons": e.severity_reasons,
        "confidence": e.confidence, "latitude": e.latitude, "longitude": e.longitude,
        "city": e.city, "state": e.state, "affected_area_km2": e.affected_area_km2,
        "report_count": e.report_count, "verified_report_count": e.verified_report_count,
        "independent_source_count": e.independent_source_count, "evidence_count": e.evidence_count,
        "verification_status": e.verification_status,
        "start_time": e.start_time.isoformat() if e.start_time else None,
        "last_updated": e.last_updated.isoformat() if e.last_updated else None,
    }
    if detailed:
        base["fusion_breakdown"] = e.fusion_breakdown
        base["timeline"] = e.timeline
        base["report_ids"] = [er.report_id for er in e.event_reports]
    return base


@router.get("")
def list_events(
    db: Session = Depends(get_db),
    event_type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    severity: str | None = None,
    verification_status: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    import datetime as dt
    query = db.query(models.Event)
    if date_from:
        query = query.filter(models.Event.start_time >= dt.datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(models.Event.start_time <= dt.datetime.fromisoformat(date_to))
    if event_type:
        query = query.filter(models.Event.event_type == event_type)
    if state:
        query = query.filter(models.Event.state == state)
    if city:
        query = query.filter(models.Event.city == city)
    if severity:
        query = query.filter(models.Event.severity == severity)
    if verification_status:
        query = query.filter(models.Event.verification_status == verification_status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Event.title.ilike(like), models.Event.city.ilike(like),
                                   models.Event.event_code.ilike(like)))
    total = query.count()
    rows = query.order_by(models.Event.last_updated.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize(e) for e in rows]}


@router.get("/nearby")
def events_nearby(lat: float, lng: float, radius_km: float = 50, db: Session = Depends(get_db)):
    """Radius search -- real PostGIS ST_DWithin (geography cast, GIST
    index) in Live Mode; Python haversine over the candidate set in Demo
    Mode, where there is no spatial engine to delegate to."""
    from .. import config
    if config.IS_POSTGRES:
        from ..geo.postgis import events_within_radius_postgis
        ids = events_within_radius_postgis(db, lat, lng, radius_km)
        events_by_id = {e.id: e for e in db.query(models.Event).filter(models.Event.id.in_(ids)).all()}
        ordered = [events_by_id[i] for i in ids if i in events_by_id]
        return {"total": len(ordered), "items": [_serialize(e) for e in ordered]}

    from ..geo.utils import haversine_km
    candidates = db.query(models.Event).filter(models.Event.latitude.isnot(None)).all()
    within = [e for e in candidates if haversine_km(lat, lng, e.latitude, e.longitude) <= radius_km]
    within.sort(key=lambda e: haversine_km(lat, lng, e.latitude, e.longitude))
    return {"total": len(within), "items": [_serialize(e) for e in within]}


@router.get("/bbox")
def events_bbox(min_lat: float, min_lng: float, max_lat: float, max_lng: float, db: Session = Depends(get_db)):
    """Bounding-box search."""
    rows = (
        db.query(models.Event)
        .filter(models.Event.latitude >= min_lat, models.Event.latitude <= max_lat)
        .filter(models.Event.longitude >= min_lng, models.Event.longitude <= max_lng)
        .all()
    )
    return {"total": len(rows), "items": [_serialize(e) for e in rows]}


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    e = db.query(models.Event).get(event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    return _serialize(e, detailed=True)


@router.get("/{event_id}/evidence")
def get_event_evidence(event_id: int, db: Session = Depends(get_db)):
    e = db.query(models.Event).get(event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    report_ids = [er.report_id for er in e.event_reports]
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


@router.post("/{event_id}/verify")
async def verify(event_id: int, payload: schemas.VerificationActionIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    e = verification_service.verify_event(db, event_id, payload.admin_name, payload.reason)
    if not e:
        raise HTTPException(404, "Event not found")
    await pubsub.publish("event.verified", {"event_id": e.id, "verification_status": e.verification_status})
    return _serialize(e, detailed=True)


@router.post("/{event_id}/reject")
async def reject(event_id: int, payload: schemas.VerificationActionIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    e = verification_service.reject_event(db, event_id, payload.admin_name, payload.reason)
    if not e:
        raise HTTPException(404, "Event not found")
    await pubsub.publish("event.rejected", {"event_id": e.id, "verification_status": e.verification_status})
    return _serialize(e, detailed=True)


@router.post("/{event_id}/request-evidence")
async def request_evidence(event_id: int, payload: schemas.VerificationActionIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    e = verification_service.request_more_evidence(db, event_id, payload.admin_name, payload.reason)
    if not e:
        raise HTTPException(404, "Event not found")
    await pubsub.publish("event.updated", {"event_id": e.id, "verification_status": e.verification_status})
    return _serialize(e, detailed=True)


@router.post("/{event_id}/escalate")
async def escalate(event_id: int, payload: schemas.VerificationActionIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    e = verification_service.escalate_event(db, event_id, payload.admin_name, payload.reason)
    if not e:
        raise HTTPException(404, "Event not found")
    await pubsub.publish("event.updated", {"event_id": e.id, "severity": e.severity})
    return _serialize(e, detailed=True)


@router.post("/{event_id}/severity")
async def change_severity(event_id: int, payload: schemas.SeverityChangeIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    e = verification_service.set_severity(db, event_id, payload.severity, payload.admin_name, payload.reason)
    if not e:
        raise HTTPException(404, "Event not found")
    await pubsub.publish("event.updated", {"event_id": e.id, "severity": e.severity})
    return _serialize(e, detailed=True)
