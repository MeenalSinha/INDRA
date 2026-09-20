"""
ML pipeline unit tests — updated to use the new AI provider registry
instead of the deleted app.ml module.
"""
import pytest
import asyncio
import datetime as dt

from app.ai.providers.text_classifier import RuleBasedTextClassifier
from app.ai.providers.duplicate_detector import DefaultDuplicateDetector
from app.ai.providers.trust_assessor import DefaultTrustAssessor
from app.geo.clustering import cluster_reports
from app.fusion.severity import compute_severity


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

class FakeReport:
    def __init__(self, id, text, lat, lng, ts, source_name="test"):
        self.id = id
        self.text = text
        self.latitude = lat
        self.longitude = lng
        self.timestamp = ts
        self.source_name = source_name


# --------------------------------------------------------------------------- #
# Text classifier                                                               #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_classifier_flood():
    c = RuleBasedTextClassifier()
    r = await c.predict("Roads completely flooded after 3 hours of heavy rain", [])
    assert r.prediction == "Urban Flooding"
    assert 0 < r.confidence <= 1


@pytest.mark.asyncio
async def test_classifier_fog():
    c = RuleBasedTextClassifier()
    r = await c.predict("Dense fog reducing visibility on the highway", [])
    assert r.prediction == "Fog"


@pytest.mark.asyncio
async def test_classifier_unknown_defaults_other():
    c = RuleBasedTextClassifier()
    r = await c.predict("Just a normal sunny day, nothing unusual", [])
    assert r.prediction == "Other"


# --------------------------------------------------------------------------- #
# Duplicate detection                                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_duplicate_detection_close_reports():
    t0 = dt.datetime.utcnow()
    reports = [
        FakeReport(1, "Heavy rain flooding roads near Gandhi Maidan", 25.594, 85.137, t0),
        FakeReport(2, "Heavy rain flooding roads near Gandhi Maidan", 25.595, 85.138, t0 + dt.timedelta(minutes=5)),
    ]
    detector = DefaultDuplicateDetector()
    dups = await detector.find_duplicates(reports)
    assert len(dups) == 1
    assert dups[0]["report_id"] == 2


@pytest.mark.asyncio
async def test_duplicate_detection_far_apart_not_duplicate():
    t0 = dt.datetime.utcnow()
    reports = [
        FakeReport(1, "Heavy rain flooding roads", 25.594, 85.137, t0),
        FakeReport(2, "Heavy rain flooding roads", 19.076, 72.877, t0),  # Mumbai
    ]
    detector = DefaultDuplicateDetector()
    dups = await detector.find_duplicates(reports)
    assert len(dups) == 0


# --------------------------------------------------------------------------- #
# Geo clustering                                                               #
# --------------------------------------------------------------------------- #

def test_clustering_groups_nearby_points():
    class R:
        def __init__(self, id, lat, lng):
            self.id, self.latitude, self.longitude = id, lat, lng
    reports = [R(1, 25.594, 85.137), R(2, 25.595, 85.138), R(3, 19.076, 72.877)]
    clusters = cluster_reports(reports)
    labels = {}
    for label, ids in clusters.items():
        for rid in ids:
            labels[rid] = label
    assert labels[1] == labels[2]
    assert labels[3] != labels[1]


# --------------------------------------------------------------------------- #
# Source reliability / trust assessor                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_source_reliability_government_high_trust():
    assessor = DefaultTrustAssessor()
    result = await assessor.predict("government", verification_history_count=50, metadata_completeness=0.9)
    assert result.confidence > 0.6
    assert result.prediction in ("HIGH TRUST", "MEDIUM TRUST")


# --------------------------------------------------------------------------- #
# Severity                                                                     #
# --------------------------------------------------------------------------- #

def test_severity_critical_for_large_flood():
    severity, reasons = compute_severity(
        event_type="Urban Flooding", report_count=120, spatial_spread_km=6,
        has_weather_anomaly=True, independent_source_count=10, confidence=0.9,
        has_image_evidence=True,
    )
    assert severity == "CRITICAL"
    assert len(reasons) > 0
