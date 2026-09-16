import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["api"] == "ONLINE"


def test_seed_data_present(client):
    r = client.get("/api/events")
    assert r.status_code == 200
    assert r.json()["total"] >= 9


def test_dashboard_summary(client):
    r = client.get("/api/analytics/summary")
    assert r.status_code == 200
    body = r.json()
    assert "total_reports" in body and "verified_events" in body


def test_single_live_report_classifies_but_does_not_yet_fuse(client):
    """A lone new report (no live corroborating neighbors yet) should be
    classified but NOT immediately spawn an event -- fusion requires
    multiple independent reports (CLUSTER_MIN_SAMPLES=2), matching the
    core "MULTIPLE REPORTS -> ONE EVENT" premise. It must also not
    silently piggyback onto old seeded historical data at the same
    coordinates (see models.py Report.is_seed_data)."""
    payload = {
        "source": "Citizen Reporter App", "source_type": "citizen",
        "text": "Isolated report: light drizzle near Rajendra Nagar, Patna",
        "city": "Patna", "state": "Bihar", "hashtags": [],
    }
    r = client.post("/api/reports", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["event_type"] in ("Heavy Rainfall", "Other")
    assert body["event_id"] is None


def test_multiple_similar_reports_fuse_into_one_new_event(client):
    """The golden-path guarantee: several independent reports describing
    the same event, close in space/time, fuse into exactly ONE new event
    -- distinct from any pre-existing seeded event at the same location."""
    texts = [
        "Heavy rain flooding roads near Gandhi Maidan, Patna, water entering shops",
        "Complete waterlogging and flooding reported near Gandhi Maidan, Patna",
        "Flood water entering shops near Gandhi Maidan, Patna",
    ]
    event_ids = []
    for i, text in enumerate(texts):
        payload = {
            "source": "Citizen Reporter App" if i % 2 == 0 else "Social Media Monitor",
            "source_type": "citizen" if i % 2 == 0 else "social",
            "text": text, "city": "Patna", "state": "Bihar",
            "latitude": 25.601 + i * 0.001, "longitude": 85.145 + i * 0.001,
        }
        r = client.post("/api/reports", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["event_type"] == "Urban Flooding"
        event_ids.append(body["event_id"])

    # first report alone: no event yet; once the 2nd+3rd corroborate, all
    # three converge on the same freshly-created event
    assert event_ids[0] is None
    assert event_ids[1] is not None
    assert event_ids[1] == event_ids[2]

    seeded_patna_event = next(e for e in client.get("/api/events").json()["items"] if e["event_code"] == "EVT-1001")
    assert event_ids[1] != seeded_patna_event["id"], "live reports must not merge into the pre-seeded/already-verified Patna event"

    new_event = client.get(f"/api/events/{event_ids[1]}").json()
    assert new_event["verification_status"] in ("UNVERIFIED", "UNDER_REVIEW", "PROBABLE")
    assert new_event["report_count"] >= 2

    # and the admin-verification action is genuinely available (not
    # already pre-verified from seed data)
    verify = client.post(f"/api/events/{event_ids[1]}/verify", json={"reason": "confirmed by field team"})
    assert verify.status_code == 200
    assert verify.json()["verification_status"] == "VERIFIED"


def test_alert_fires_once_on_transition_to_critical_not_every_update(client):
    """Regression test for a real bug found during the audit: repeatedly
    fusing more reports into an event that is already CRITICAL must NOT
    create a new alert every time -- only the transition into CRITICAL
    should fire one."""
    base_payload = dict(
        source="Citizen Reporter App", source_type="citizen",
        city="Mumbai", state="Maharashtra", latitude=19.09, longitude=72.90,
    )
    texts = [
        "Severe cyclone damage reported near Marine Drive, Mumbai, strong winds",
        "Cyclonic winds uprooting trees near Marine Drive, Mumbai",
        "Storm surge and cyclone warning in effect near Marine Drive, Mumbai",
        "Cyclone intensifying near Marine Drive, Mumbai, widespread damage",
        "Coastal cyclone landfall confirmed near Marine Drive, Mumbai",
        "Cyclone continues near Marine Drive, Mumbai, more reports coming in",
    ]
    event_id = None
    for i, text in enumerate(texts):
        r = client.post("/api/reports", json={**base_payload, "text": text,
                                                "latitude": 19.09 + i * 0.0005, "longitude": 72.90 + i * 0.0005})
        body = r.json()
        if body["event_id"]:
            event_id = body["event_id"]

    assert event_id is not None
    event = client.get(f"/api/events/{event_id}").json()

    alerts = client.get("/api/alerts", params={"level": "CRITICAL"}).json()["items"]
    matching = [a for a in alerts if a["event_id"] == event_id]
    if event["severity"] == "CRITICAL":
        assert len(matching) == 1, f"expected exactly one CRITICAL alert for one event, got {len(matching)}"
    else:
        assert len(matching) == 0


def test_event_description_stays_in_sync_with_report_count(client):
    """Regression test for a real bug found during the audit: description
    was only ever set at event creation time and never refreshed, so it
    kept saying "2 reports" while report_count had grown to 99."""
    base_payload = dict(source="Citizen Reporter App", source_type="citizen", city="Chennai", state="Tamil Nadu")
    texts = [
        "Heavy rainfall flooding streets near Marina Beach, Chennai",
        "Continuous heavy rainfall in Chennai, roads waterlogged near Marina Beach",
        "Marina Beach area Chennai reports heavy rainfall and flooding",
        "More heavy rainfall reports pouring in from Marina Beach, Chennai",
    ]
    event_id = None
    for i, text in enumerate(texts):
        r = client.post("/api/reports", json={**base_payload, "text": text,
                                                "latitude": 13.05 + i * 0.001, "longitude": 80.28 + i * 0.001})
        body = r.json()
        if body["event_id"]:
            event_id = body["event_id"]

    assert event_id is not None
    event = client.get(f"/api/events/{event_id}").json()
    assert str(event["report_count"]) in event["description"], (
        f"description ({event['description']!r}) does not mention the current report_count ({event['report_count']})"
    )


def test_verification_workflow_end_to_end(client):
    events = client.get("/api/events").json()["items"]
    target = next(e for e in events if e["verification_status"] in ("UNDER_REVIEW", "PROBABLE"))
    r = client.post(f"/api/events/{target['id']}/verify", json={"admin_name": "Test Admin", "reason": "confirmed"})
    assert r.status_code == 200
    assert r.json()["verification_status"] == "VERIFIED"
    audit = client.get("/api/audit-logs").json()["items"]
    assert any(a["action"] == "VERIFY" for a in audit)


def test_reject_workflow(client):
    events = client.get("/api/events").json()["items"]
    target = next(e for e in events if e["verification_status"] not in ("VERIFIED", "REJECTED"))
    r = client.post(f"/api/events/{target['id']}/reject", json={"admin_name": "Test Admin", "reason": "insufficient evidence"})
    assert r.status_code == 200
    assert r.json()["verification_status"] == "REJECTED"


def test_mark_report_duplicate(client):
    reports = client.get("/api/reports?limit=2").json()["items"]
    r = client.post(f"/api/reports/{reports[1]['id']}/duplicate", json={"duplicate_of": reports[0]["id"]})
    assert r.status_code == 200
    assert r.json()["duplicate_status"] == "LIKELY_DUPLICATE"


def test_demo_mode_lifecycle(client):
    r = client.post("/api/demo/start")
    assert r.status_code == 200
    status = client.get("/api/demo/status").json()
    assert "running" in status
    r = client.post("/api/demo/reset")
    assert r.status_code == 200


def test_search(client):
    r = client.get("/api/search", params={"q": "Patna"})
    assert r.status_code == 200
    assert "events" in r.json()
