from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .. import models, schemas
from ..core.database import get_db
from ..verification import service as verification_service
from ..services.event_service import event_service
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
    total, rows = event_service.list_events(
        db,
        event_type=event_type,
        state=state,
        city=city,
        severity=severity,
        verification_status=verification_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
        skip=offset,
        limit=limit
    )
    return {"total": total, "items": [_serialize(e) for e in rows]}


@router.get("/nearby")
def events_nearby(lat: float, lng: float, radius_km: float = 50, db: Session = Depends(get_db)):
    total, rows = event_service.get_events_nearby(db, lat, lng, radius_km)
    return {"total": total, "items": [_serialize(e) for e in rows]}


@router.get("/bbox")
def events_bbox(min_lat: float, min_lng: float, max_lat: float, max_lng: float, db: Session = Depends(get_db)):
    """Bounding-box search."""
    total, rows = event_service.get_events_bbox(db, min_lat, min_lng, max_lat, max_lng)
    return {"total": total, "items": [_serialize(e) for e in rows]}


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    e = event_service.get_event(db, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    return _serialize(e, detailed=True)


@router.get("/{event_id}/evidence")
def get_event_evidence(event_id: int, db: Session = Depends(get_db)):
    evidence = event_service.get_event_evidence(db, event_id)
    if not evidence:
        raise HTTPException(404, "Event not found")
    return evidence


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

