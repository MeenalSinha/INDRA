"""
Relational schema for INDRA.

Geospatial note: columns are plain lat/lng floats so the schema runs
identically on SQLite (DEMO MODE) and Postgres (LIVE MODE). When
DATABASE_URL points at Postgres with the PostGIS extension enabled, the
geo/clustering.py and geo/utils.py modules can be swapped to issue
ST_DWithin / ST_ClusterDBSCAN queries against a `geography(Point)` column
instead of computing haversine distance in Python -- the API/service layer
above does not change. This keeps the demo runnable without PostGIS while
keeping the upgrade path explicit, per the DEMO vs LIVE architecture
requirement.
"""
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON, Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


def now():
    return dt.datetime.utcnow()


class User(Base):
    """Database-backed user accounts for RBAC.

    Seeded from DEMO_* env vars on first boot (see seed.py) so the three
    demo accounts work identically to before. An ADMIN can create additional
    accounts via POST /api/auth/users without restarting or editing env vars.
    Passwords are bcrypt-hashed (passlib); the plain-text value is never stored.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # ADMIN, ANALYST, VIEWER
    created_at = Column(DateTime, default=now)
    is_active = Column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    source_type = Column(String, nullable=False)  # government, weather_api, social, citizen, dataset, news
    trust_level = Column(String, default="UNKNOWN")  # HIGH, MEDIUM, LOW, UNKNOWN
    reliability_score = Column(Float, default=0.5)
    verification_history_count = Column(Integer, default=0)
    metadata_completeness_avg = Column(Float, default=0.5)
    created_at = Column(DateTime, default=now)

    reports = relationship("Report", back_populates="source")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    source_name = Column(String)
    source_type = Column(String)
    source_ref_id = Column(String)  # source_id field from ingestion payload

    text = Column(Text, default="")
    timestamp = Column(DateTime, default=now, index=True)
    created_at = Column(DateTime, default=now, index=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True, index=True)

    hashtags = Column(JSON, default=list)
    raw_metadata = Column(JSON, default=dict)

    event_type = Column(String, nullable=True, index=True)         # AI classification output
    classification_confidence = Column(Float, nullable=True)

    processing_status = Column(String, default="RECEIVED")
    # RECEIVED -> PROCESSING -> NORMALIZED -> ANALYZED -> FUSED -> VERIFIED

    duplicate_status = Column(String, default="UNIQUE", index=True)  # UNIQUE, LIKELY_DUPLICATE
    duplicate_of_report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)

    # True only for rows created by seed.py's historical backfill. Kept out
    # of live clustering (see ingestion/adapters.py) so a fresh incoming
    # report stream forms its own event rather than silently merging into
    # (and inheriting the verification_status of) old seeded demo data that
    # happens to sit at the same coordinates -- found during the golden-path
    # audit: Judge Mode's Patna Flood scenario was fusing into the already-
    # VERIFIED seeded Patna event, so the live "admin verifies" demo moment
    # never actually triggered a state change.
    is_seed_data = Column(Boolean, default=False)

    source = relationship("Source", back_populates="reports")
    media_items = relationship("Media", back_populates="report")
    event_links = relationship("EventReport", back_populates="report")

    __table_args__ = (
        # Matches the exact WHERE clause the clustering candidate query
        # (ingestion/adapters.py) runs on every single ingest -- this is
        # the composite index that query actually needs, not a generic
        # "index everything" guess.
        Index("ix_reports_event_type_timestamp_seed", "event_type", "timestamp", "is_seed_data"),
    )


class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("reports.id"))
    media_url = Column(String)
    media_type = Column(String, default="image")
    detected_category = Column(String, nullable=True)
    analysis_confidence = Column(Float, nullable=True)
    evidence_summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)

    report = relationship("Report", back_populates="media_items")


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id = Column(Integer, primary_key=True)
    city = Column(String)
    state = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    rainfall_mm = Column(Float, nullable=True)
    wind_speed_kmph = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    visibility_km = Column(Float, nullable=True)
    baseline_rainfall_mm = Column(Float, nullable=True)
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=now)
    source_name = Column(String, default="IMD Simulated Feed")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    event_code = Column(String, unique=True)  # e.g. EVT-1024
    event_type = Column(String, index=True)
    title = Column(String)
    description = Column(Text, default="")

    severity = Column(String, default="LOW", index=True)       # LOW, MODERATE, HIGH, CRITICAL
    severity_reasons = Column(JSON, default=list)

    confidence = Column(Float, default=0.0)
    fusion_breakdown = Column(JSON, default=dict)   # semantic/geo/time/weather/source/independent

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True, index=True)
    affected_area_km2 = Column(Float, nullable=True)

    report_count = Column(Integer, default=0)
    verified_report_count = Column(Integer, default=0)
    independent_source_count = Column(Integer, default=0)
    evidence_count = Column(Integer, default=0)

    verification_status = Column(String, default="UNVERIFIED", index=True)
    # UNVERIFIED, UNDER_REVIEW, PROBABLE, VERIFIED, REJECTED

    start_time = Column(DateTime, default=now, index=True)
    last_updated = Column(DateTime, default=now, index=True)

    timeline = Column(JSON, default=list)  # list of {time, label}

    event_reports = relationship("EventReport", back_populates="event")


class EventReport(Base):
    __tablename__ = "event_reports"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    report_id = Column(Integer, ForeignKey("reports.id"))
    added_at = Column(DateTime, default=now)

    event = relationship("Event", back_populates="event_reports")
    report = relationship("Report", back_populates="event_links")


class VerificationAction(Base):
    __tablename__ = "verification_actions"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    action = Column(String)  # VERIFY, REJECT, REQUEST_MORE_EVIDENCE, ESCALATE, SEVERITY_CHANGE
    admin_name = Column(String, default="Sixth Sense Admin")
    reason = Column(String, default="")
    previous_state = Column(String, default="")
    new_state = Column(String, default="")
    created_at = Column(DateTime, default=now)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    level = Column(String, default="INFO")  # INFO, WARNING, HIGH, CRITICAL
    title = Column(String)
    message = Column(String)
    created_at = Column(DateTime, default=now)
    acknowledged = Column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String, default="system")
    action = Column(String)
    target_type = Column(String)
    target_id = Column(Integer, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    source = Column(String)
    date_range = Column(String)
    record_count = Column(Integer, default=0)
    event_types = Column(JSON, default=list)
    geographic_coverage = Column(String)
    last_updated = Column(DateTime, default=now)
    description = Column(String, default="")
