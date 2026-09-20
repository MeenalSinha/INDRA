"""
Ingestion layer.

Adapters give each data source (government/weather APIs, social media,
citizen reports, public datasets, media uploads) a common normalized shape
before it enters the pipeline, per the spec's adapter interface
requirement. In DEMO MODE the "adapters" are simple normalizers fed by
seed/simulated data; in LIVE MODE the same classes are where a real HTTP
client / webhook receiver / social API poller would live -- the
`ingest_report()` pipeline below does not change either way.

Pipeline (mirrors the architecture diagram):
    RECEIVED -> PROCESSING -> NORMALIZED -> ANALYZED -> FUSED
with a WebSocket / pubsub event published at each stage so the frontend's
live feed and dashboard update without polling.
"""
import datetime as dt
from ..core import config
from .. import models
from ..services.ingestion_service import ingestion_service

# Minimal offline geocoding fallback for demo records that arrive with a
# city name but no coordinates (e.g. a terse citizen SMS-style report).
INDIAN_CITY_COORDS = {
    "patna": (25.5941, 85.1376, "Bihar"),
    "guwahati": (26.1445, 91.7362, "Assam"),
    "mumbai": (19.0760, 72.8777, "Maharashtra"),
    "new delhi": (28.6139, 77.2090, "Delhi"),
    "delhi": (28.6139, 77.2090, "Delhi"),
    "chennai": (13.0827, 80.2707, "Tamil Nadu"),
    "jaipur": (26.9124, 75.7873, "Rajasthan"),
    "jodhpur": (26.2389, 73.0243, "Rajasthan"),
    "bengaluru": (12.9716, 77.5946, "Karnataka"),
    "hyderabad": (17.3850, 78.4867, "Telangana"),
    "kolkata": (22.5726, 88.3639, "West Bengal"),
    "ahmedabad": (23.0225, 72.5714, "Gujarat"),
    "bhubaneswar": (20.2961, 85.8245, "Odisha"),
}

from abc import ABC, abstractmethod

class DataSourceAdapter(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str:
        pass

    @abstractmethod
    def fetch(self) -> list[dict]:
        pass

    def normalize(self, raw: dict) -> dict:
        return normalize_payload(raw)

    def validate(self, payload: dict) -> bool:
        return True

    async def publish(self, db, payload: dict):
        if self.validate(payload):
            return await ingest_report(db, payload)
        return None

class IMDAdapter(DataSourceAdapter):
    source_type = "government"
    def fetch(self): return []

class GovernmentWeatherAdapter(DataSourceAdapter):
    source_type = "government"
    def fetch(self): return []

class WeatherAPIAdapter(DataSourceAdapter):
    source_type = "weather_api"
    def fetch(self): return []

class DatasetAdapter(DataSourceAdapter):
    source_type = "dataset"
    def fetch(self): return []

class SocialMediaAdapter(DataSourceAdapter):
    source_type = "social"
    def fetch(self): return []

class CitizenReportAdapter(DataSourceAdapter):
    source_type = "citizen"
    def fetch(self): return []

class MediaAdapter(DataSourceAdapter):
    source_type = "image"
    def fetch(self): return []

def normalize_payload(raw: dict) -> dict:
    """Schema validation, timestamp/GPS normalization, missing-value handling."""
    payload = dict(raw)
    payload.setdefault("text", "")
    payload.setdefault("metadata", {})
    
    # Extract hashtags if not present
    if "hashtags" not in payload and payload.get("text"):
        import re
        payload["hashtags"] = list(set(re.findall(r"#(\w+)", payload["text"])))
    else:
        payload.setdefault("hashtags", [])
    # Timestamp normalization
    ts = payload.get("timestamp")
    if isinstance(ts, str):
        try:
            payload["timestamp"] = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            payload["timestamp"] = dt.datetime.utcnow()
    elif not isinstance(ts, dt.datetime):
        payload["timestamp"] = dt.datetime.utcnow()

    # GPS validation / geocoding fallback
    lat, lng = payload.get("latitude"), payload.get("longitude")
    valid_gps = isinstance(lat, (int, float)) and isinstance(lng, (int, float)) and -90 <= lat <= 90 and -180 <= lng <= 180
    if not valid_gps:
        city_key = (payload.get("city") or "").strip().lower()
        if city_key in INDIAN_CITY_COORDS:
            lat, lng, state = INDIAN_CITY_COORDS[city_key]
            payload["latitude"], payload["longitude"] = lat, lng
            payload.setdefault("state", state)
        else:
            payload["latitude"], payload["longitude"] = None, None

    if not payload.get("state"):
        city_key = (payload.get("city") or "").strip().lower()
        if city_key in INDIAN_CITY_COORDS:
            payload["state"] = INDIAN_CITY_COORDS[city_key][2]

    return payload


def get_or_create_source(db, name: str, source_type: str):
    src = db.query(models.Source).filter(models.Source.name == name).first()
    if src:
        return src
    src = models.Source(name=name, source_type=source_type, trust_level="UNKNOWN", reliability_score=0.5)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


async def ingest_report(db, raw_payload: dict, broadcast: bool = True) -> models.Report:
    """
    Single entry point for all adapters (REST, simulator, batch loader).

    Normalizes the payload then delegates to IngestionService which runs
    the full pipeline: persist → classify → media → dedup → cluster →
    fuse → alert dispatch.  Signature is stable — all callers unchanged.
    """
    payload = normalize_payload(raw_payload)
    return await ingestion_service.run(db, payload, broadcast)
