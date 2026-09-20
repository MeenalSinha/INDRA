"""
IngestionService — orchestrates the full report ingestion pipeline.

Each stage is a named, independently-testable method:

    _persist_report()      save raw report + sync PostGIS geometry
    _classify()            AI event-type classification
    _analyze_media()       image / media evidence analysis
    _detect_duplicates()   TF-IDF duplicate detection against recent nearby
    _cluster_and_fuse()    spatial DBSCAN + fusion engine call
    _dispatch_alerts()     pubsub, alert creation, email/SMS/push notifications

The public entry point `run()` chains them in order and returns the Report.

`ingest_report()` in ingestion/adapters.py delegates here — all existing
callers continue to work without modification.
"""
import datetime as dt
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..core import config
from ..geo import clustering
from ..geo.registry import get_spatial_store
from ..fusion import engine as fusion_engine
from ..ai.registry import (
    get_text_classifier,
    get_image_analyzer,
    get_duplicate_detector
)
from ..realtime import pubsub


class IngestionService:
    # ------------------------------------------------------------------ #
    # Public entry point                                                  #
    # ------------------------------------------------------------------ #

    async def run(self, db: Session, raw_payload: dict, broadcast: bool = True) -> models.Report:
        """
        Full pipeline: normalize → persist → classify → media → dedup →
        cluster → fuse → alert dispatch.

        `raw_payload` must already be normalized (call normalize_payload
        from adapters.py first, as adapters.ingest_report does).
        """
        report, source_name, source_type = await self._persist_report(db, raw_payload, broadcast)
        event_type = await self._classify(db, report, broadcast)
        await self._analyze_media(db, report, raw_payload)
        await self._detect_duplicates(db, report, event_type, broadcast)
        event = await self._cluster_and_fuse(db, report, event_type)
        await self._dispatch_alerts(db, report, event, broadcast)
        db.commit()
        db.refresh(report)
        return report

    # ------------------------------------------------------------------ #
    # Stage 1 — Persist raw report                                        #
    # ------------------------------------------------------------------ #

    async def _persist_report(
        self, db: Session, payload: dict, broadcast: bool
    ) -> tuple[models.Report, str, str]:
        from ..ingestion.adapters import get_or_create_source  # local import avoids circularity

        source_name = payload.get("source", "Unknown Source")
        source_type = payload.get("source_type", "citizen")
        source = get_or_create_source(db, source_name, source_type)

        report = models.Report(
            source_id=source.id,
            source_name=source_name,
            source_type=source_type,
            source_ref_id=str(payload.get("source_id", "")),
            text=payload.get("text", ""),
            timestamp=payload["timestamp"],
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            city=payload.get("city"),
            state=payload.get("state"),
            hashtags=payload.get("hashtags", []),
            raw_metadata=payload.get("metadata", {}),
            processing_status="PROCESSING",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        store = get_spatial_store()
        store.sync_report_geom(db, report.id, report.latitude, report.longitude)
        db.commit()

        if broadcast:
            await pubsub.publish("report.received", {
                "report_id": report.id, "source": source_name, "source_type": source_type,
                "text": report.text, "city": report.city, "state": report.state,
                "timestamp": report.timestamp.isoformat(),
            })

        return report, source_name, source_type

    # ------------------------------------------------------------------ #
    # Stage 2 — AI classification                                         #
    # ------------------------------------------------------------------ #

    async def _classify(self, db: Session, report: models.Report, broadcast: bool) -> str:
        classifier = get_text_classifier()
        result = await classifier.predict(report.text, report.hashtags)
        event_type = result.prediction
        confidence = result.confidence
        
        report.event_type = event_type
        report.classification_confidence = confidence
        report.processing_status = "ANALYZED"
        db.commit()

        if broadcast:
            await pubsub.publish("report.classified", {
                "report_id": report.id, "event_type": event_type, "confidence": confidence,
            })

        return event_type

    # ------------------------------------------------------------------ #
    # Stage 3 — Media / image analysis                                    #
    # ------------------------------------------------------------------ #

    async def _analyze_media(self, db: Session, report: models.Report, payload: dict) -> None:
        media_list = payload.get("media", [])
        # Backwards-compat: older payloads use a flat media_url string
        if not media_list and payload.get("media_url"):
            media_list = [payload.get("media_url")]

        for media_item in media_list:
            if isinstance(media_item, str):
                media_url, media_type = media_item, "image"
            else:
                media_url = media_item.get("url")
                media_type = media_item.get("type", "image")

            if media_url:
                analyzer = get_image_analyzer()
                result = await analyzer.analyze(None, media_type)
                
                db.add(models.Media(
                    report_id=report.id, 
                    media_url=media_url, 
                    media_type=media_type,
                    detected_category=result.prediction, 
                    analysis_confidence=result.confidence,
                    evidence_summary=result.metadata.get("evidence_summary", ""),
                ))

        db.commit()

    # ------------------------------------------------------------------ #
    # Stage 4 — Duplicate detection                                       #
    # ------------------------------------------------------------------ #

    async def _detect_duplicates(
        self, db: Session, report: models.Report, event_type: str, broadcast: bool
    ) -> None:
        window_start = report.timestamp - dt.timedelta(minutes=180)
        dup_query = (
            db.query(models.Report)
            .filter(models.Report.event_type == event_type)
            .filter(models.Report.timestamp >= window_start)
            .filter(models.Report.is_seed_data.is_(False))
        )
        if report.latitude is not None and report.longitude is not None:
            box_deg = config.DUPLICATE_RADIUS_KM * 2 / 111.0
            dup_query = (
                dup_query
                .filter(models.Report.latitude.between(
                    report.latitude - box_deg, report.latitude + box_deg))
                .filter(models.Report.longitude.between(
                    report.longitude - box_deg, report.longitude + box_deg))
            )
        nearby_recent = dup_query.all()
        
        detector = get_duplicate_detector()
        dup_results = await detector.find_duplicates(nearby_recent)

        for d in dup_results:
            r = db.get(models.Report, d["report_id"])  # SQLAlchemy 2.0 style
            if r and r.duplicate_status != "LIKELY_DUPLICATE":
                r.duplicate_status = "LIKELY_DUPLICATE"
                r.duplicate_of_report_id = d["duplicate_of"]
        db.commit()

        if dup_results and broadcast:
            await pubsub.publish("duplicates.detected", {"pairs": dup_results})

    # ------------------------------------------------------------------ #
    # Stage 5 — Geo clustering + fusion                                   #
    # ------------------------------------------------------------------ #

    async def _cluster_and_fuse(
        self, db: Session, report: models.Report, event_type: str
    ) -> Optional[models.Event]:
        """
        Narrow candidate pool with a spatial bounding-box pre-filter, run
        DBSCAN, then call fuse_cluster() for the cluster containing this report.

        The pre-filter + DBSCAN approach is the fix for the 17ms→140-220ms
        per-request latency regression found during the audit when nationwide
        same-type reports were fed to DBSCAN on every insert.
        """
        query = (
            db.query(models.Report)
            .filter(models.Report.event_type == event_type)
            .filter(models.Report.timestamp >= report.timestamp - dt.timedelta(hours=12))
            .filter(models.Report.is_seed_data.is_(False))
        )
        if report.latitude is not None and report.longitude is not None:
            box_deg = (config.CLUSTER_EPS_KM * 3) / 111.0
            query = (
                query
                .filter(models.Report.latitude.between(
                    report.latitude - box_deg, report.latitude + box_deg))
                .filter(models.Report.longitude.between(
                    report.longitude - box_deg, report.longitude + box_deg))
            )
        candidates = query.all()
        clusters = clustering.cluster_reports(candidates)

        this_report_cluster = None
        for label, ids in clusters.items():
            if label == -1:
                continue
            if report.id in ids:
                this_report_cluster = ids

        if not (this_report_cluster and len(this_report_cluster) >= 1):
            return None

        nearby_weather = []
        if report.city:
            nearby_weather = (
                db.query(models.WeatherObservation)
                .filter(models.WeatherObservation.city == report.city)
                .order_by(models.WeatherObservation.timestamp.desc())
                .limit(5).all()
            )

        return await fusion_engine.fuse_cluster(db, this_report_cluster, nearby_weather)

    # ------------------------------------------------------------------ #
    # Stage 6 — Alert dispatch                                            #
    # ------------------------------------------------------------------ #

    async def _dispatch_alerts(
        self,
        db: Session,
        report: models.Report,
        event: Optional[models.Event],
        broadcast: bool,
    ) -> None:
        if not (broadcast and event):
            return

        # Capture previous severity before fusion so we only alert on the
        # TRANSITION into CRITICAL, not on every subsequent update.
        # (See audit finding: a single growing event generated 60+ near-
        #  identical "Critical weather event" alerts as it grew 40→99 reports.)
        existing_link = (
            db.query(models.EventReport)
            .filter(models.EventReport.report_id.in_([report.id]))
            .first()
        )
        prior_severity = None
        if existing_link:
            prior_event = db.get(models.Event, existing_link.event_id)
            prior_severity = prior_event.severity if prior_event else None

        await pubsub.publish("event.updated", {
            "event_id": event.id, "event_code": event.event_code, "title": event.title,
            "severity": event.severity, "confidence": event.confidence,
            "verification_status": event.verification_status, "report_count": event.report_count,
        })

        severity_newly_critical = event.severity == "CRITICAL" and prior_severity != "CRITICAL"
        if not severity_newly_critical:
            return

        alert = models.Alert(
            event_id=event.id, level="CRITICAL",
            title=f"Critical weather event: {event.title}",
            message=f"{event.report_count} reports, {round(event.confidence * 100)}% confidence.",
        )
        db.add(alert)
        db.commit()

        await pubsub.publish("alert.created", {
            "event_id": event.id, "level": "CRITICAL",
            "title": alert.title, "message": alert.message,
        })

        # §7: multi-channel notification — gated by config flags, never raises
        try:
            from ..notifications.email import send_critical_alert_email
            from ..notifications.sms import send_critical_alert_sms
            from ..notifications.push import send_critical_alert_push

            send_critical_alert_email(event.title, event.report_count, event.confidence)
            send_critical_alert_sms(event.title, event.report_count)
            send_critical_alert_push(event.title)
        except Exception:
            pass  # notification failure must never break ingestion


# Module-level singleton — importable by adapters.py and any future callers
ingestion_service = IngestionService()
