"""
Event Fusion Engine — the core differentiator.

Takes a spatial cluster of raw reports (already classified, de-duplicated,
geo-clustered) and fuses them into ONE structured WeatherEvent with a
transparent, itemized confidence breakdown:

    semantic_similarity   how much the report texts agree
    geo_proximity         how tightly the reports are clustered
    time_proximity        how close together in time
    weather_agreement     do nearby weather observations corroborate it
    source_reliability    average reliability of contributing sources
    independent_evidence  how many distinct sources / how much media

Each factor is 0..1 and the final confidence is a weighted blend -- never
an opaque number. `evidence_count` sums independent reports + weather
observations + images, matching the "Evidence:" panel in the product spec.

Confidence math lives in fusion/confidence.py (pure, DB-free, unit-testable).
Event persistence uses SQLAlchemy 2.0-style db.get() throughout.
"""
import datetime as dt
from collections import Counter

from ..core import config
from .. import models
from ..geo.registry import get_spatial_store
from ..fusion.severity import compute_severity
from ..fusion.confidence import compute_breakdown, compute_confidence
from ..geo.risk_zones import get_risk_zones, check_intersection


def _event_code(db) -> str:
    count = db.query(models.Event).count()
    return f"EVT-{1000 + count + 1}"


def _prepare_breakdown_inputs(reports: list[models.Report], weather_obs: list[models.WeatherObservation]) -> dict:
    return {
        "texts": [r.text or "" for r in reports],
        "coords": [(r.latitude, r.longitude) for r in reports if r.latitude is not None],
        "timestamps": [r.timestamp for r in reports],
        "weather_obs": weather_obs,
        "source_types": [r.source_type for r in reports],
        "source_names": [r.source_name for r in reports],
        "media_counts": [len(r.media_items) for r in reports],
        "report_count": len(reports),
    }


def _compute_majority_attributes(reports: list[models.Report]) -> tuple[str, float|None, float|None, str|None, str|None]:
    type_counts = Counter(r.event_type for r in reports if r.event_type)
    event_type = type_counts.most_common(1)[0][0] if type_counts else "Other"

    lat_vals = [r.latitude for r in reports if r.latitude is not None]
    lng_vals = [r.longitude for r in reports if r.longitude is not None]
    lat = sum(lat_vals) / len(lat_vals) if lat_vals else None
    lng = sum(lng_vals) / len(lng_vals) if lng_vals else None
    city = Counter(r.city for r in reports if r.city).most_common(1)
    state = Counter(r.state for r in reports if r.state).most_common(1)
    return (
        event_type,
        lat,
        lng,
        city[0][0] if city else None,
        state[0][0] if state else None,
    )


async def fuse_cluster(db, report_ids: list[int], weather_obs: list[models.WeatherObservation] | None = None):
    """
    Fuse a cluster of reports into a single Event (creating or updating it).

    Public signature is stable — callers and tests must not need to change.
    Returns the Event ORM object, or None if report_ids resolves to nothing.
    """
    reports = db.query(models.Report).filter(models.Report.id.in_(report_ids)).all()
    if not reports:
        return None
    weather_obs = weather_obs or []

    # ------------------------------------------------------------------ #
    # Build inputs for the pure confidence computation                    #
    # ------------------------------------------------------------------ #
    inputs = _prepare_breakdown_inputs(reports, weather_obs)
    breakdown = await compute_breakdown(**inputs)
    confidence = compute_confidence(breakdown)

    # Pull derived values computed alongside the breakdown
    spread_km = breakdown.pop("_spread_km")
    anomaly_count = breakdown.pop("_anomaly_hits")
    distinct_sources = breakdown.pop("_distinct_sources")
    total_media = breakdown.pop("_total_media")

    # ------------------------------------------------------------------ #
    # Majority event type & centroid location                             #
    # ------------------------------------------------------------------ #
    event_type, lat, lng, city, state = _compute_majority_attributes(reports)

    # ------------------------------------------------------------------ #
    # Severity + risk-zone boost                                          #
    # ------------------------------------------------------------------ #
    severity, reasons = compute_severity(
        event_type=event_type,
        report_count=len(reports),
        spatial_spread_km=spread_km,
        has_weather_anomaly=anomaly_count > 0,
        independent_source_count=distinct_sources,
        confidence=confidence,
        has_image_evidence=total_media > 0,
    )

    zones = get_risk_zones(db)
    intersecting_zones = check_intersection(lat, lng, zones)
    if intersecting_zones:
        if severity != "CRITICAL":
            severity = "CRITICAL" if any(z["risk_level"] == "CRITICAL" for z in intersecting_zones) else "HIGH"
        zone_names = [z["name"] for z in intersecting_zones]
        reasons.append(f"Intersects high-risk zones: {', '.join(zone_names)}")

    # ------------------------------------------------------------------ #
    # Event lookup / create / update — SQLAlchemy 2.0-style db.get()     #
    # ------------------------------------------------------------------ #
    existing_link = (
        db.query(models.EventReport)
        .filter(models.EventReport.report_id.in_([r.id for r in reports]))
        .first()
    )
    event = db.get(models.Event, existing_link.event_id) if existing_link else None

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    if event is None:
        event = models.Event(
            event_code=_event_code(db),
            event_type=event_type,
            title=f"{event_type} — {city or 'Unknown Location'}",
            latitude=lat, longitude=lng, city=city, state=state,
            start_time=now,
            timeline=[{"time": now.isoformat(), "label": "Event created by fusion engine"}],
        )
        db.add(event)
        db.flush()
    else:
        event.event_type = event_type
        event.title = f"{event_type} — {city or event.city or 'Unknown Location'}"
        timeline = list(event.timeline or [])
        timeline.append({"time": now.isoformat(), "label": f"Fusion updated ({len(reports)} reports in cluster)"})
        event.timeline = timeline

    # Recomputed on every fusion call (not just at creation) — a stale
    # description showing the report count from the event's first fusion
    # pass while report_count elsewhere had already grown to 99 was found
    # live during the audit's golden-path run.
    event.description = (
        f"{len(reports)} reports fused from {distinct_sources} independent sources "
        f"near {city or 'an unresolved location'}, {state or ''}."
    )

    event.severity = severity
    event.severity_reasons = reasons
    event.confidence = confidence
    event.fusion_breakdown = breakdown
    event.affected_area_km2 = round(3.14159 * (spread_km / 2) ** 2, 1) if spread_km else None
    event.report_count = len(reports)
    event.independent_source_count = distinct_sources
    event.evidence_count = len(reports) + len(weather_obs) + total_media
    event.last_updated = now

    if event.verification_status == "UNVERIFIED" and confidence >= 0.6:
        event.verification_status = "PROBABLE"
    elif event.verification_status == "UNVERIFIED" and confidence >= config.FUSION_MIN_CONFIDENCE_FOR_EVENT:
        event.verification_status = "UNDER_REVIEW"

    db.flush()

    # Link reports to event (idempotent)
    existing_report_ids = {er.report_id for er in event.event_reports}
    for r in reports:
        if r.id not in existing_report_ids:
            db.add(models.EventReport(event_id=event.id, report_id=r.id))
        r.processing_status = "FUSED"

    db.commit()
    store = get_spatial_store()
    store.sync_event_geom(db, event.id, event.latitude, event.longitude)
    db.commit()
    db.refresh(event)
    return event
