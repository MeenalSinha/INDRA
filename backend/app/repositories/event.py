from typing import Optional, List, Any
import datetime as dt
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_
from .base import BaseRepository
from .. import models

class EventRepository(BaseRepository[models.Event]):
    def __init__(self):
        super().__init__(models.Event)

    def get_by_code(self, db: Session, event_code: str) -> Optional[models.Event]:
        return db.query(self.model).filter(self.model.event_code == event_code).first()

    def get_with_reports(self, db: Session, id: Any) -> Optional[models.Event]:
        return db.query(self.model).options(
            selectinload(self.model.event_reports).selectinload(models.EventReport.report)
        ).filter(self.model.id == id).first()

    def list_events(
        self, 
        db: Session, 
        *, 
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        verification_status: Optional[str] = None,
        state: Optional[str] = None,
        date_from: Optional[dt.datetime] = None,
        date_to: Optional[dt.datetime] = None,
        q: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[int, List[models.Event]]:
        query = db.query(self.model)
        
        if date_from:
            query = query.filter(self.model.start_time >= date_from)
        if date_to:
            query = query.filter(self.model.start_time <= date_to)
        if event_type:
            query = query.filter(self.model.event_type == event_type)
        if severity:
            query = query.filter(self.model.severity == severity)
        if verification_status:
            query = query.filter(self.model.verification_status == verification_status)
        if state:
            query = query.filter(self.model.state == state)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(self.model.title.ilike(like), self.model.description.ilike(like)))
            
        total = query.count()
        rows = query.order_by(self.model.last_updated.desc()).offset(skip).limit(limit).all()
        return total, rows

event_repo = EventRepository()
