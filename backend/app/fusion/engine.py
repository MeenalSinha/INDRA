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
"""
import datetime as dt
from collections import Counter

from .. import config, models
from ..geo.utils import haversine_km
from ..geo.postgis import sync_event_geom
from ..ml.embeddings import pairwise_similarity
from ..ml.reliability import score_source
from .severity import compute_severity

WEIGHTS = {
    "semantic_similarity": 0.20,
    "geo_proximity": 0.20,
    "time_proximity": 0.15,
    "weather_agreement": 0.20,
    "source_reliability": 0.10,
    "independent_evidence": 0.15,
}


def _event_code(db):
    count = db.query(models.Event).count()
    return f"EVT-{1000 + count + 1}"


def _spatial_spread_km(reports):
    pts = [(r.latitude, r.longitude) for r in reports if r.latitude is not None]
    if len(pts) < 2:
        return 0.0
    max_d = 0.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            max_d = max(max_d, haversine_km(*pts[i], *pts[j]))
    return max_d


def fuse_cluster(db, report_ids: list[int], weather_obs: list[models.WeatherObservation] | None = None):
    """
    Fuse a cluster of reports into a single Event (creating or updating it).
    Returns the Event ORM object.
    """
    reports = db.query(models.Report).filter(models.Report.id.in_(report_ids)).all()
    if not reports:
        return None
    weather_obs = weather_obs or []

    # --- semantic similarity: mean pairwise cosine similarity of text ----
    texts = [r.text or "" for r in reports]
    if len(texts) >= 2:
        sim_matrix = pairwise_similarity(texts)
        vals = [sim_matrix[i][j] for i in range(len(texts)) for j in range(i + 1, len(texts))]
        semantic_similarity = sum(vals) / len(vals) if vals else 0.5
    else:
        semantic_similarity = 0.6  # single report: neutral-ish, more evidence needed

    # --- geo proximity: tighter cluster => higher score ------------------
    spread_km = _spatial_spread_km(reports)
    geo_proximity = max(0.1, min(1.0, 1 - (spread_km / (config.CLUSTER_EPS_KM * 2))))

    # --- time proximity ----------------------------------------------------
    timestamps = [r.timestamp for r in reports]
    time_spread_min = (max(timestamps) - min(timestamps)).total_seconds() / 60.0 if len(timestamps) > 1 else 0
    time_proximity = max(0.1, min(1.0, 1 - (time_spread_min / (config.DUPLICATE_TIME_WINDOW_MIN * 3))))

    # --- weather agreement: any anomalous nearby observation? -------------
    anomaly_hits = [w for w in weather_obs if w.is_anomaly]
    weather_agreement = 0.9 if anomaly_hits else (0.55 if weather_obs else 0.35)

    # --- source reliability: average across contributing sources ----------
    reliability_scores = []
    for r in reports:
        s, _ = score_source(
            r.source_type or "citizen",
            verification_history_count=0,
            metadata_completeness=0.8 if (r.latitude and r.text) else 0.4,
        )
        reliability_scores.append(s)
    source_reliability = sum(reliability_scores) / len(reliability_scores) if reliability_scores else 0.5

    # --- independent evidence: distinct sources + media -------------------
    distinct_sources = len({r.source_name for r in reports if r.source_name})
    media_count = sum(len(r.media_items) for r in reports)
    independent_evidence = min(1.0, 0.10 * distinct_sources + 0.05 * media_count + 0.05 * len(reports))
    independent_evidence = max(0.2, independent_evidence)

    breakdown = {
        "semantic_similarity": round(semantic_similarity, 2),
        "geo_proximity": round(geo_proximity, 2),
        "time_proximity": round(time_proximity, 2),
        "weather_agreement": round(weather_agreement, 2),
        "source_reliability": round(source_reliability, 2),
        "independent_evidence": round(independent_evidence, 2),
    }
    confidence = round(sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS), 2)
    confidence = min(0.97, confidence)

    # --- majority event type -----------------------------------------------
    type_counts = Counter(r.event_type for r in reports if r.event_type)
    event_type = type_counts.most_common(1)[0][0] if type_counts else "Other"

    # --- centroid location ---------------------------------------------------
    lat_vals = [r.latitude for r in reports if r.latitude is not None]
    lng_vals = [r.longitude for r in reports if r.longitude is not None]
    lat = sum(lat_vals) / len(lat_vals) if lat_vals else None
    lng = sum(lng_vals) / len(lng_vals) if lng_vals else None
    city = Counter(r.city for r in reports if r.city).most_common(1)
    state = Counter(r.state for r in reports if r.state).most_common(1)
    city = city[0][0] if city else None
    state = state[0][0] if state else None

    severity, reasons = compute_severity(
        event_type=event_type,
        report_count=len(reports),
        spatial_spread_km=spread_km,
        has_weather_anomaly=bool(anomaly_hits),
        independent_source_count=distinct_sources,
        confidence=confidence,
        has_image_evidence=media_count > 0,
    )

    # --- find existing event already linked to any of these reports -------
    existing_link = (
        db.query(models.EventReport)
        .filter(models.EventReport.report_id.in_([r.id for r in reports]))
        .first()
    )
    event = db.query(models.Event).get(existing_link.event_id) if existing_link else None

    now = dt.datetime.utcnow()
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

    # Recomputed on every fusion call (not just at creation) -- a stale
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
    event.evidence_count = len(reports) + len(weather_obs) + media_count
    event.last_updated = now
    if event.verification_status == "UNVERIFIED" and confidence >= 0.6:
        event.verification_status = "PROBABLE"
    elif event.verification_status == "UNVERIFIED" and confidence >= config.FUSION_MIN_CONFIDENCE_FOR_EVENT:
        event.verification_status = "UNDER_REVIEW"

    db.flush()

    # link reports to event (idempotent)
    existing_report_ids = {er.report_id for er in event.event_reports}
    for r in reports:
        if r.id not in existing_report_ids:
            db.add(models.EventReport(event_id=event.id, report_id=r.id))
        r.processing_status = "FUSED"

    db.commit()
    sync_event_geom(db, event.id, event.latitude, event.longitude)
    db.commit()
    db.refresh(event)
    return event
