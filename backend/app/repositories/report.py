from typing import Optional, List, Any
import datetime as dt
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_
from .base import BaseRepository
from .. import models

class ReportRepository(BaseRepository[models.Report]):
    def __init__(self):
        super().__init__(models.Report)

    def get_with_relations(self, db: Session, id: Any) -> Optional[models.Report]:
        return db.query(self.model).options(
            selectinload(self.model.media_items), 
            selectinload(self.model.event_links)
        ).filter(self.model.id == id).first()

    def list_reports(
        self, 
        db: Session, 
        *, 
        event_type: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        source_type: Optional[str] = None,
        duplicate_status: Optional[str] = None,
        date_from: Optional[dt.datetime] = None,
        date_to: Optional[dt.datetime] = None,
        q: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[int, List[models.Report]]:
        query = db.query(self.model).options(
            selectinload(self.model.media_items), 
            selectinload(self.model.event_links)
        )
        if date_from:
            query = query.filter(self.model.timestamp >= date_from)
        if date_to:
            query = query.filter(self.model.timestamp <= date_to)
        if duplicate_status:
            query = query.filter(self.model.duplicate_status == duplicate_status)
        if event_type:
            query = query.filter(self.model.event_type == event_type)
        if state:
            query = query.filter(self.model.state == state)
        if city:
            query = query.filter(self.model.city == city)
        if source_type:
            query = query.filter(self.model.source_type == source_type)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(self.model.text.ilike(like), self.model.city.ilike(like)))
            
        total = query.count()
        rows = query.order_by(self.model.timestamp.desc()).offset(skip).limit(limit).all()
        return total, rows

report_repo = ReportRepository()
