"""
Seeds the database with the 9 sample Indian weather scenarios, backing
reports, weather observations, sources, datasets and one active alert, so
the dashboard/map/events pages are populated the moment the app starts --
no manual "load demo data" step required (a "Load Demo Dataset" button on
the Datasets page can re-run this for a clean-slate demo).
"""
import datetime as dt
import random
from . import models
from .database import SessionLocal, engine, Base, ensure_schema
from .demo.scenarios import SEED_EVENTS
from .ml.reliability import predict as score_source

SOURCE_DEFS = [
    ("IMD Government Feed", "government"),
    ("IMD Weather Feed", "weather_api"),
    ("Verified Citizen Reporter", "citizen_verified"),
    ("Citizen Reporter App", "citizen"),
    ("Social Media Monitor", "social"),
    ("News Source", "news"),
    ("Public Dataset — IMD Archive", "dataset"),
]

REPORT_TEXT_BY_TYPE = {
    "Urban Flooding": "Roads completely flooded after hours of heavy rain, water entering homes.",
    "Heavy Rainfall": "Continuous heavy rainfall since morning, streets waterlogged in low-lying areas.",
    "Strong Winds": "Strong winds uprooted trees and damaged hoardings across the city.",
    "Fog": "Dense fog reducing visibility on the highway since early morning.",
    "Dust Storm": "Dust storm reduced visibility sharply, flights delayed at the airport.",
    "Thunderstorm": "Thunderstorm with frequent lightning strikes reported across the district.",
    "Heatwave": "Extreme heat wave conditions, temperatures well above seasonal average.",
    "Cyclone": "Cyclonic system making landfall, coastal areas issued high alert.",
}


def _seed_users(db):
    """Create the three demo accounts in the `users` table if they don't
    already exist. Called every boot — uses upsert-by-username logic so
    it's safe to re-run against a database that already has users."""
    import os
    from .security.jwt_auth import hash_password

    demo_accounts = [
        (os.getenv("DEMO_ADMIN_USERNAME", "admin"),
         os.getenv("DEMO_ADMIN_PASSWORD", "indra-admin-demo"), "ADMIN"),
        (os.getenv("DEMO_ANALYST_USERNAME", "analyst"),
         os.getenv("DEMO_ANALYST_PASSWORD", "indra-analyst-demo"), "ANALYST"),
        (os.getenv("DEMO_VIEWER_USERNAME", "viewer"),
         os.getenv("DEMO_VIEWER_PASSWORD", "indra-viewer-demo"), "VIEWER"),
    ]
    for username, password, role in demo_accounts:
        existing = db.query(models.User).filter(models.User.username == username).first()
        if not existing:
            db.add(models.User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
            ))
    db.commit()


