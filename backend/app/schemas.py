import datetime as dt
from typing import Optional, Any
from pydantic import BaseModel


class ReportIn(BaseModel):
    source: str
    source_type: str = "citizen"
    source_id: Optional[str] = None
    text: str = ""
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    hashtags: list[str] = []
    media_url: Optional[str] = None
    media_type: Optional[str] = "image"
    media_category: Optional[str] = None
    raw_metadata: dict[str, Any] = {}


class VerificationActionIn(BaseModel):
    admin_name: str = "Sixth Sense Admin"
    reason: str = ""


class SeverityChangeIn(BaseModel):
    severity: str
    admin_name: str = "Sixth Sense Admin"
    reason: str = ""


class DuplicateMarkIn(BaseModel):
    duplicate_of: int
    admin_name: str = "Sixth Sense Admin"
