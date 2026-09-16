from app.ml.classifier import predict
from app.ml.duplicate import find_duplicates
from app.geo.clustering import cluster_reports
from app.ml.reliability import predict as score_source
from app.fusion.severity import compute_severity


def test_classifier_flood():
    result = predict("Roads completely flooded after 3 hours of heavy rain")
    event_type, confidence = result["category"], result["confidence"]
    assert event_type == "Urban Flooding"
    assert 0 < confidence <= 1


def test_classifier_fog():
    result = predict("Dense fog reducing visibility on the highway")
    event_type, confidence = result["category"], result["confidence"]
    assert event_type == "Fog"


def test_classifier_unknown_defaults_other():
    result = predict("Just a normal sunny day, nothing unusual")
    event_type, confidence = result["category"], result["confidence"]
    assert event_type == "Other"


class FakeReport:
    def __init__(self, id, text, lat, lng, ts):
        self.id, self.text, self.latitude, self.longitude, self.timestamp = id, text, lat, lng, ts


def test_duplicate_detection_close_reports():
    import datetime as dt
    t0 = dt.datetime.utcnow()
    reports = [
        FakeReport(1, "Heavy rain flooding roads near Gandhi Maidan", 25.594, 85.137, t0),
        FakeReport(2, "Heavy rain flooding roads near Gandhi Maidan", 25.595, 85.138, t0 + dt.timedelta(minutes=5)),
    ]
    dups = find_duplicates(reports)
    assert len(dups) == 1
    assert dups[0]["report_id"] == 2


def test_duplicate_detection_far_apart_not_duplicate():
    import datetime as dt
    t0 = dt.datetime.utcnow()
    reports = [
        FakeReport(1, "Heavy rain flooding roads", 25.594, 85.137, t0),
        FakeReport(2, "Heavy rain flooding roads", 19.076, 72.877, t0),  # Mumbai, far away
    ]
    dups = find_duplicates(reports)
    assert len(dups) == 0


def test_clustering_groups_nearby_points():
    class R:
        def __init__(self, id, lat, lng):
            self.id, self.latitude, self.longitude = id, lat, lng
    reports = [R(1, 25.594, 85.137), R(2, 25.595, 85.138), R(3, 19.076, 72.877)]
    clusters = cluster_reports(reports)
    # the two Patna points should share a cluster label, distinct from Mumbai
    labels = {}
    for label, ids in clusters.items():
        for rid in ids:
            labels[rid] = label
    assert labels[1] == labels[2]
    assert labels[3] != labels[1]


def test_source_reliability_government_high_trust():
    result = score_source("government", verification_history_count=50, metadata_completeness=0.9)
    score, trust = result["score"], result["trust_level"]
    assert score > 0.6
    assert trust in ("HIGH TRUST", "MEDIUM TRUST")


def test_severity_critical_for_large_flood():
    severity, reasons = compute_severity(
        event_type="Urban Flooding", report_count=120, spatial_spread_km=6,
        has_weather_anomaly=True, independent_source_count=10, confidence=0.9,
        has_image_evidence=True,
    )
    assert severity == "CRITICAL"
    assert len(reasons) > 0