def run_seed():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        # Always seed users (runs every boot, idempotent by username).
        _seed_users(db)

        if db.query(models.Event).count() > 0:
            return  # already seeded

        sources = {}
        for name, stype in SOURCE_DEFS:
            result = score_source(stype, verification_history_count=random.randint(5, 60), metadata_completeness=0.75)
            score, trust = result["score"], result["trust_level"]
            src = models.Source(name=name, source_type=stype, trust_level=trust, reliability_score=score,
                                 verification_history_count=random.randint(5, 60))
            db.add(src)
            sources[name] = src
        db.commit()

        now = dt.datetime.utcnow()

        for i, s in enumerate(SEED_EVENTS):
            start_time = now - dt.timedelta(hours=s["hours_ago"])
            event = models.Event(
                event_code=f"EVT-{1000 + i + 1}",
                event_type=s["event_type"],
                title=f"{s['event_type']} — {s['city']}",
                description=f"{s['report_count']} reports fused near {s['city']}, {s['state']}.",
                severity=s["severity"],
                severity_reasons=[f"{s['report_count']} reports received", f"Category: {s['event_type']}"],
                confidence=s["confidence"],
                fusion_breakdown={
                    "semantic_similarity": round(min(0.97, s["confidence"] + 0.02), 2),
                    "geo_proximity": round(min(0.97, s["confidence"] - 0.03), 2),
                    "time_proximity": round(min(0.97, s["confidence"] + 0.01), 2),
                    "weather_agreement": round(min(0.97, s["confidence"] - 0.05), 2),
                    "source_reliability": round(min(0.97, s["confidence"] - 0.15), 2),
                    "independent_evidence": round(min(0.97, s["confidence"] - 0.02), 2),
                },
                latitude=s["lat"], longitude=s["lng"], city=s["city"], state=s["state"],
                affected_area_km2=round(random.uniform(4, 40), 1),
                report_count=s["report_count"],
                verified_report_count=s["verified_report_count"],
                independent_source_count=random.randint(6, 20),
                evidence_count=s["report_count"] + random.randint(5, 25),
                verification_status=s["verification_status"],
                start_time=start_time,
                last_updated=start_time + dt.timedelta(minutes=random.randint(15, 90)),
                timeline=[
                    {"time": start_time.isoformat(), "label": "First report received"},
                    {"time": (start_time + dt.timedelta(minutes=5)).isoformat(), "label": "Weather anomaly detected"},
                    {"time": (start_time + dt.timedelta(minutes=12)).isoformat(), "label": "Geospatial clustering identified event"},
                    {"time": (start_time + dt.timedelta(minutes=20)).isoformat(), "label": "Fusion confidence finalized"},
                ] + ([{"time": (start_time + dt.timedelta(minutes=28)).isoformat(), "label": "Verified by Sixth Sense Admin"}]
                     if s["verification_status"] == "VERIFIED" else []),
            )
            db.add(event)
            db.flush()

            # Backing reports (sample, not all 127 stored individually for
            # older seed events -- report_count is the authoritative total)
            sample_n = min(12, s["report_count"])
            text = REPORT_TEXT_BY_TYPE.get(s["event_type"], "Weather event reported in the area.")
            for j in range(sample_n):
                src_name = random.choice(list(sources.keys()))
                r = models.Report(
                    source_id=sources[src_name].id, source_name=src_name, source_type=sources[src_name].source_type,
                    text=text, timestamp=start_time + dt.timedelta(minutes=j * 3),
                    latitude=s["lat"] + random.uniform(-0.02, 0.02), longitude=s["lng"] + random.uniform(-0.02, 0.02),
                    city=s["city"], state=s["state"], event_type=s["event_type"],
                    classification_confidence=round(random.uniform(0.7, 0.95), 2),
                    processing_status="FUSED", duplicate_status="UNIQUE", is_seed_data=True,
                )
                db.add(r)
                db.flush()
                db.add(models.EventReport(event_id=event.id, report_id=r.id))
                if j < 3:
                    db.add(models.Media(
                        report_id=r.id, media_url=f"demo://{s['city'].lower()}-{j}.jpg", media_type="image",
                        detected_category="Flooded Road" if s["event_type"] == "Urban Flooding" else "Heavy Rain",
                        analysis_confidence=round(random.uniform(0.7, 0.9), 2),
                        evidence_summary="Image evidence consistent with reported conditions",
                    ))

            db.add(models.WeatherObservation(
                city=s["city"], state=s["state"], latitude=s["lat"], longitude=s["lng"],
                rainfall_mm=round(random.uniform(60, 180), 1) if "Rain" in s["event_type"] or "Flood" in s["event_type"] else None,
                wind_speed_kmph=round(random.uniform(40, 90), 1) if "Wind" in s["event_type"] or "Cyclone" in s["event_type"] else None,
                temperature_c=round(random.uniform(40, 47), 1) if s["event_type"] == "Heatwave" else None,
                visibility_km=round(random.uniform(0.2, 1.5), 1) if s["event_type"] == "Fog" else None,
                baseline_rainfall_mm=35.0, is_anomaly=s["confidence"] > 0.7, anomaly_score=round(s["confidence"], 2),
                timestamp=start_time, source_name="IMD Weather Feed",
            ))

            if s["severity"] == "CRITICAL":
                db.add(models.Alert(
                    event_id=event.id, level="CRITICAL", title=f"Critical weather event: {event.title}",
                    message=f"{event.report_count} reports, {round(event.confidence * 100)}% confidence.",
                    created_at=start_time,
                ))

            if s["verification_status"] == "VERIFIED":
                db.add(models.VerificationAction(
                    event_id=event.id, action="VERIFY", admin_name="Sixth Sense Admin",
                    reason="Corroborated by independent sources and weather observation",
                    previous_state="PROBABLE", new_state="VERIFIED",
                    created_at=start_time + dt.timedelta(minutes=28),
                ))
                db.add(models.AuditLog(
                    actor="Sixth Sense Admin", action="VERIFY", target_type="event", target_id=event.id,
                    details={"new_state": "VERIFIED"}, created_at=start_time + dt.timedelta(minutes=28),
                ))

        # Datasets catalogue
        db.add_all([
            models.Dataset(name="IMD Historical Rainfall Archive", source="India Meteorological Department",
                            date_range="2015 - 2026", record_count=482000,
                            event_types=["Heavy Rainfall", "Urban Flooding", "Thunderstorm"],
                            geographic_coverage="Pan-India", last_updated=now - dt.timedelta(days=2),
                            description="District-level daily rainfall records used for anomaly baselines."),
            models.Dataset(name="Citizen Reports — Monsoon 2026", source="INDRA Citizen Reporter App",
                            date_range="Jun 2026 - Sep 2026", record_count=52340,
                            event_types=["Urban Flooding", "Heavy Rainfall", "Strong Winds"],
                            geographic_coverage="Bihar, Assam, Maharashtra, Tamil Nadu", last_updated=now - dt.timedelta(hours=6),
                            description="Crowd-sourced ground reports collected during the current monsoon season."),
            models.Dataset(name="Cyclone Track Records — East Coast", source="Public Dataset Archive",
                            date_range="2010 - 2026", record_count=1240,
                            event_types=["Cyclone"], geographic_coverage="Odisha, Andhra Pradesh, West Bengal coast",
                            last_updated=now - dt.timedelta(days=10),
                            description="Historical cyclone landfall and intensity records."),
        ])

        db.commit()

        # Backfill PostGIS geometry for every seeded row with coordinates
        # (Live Mode only -- no-op in Demo Mode).
        from .geo.postgis import sync_report_geom, sync_event_geom
        for r in db.query(models.Report).filter(models.Report.latitude.isnot(None)).all():
            sync_report_geom(db, r.id, r.latitude, r.longitude)
        for e in db.query(models.Event).filter(models.Event.latitude.isnot(None)).all():
            sync_event_geom(db, e.id, e.latitude, e.longitude)
        db.commit()
    finally:
        db.close()
