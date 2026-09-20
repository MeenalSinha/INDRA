from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .. import models
from ..core.database import get_db
from ..realtime import pubsub
from ..security.auth import require_admin
from ..security.jwt_auth import require_role

router = APIRouter(tags=["alerts-sources-health"])


@router.get("/api/v1/alerts")
def list_alerts(db: Session = Depends(get_db), acknowledged: bool | None = None, level: str | None = None):
    query = db.query(models.Alert)
    if acknowledged is not None:
        query = query.filter(models.Alert.acknowledged == acknowledged)
    if level:
        query = query.filter(models.Alert.level == level)
    rows = query.order_by(models.Alert.created_at.desc()).limit(200).all()
    return {"items": [{
        "id": a.id, "event_id": a.event_id, "level": a.level, "title": a.title,
        "message": a.message, "created_at": a.created_at.isoformat(), "acknowledged": a.acknowledged,
    } for a in rows]}


@router.post("/api/v1/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db), _admin: bool = Depends(require_admin), _role: bool = Depends(require_role("ADMIN"))):
    a = db.query(models.Alert).get(alert_id)
    if a:
        a.acknowledged = True
        db.commit()
    return {"ok": True}


@router.get("/api/v1/sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(models.Source).all()
    return {"items": [{
        "id": s.id, "name": s.name, "source_type": s.source_type, "trust_level": s.trust_level,
        "reliability_score": s.reliability_score, "verification_history_count": s.verification_history_count,
    } for s in rows]}


@router.get("/api/datasets")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.query(models.Dataset).all()
    return {"items": [{
        "id": d.id, "name": d.name, "source": d.source, "date_range": d.date_range,
        "record_count": d.record_count, "event_types": d.event_types,
        "geographic_coverage": d.geographic_coverage, "last_updated": d.last_updated.isoformat(),
        "description": d.description,
    } for d in rows]}


@router.get("/api/v1/audit-logs")
def list_audit_logs(db: Session = Depends(get_db), limit: int = 200):
    rows = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return {"items": [{
        "id": a.id, "actor": a.actor, "action": a.action, "target_type": a.target_type,
        "target_id": a.target_id, "details": a.details, "created_at": a.created_at.isoformat(),
    } for a in rows]}


@router.get("/api/v1/search")
def search(q: str, db: Session = Depends(get_db)):
    like = f"%{q}%"
    events = db.query(models.Event).filter(or_(
        models.Event.title.ilike(like), models.Event.city.ilike(like),
        models.Event.state.ilike(like), models.Event.event_code.ilike(like),
    )).limit(20).all()
    reports = db.query(models.Report).filter(or_(
        models.Report.text.ilike(like), models.Report.city.ilike(like),
    )).limit(20).all()
    sources = db.query(models.Source).filter(models.Source.name.ilike(like)).limit(10).all()
    return {
        "events": [{"id": e.id, "title": e.title, "event_code": e.event_code, "city": e.city} for e in events],
        "reports": [{"id": r.id, "text": r.text, "city": r.city} for r in reports],
        "sources": [{"id": s.id, "name": s.name} for s in sources],
    }


@router.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    import datetime as dt
    from ..core import config
    reports_count = db.query(models.Report).count()
    events_count = db.query(models.Event).count()

    now = dt.datetime.utcnow()
    minute_ago = now - dt.timedelta(minutes=1)
    reports_per_min = db.query(models.Report).filter(models.Report.created_at >= minute_ago).count()
    events_per_min = db.query(models.Event).filter(models.Event.last_updated >= minute_ago).count()

    # Approx end-to-end processing latency: time between a report's raw
    # timestamp and when it was actually persisted (created_at), averaged
    # over recently-created reports whose timestamp is close to creation
    # time (i.e. live-ingested, not backfilled historical seed data whose
    # timestamps are deliberately set hours in the past).
    recent_reports = db.query(models.Report).order_by(models.Report.created_at.desc()).limit(50).all()
    latencies_ms = [
        (r.created_at - r.timestamp).total_seconds() * 1000
        for r in recent_reports if r.created_at and r.timestamp
    ]
    latencies_ms = [l for l in latencies_ms if 0 <= l <= 60_000]  # live-ingestion range only
    avg_latency_ms = round(sum(latencies_ms) / len(latencies_ms), 1) if latencies_ms else 0.0

    return {
        "api": "ONLINE",
        "database": "ONLINE",
        "mode": "LIVE (Postgres)" if config.IS_POSTGRES else "DEMO (SQLite)",
        "cache": "ONLINE (in-process, demo)" if not config.REDIS_URL else "ONLINE (Redis)",
        "streaming": "ONLINE (in-process bus, demo)" if not config.KAFKA_BOOTSTRAP_SERVERS else "ONLINE (Kafka)",
        "ai_engine": "ONLINE",
        "websocket": "ONLINE",
        "reports_total": reports_count,
        "events_total": events_count,
        "reports_per_min": reports_per_min,
        "events_per_min": events_per_min,
        "avg_processing_latency_ms": avg_latency_ms,
        "stream_queue_depth": len(pubsub.recent(200)),
        "recent_stream_activity": pubsub.recent(10),
    }


@router.get("/api/admin/overview")
def admin_overview(db: Session = Depends(get_db)):
    pending = db.query(models.Event).filter(models.Event.verification_status.in_(["UNDER_REVIEW", "PROBABLE"])).count()
    suspicious = db.query(models.Report).filter(models.Report.classification_confidence < 0.5).count()
    duplicates = db.query(models.Report).filter(models.Report.duplicate_status == "LIKELY_DUPLICATE").count()
    critical = db.query(models.Event).filter(models.Event.severity == "CRITICAL").count()
    return {
        "pending_verification": pending, "suspicious_reports": suspicious,
        "duplicate_reports": duplicates, "critical_events": critical,
    }

