"""
Tests for §6 (Users Table + RBAC) and §7 (Email delivery).

These tests run against a fresh in-memory SQLite DB via the same TestClient
fixture as the existing suite — no external services needed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine

client = TestClient(app)


# --------------------------------------------------------------------------
# §6 User management
# --------------------------------------------------------------------------

def test_demo_users_seeded_in_database():
    """Users table is seeded from DEMO_* env vars on startup."""
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        assert admin is not None, "admin user not found in DB"
        assert admin.role == "ADMIN"
        analyst = db.query(models.User).filter(models.User.username == "analyst").first()
        assert analyst is not None
        assert analyst.role == "ANALYST"
        viewer = db.query(models.User).filter(models.User.username == "viewer").first()
        assert viewer is not None
        assert viewer.role == "VIEWER"
    finally:
        db.close()


def test_login_checks_database_user():
    """POST /api/auth/login returns a JWT when credentials match the DB."""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "indra-admin-demo"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["role"] == "ADMIN"


def test_wrong_password_rejected():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert r.status_code == 401


def test_create_user_endpoint_requires_admin_role(monkeypatch):
    """POST /api/auth/users is ADMIN-only when REQUIRE_JWT_AUTH=true."""
    from app import config as cfg
    monkeypatch.setattr(cfg, "REQUIRE_JWT_AUTH", True)

    # Viewer token should be rejected (403)
    viewer_token = client.post(
        "/api/auth/login", json={"username": "viewer", "password": "indra-viewer-demo"}
    ).json()["access_token"]

    r = client.post(
        "/api/auth/users",
        json={"username": "newuser", "password": "newpass123", "role": "ANALYST"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403


def test_create_user_and_login():
    """Admin can create a new user; new user can log in immediately."""
    # Create via API (admin token header, REQUIRE_ADMIN_TOKEN=false by default)
    r = client.post(
        "/api/auth/users",
        json={"username": "testanalyst_u6", "password": "t3stP@ssw0rd!", "role": "ANALYST"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "testanalyst_u6"
    assert body["role"] == "ANALYST"

    # New user can now log in
    r2 = client.post(
        "/api/auth/login", json={"username": "testanalyst_u6", "password": "t3stP@ssw0rd!"}
    )
    assert r2.status_code == 200
    assert r2.json()["role"] == "ANALYST"


def test_create_user_duplicate_rejected():
    """Creating an account with an existing username returns 409."""
    r = client.post(
        "/api/auth/users",
        json={"username": "admin", "password": "somepass", "role": "ANALYST"},
    )
    assert r.status_code == 409


def test_create_user_invalid_role():
    """Invalid role returns 422."""
    r = client.post(
        "/api/auth/users",
        json={"username": "badroleu6", "password": "pass", "role": "SUPERUSER"},
    )
    assert r.status_code == 422


def test_list_users_endpoint():
    """GET /api/auth/users returns all accounts, no password field."""
    r = client.get("/api/auth/users")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(u["username"] == "admin" for u in items)
    # Passwords must not be returned
    for item in items:
        assert "hashed_password" not in item
        assert "password" not in item


# --------------------------------------------------------------------------
# §7 Email delivery
# --------------------------------------------------------------------------

def test_email_delivery_skips_when_disabled():
    """send_alert_email() returns False and never raises when env var is off."""
    from app.notifications.email import send_alert_email
    result = send_alert_email("Test subject", "Test body — not sent")
    # Default: ALERT_EMAIL_ENABLED=false → skips silently
    assert result is False


def test_email_delivery_warns_on_incomplete_config(monkeypatch):
    """Returns False (not raises) if ENABLED but SMTP host missing."""
    import app.notifications.email as mail_mod
    monkeypatch.setattr(mail_mod, "_ENABLED", True)
    monkeypatch.setattr(mail_mod, "_SMTP_HOST", "")
    result = mail_mod.send_alert_email("Subject", "Body")
    assert result is False


def test_critical_alert_email_convenience_wrapper():
    """send_critical_alert_email() returns False gracefully in disabled state."""
    from app.notifications.email import send_critical_alert_email
    result = send_critical_alert_email("Patna Flood", 12, 0.87)
    assert result is False  # disabled in test env, never raises
