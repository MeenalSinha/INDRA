import datetime as dt
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from .. import models
from ..repositories import report_repo, event_repo

class ReportService:
    @staticmethod
    def get_report(db: Session, report_id: int) -> Optional[models.Report]:
        return report_repo.get_with_relations(db, report_id)

    @staticmethod
    def list_reports(
        db: Session, 
        event_type: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        verification_status: Optional[str] = None,
        source_type: Optional[str] = None,
        duplicate_status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        q: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[int, List[models.Report]]:
        d_from = dt.datetime.fromisoformat(date_from) if date_from else None
        d_to = dt.datetime.fromisoformat(date_to) if date_to else None
        
        return report_repo.list_reports(
            db,
            event_type=event_type,
            state=state,
            city=city,
            source_type=source_type,
            duplicate_status=duplicate_status,
            date_from=d_from,
            date_to=d_to,
            q=q,
            skip=skip,
            limit=limit
        )

    @staticmethod
    async def create_report(db: Session, payload: dict) -> models.Report:
        # Local import avoids circular dependency:
        # report_service <- adapters <- ingestion_service <- services/__init__
        from ..ingestion.adapters import ingest_report
        return await ingest_report(db, payload)

    @staticmethod
    def link_report_to_event(db: Session, report_id: int, event_id: int) -> Optional[models.Report]:
        report = report_repo.get(db, report_id)
        event = event_repo.get(db, event_id)
        if not report or not event:
            return None
            
        exists = db.query(models.EventReport).filter_by(report_id=report_id, event_id=event_id).first()
        if not exists:
            db.add(models.EventReport(report_id=report_id, event_id=event_id))
            event.report_count = db.query(models.EventReport).filter_by(event_id=event_id).count()
            db.commit()
            
        return report_repo.get_with_relations(db, report_id)

report_service = ReportService()
