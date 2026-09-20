import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_events_nearby_radius_search():
    r = client.get("/api/v1/events/nearby", params={"lat": 25.5941, "lng": 85.1376, "radius_km": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(e["city"] == "Patna" for e in body["items"])


def test_events_nearby_excludes_far_away():
    r = client.get("/api/v1/events/nearby", params={"lat": 25.5941, "lng": 85.1376, "radius_km": 5})
    body = r.json()
    assert all(e["city"] != "Mumbai" for e in body["items"])


def test_events_bbox_search():
    r = client.get("/api/v1/events/bbox", params={"min_lat": 24, "max_lat": 27, "min_lng": 84, "max_lng": 87})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_events_date_filter():
    r = client.get("/api/v1/events", params={"date_from": "2020-01-01T00:00:00"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_reports_duplicate_status_filter():
    r = client.get("/api/v1/reports", params={"duplicate_status": "UNIQUE"})
    assert r.status_code == 200


def test_media_upload_rejects_bad_content_type():
    r = client.post(
        "/api/v1/media/upload",
        files={"file": ("evil.exe", io.BytesIO(b"not an image"), "application/x-msdownload")},
    )
    assert r.status_code == 415


def test_media_upload_accepts_image():
    r = client.post(
        "/api/v1/media/upload",
        files={"file": ("flood.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fakejpegbytes"), "image/jpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["media_url"].startswith("/media/")
    assert "detected_category" in body


def test_media_upload_rejects_empty_file():
    r = client.post(
        "/api/v1/media/upload",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert r.status_code == 400


def test_health_reports_observability_metrics():
    r = client.get("/api/v1/health")
    body = r.json()
    for key in ("reports_per_min", "events_per_min", "avg_processing_latency_ms", "stream_queue_depth"):
        assert key in body


def test_admin_token_not_required_by_default():
    # REQUIRE_ADMIN_TOKEN defaults to false -- admin actions work with no header.
    events = client.get("/api/v1/events").json()["items"]
    target = next(e for e in events if e["verification_status"] not in ("VERIFIED", "REJECTED"))
    r = client.post(f"/api/v1/events/{target['id']}/escalate", json={"reason": "test"})
    assert r.status_code == 200


def test_rate_limit_headers_do_not_break_normal_traffic():
    for _ in range(5):
        r = client.get("/api/v1/health")
        assert r.status_code == 200


def test_jwt_login_and_role_enforcement(monkeypatch):
    """JWT auth is additive and off by default; when REQUIRE_JWT_AUTH is
    enabled, only ADMIN-role tokens can verify an event, and login with
    the wrong password is rejected."""
    from app.security import jwt_auth
    from app.core import config as config_module

    # wrong password
    assert jwt_auth.authenticate("admin", "wrong-password") is None
    # correct password issues a real, decodable token with the right role
    result = jwt_auth.authenticate("admin", jwt_auth.DEMO_USERS["admin"]["password"])
    assert result is not None
    assert result["role"] == "ADMIN"
    decoded = jwt_auth.decode_token(result["access_token"])
    assert decoded["role"] == "ADMIN"

    viewer_result = jwt_auth.authenticate("viewer", jwt_auth.DEMO_USERS["viewer"]["password"])
    assert viewer_result["role"] == "VIEWER"

    monkeypatch.setattr(config_module, "REQUIRE_JWT_AUTH", True)
    dependency = jwt_auth.require_role("ADMIN")

    # no token -> rejected
    with pytest.raises(Exception):
        dependency(authorization=None)
    # viewer token -> rejected (below ADMIN)
    with pytest.raises(Exception):
        dependency(authorization=f"Bearer {viewer_result['access_token']}")
    # admin token -> allowed
    assert dependency(authorization=f"Bearer {result['access_token']}") is True


def test_login_endpoint_live():
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

    from app.security.jwt_auth import DEMO_USERS
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": DEMO_USERS["admin"]["password"]})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "ADMIN"
    assert "access_token" in body


def test_demo_credentials_endpoint():
    r = client.get("/api/v1/auth/demo-credentials")
    assert r.status_code == 200
    roles = {a["role"] for a in r.json()["accounts"]}
    assert roles == {"ADMIN", "ANALYST", "VIEWER"}

