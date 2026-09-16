import datetime as dt
from typing import Optional, Any
from pydantic import BaseModel


class WeatherReport(BaseModel):
    id: Optional[int] = None
    source: str
    source_type: str = "citizen"
    source_id: Optional[str] = None
    timestamp: Optional[str] = None
    received_at: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    event_type: Optional[str] = None
    text: str = ""
    media: list[str] = []
    metadata: dict[str, Any] = {}
    raw_payload: dict[str, Any] = {}
    reliability: Optional[float] = None
    processing_status: str = "RECEIVED"
    verification_status: str = "UNVERIFIED"


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
