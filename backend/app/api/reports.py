import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_
from .. import models, schemas
from ..database import get_db
from ..ingestion.adapters import ingest_report
from ..security.auth import require_admin
from ..security.jwt_auth import require_role

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _serialize(r: models.Report):
    return {
        "id": r.id, "source": r.source_name, "source_type": r.source_type,
        "text": r.text, "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        "latitude": r.latitude, "longitude": r.longitude, "city": r.city, "state": r.state,
        "hashtags": r.hashtags, "event_type": r.event_type,
        "classification_confidence": r.classification_confidence,
        "processing_status": r.processing_status, "duplicate_status": r.duplicate_status,
        "duplicate_of_report_id": r.duplicate_of_report_id,
        "media": [{"url": m.media_url, "type": m.media_type, "category": m.detected_category,
                    "confidence": m.analysis_confidence, "summary": m.evidence_summary} for m in r.media_items],
        "event_id": r.event_links[0].event_id if r.event_links else None,
    }


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    event_type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    verification_status: str | None = None,
    source_type: str | None = None,
    duplicate_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    query = db.query(models.Report).options(
        selectinload(models.Report.media_items), selectinload(models.Report.event_links)
    )
    if date_from:
        query = query.filter(models.Report.timestamp >= dt.datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(models.Report.timestamp <= dt.datetime.fromisoformat(date_to))
    if duplicate_status:
        query = query.filter(models.Report.duplicate_status == duplicate_status)
    if event_type:
        query = query.filter(models.Report.event_type == event_type)
    if state:
        query = query.filter(models.Report.state == state)
    if city:
        query = query.filter(models.Report.city == city)
    if source_type:
        query = query.filter(models.Report.source_type == source_type)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Report.text.ilike(like), models.Report.city.ilike(like)))
    total = query.count()
    rows = query.order_by(models.Report.timestamp.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize(r) for r in rows]}


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Report).get(report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return _serialize(r)


@router.post("")
async def create_report(payload: schemas.ReportIn, db: Session = Depends(get_db)):
    report = await ingest_report(db, payload.model_dump())
    return _serialize(report)


@router.post("/{report_id}/duplicate")
def mark_duplicate(report_id: int, payload: schemas.DuplicateMarkIn, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    from ..verification.service import mark_report_duplicate
    r = mark_report_duplicate(db, report_id, payload.duplicate_of, payload.admin_name)
    if not r:
        raise HTTPException(404, "Report not found")
    return _serialize(r)


@router.post("/{report_id}/link/{event_id}")
def link_report_to_event(report_id: int, event_id: int, db: Session = Depends(get_db)):
    report = db.query(models.Report).get(report_id)
    event = db.query(models.Event).get(event_id)
    if not report or not event:
        raise HTTPException(404, "Report or event not found")
    exists = db.query(models.EventReport).filter_by(report_id=report_id, event_id=event_id).first()
    if not exists:
        db.add(models.EventReport(report_id=report_id, event_id=event_id))
        event.report_count = db.query(models.EventReport).filter_by(event_id=event_id).count()
        db.commit()
    return _serialize(report)
