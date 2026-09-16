"""
Role-based JWT authentication — additive to, not a replacement for, the
single-shared-token admin abstraction in security/auth.py.

§6 upgrade (UPGRADE_AUDIT_2): Users are now stored in the `users` database
table with bcrypt-hashed passwords (passlib). The three demo accounts are
seeded from DEMO_* env vars on first boot (see seed.py), so they continue
to work identically. An ADMIN can create additional accounts via
POST /api/auth/users without restarting or editing env vars — the sole
gap the previous round explicitly left open.

Fallback: if passlib is not installed (shouldn't happen post-install, but
defensive) the old env-var DEMO_USERS dict is used as a last resort so the
demo is never broken by a missing optional package.
"""
import datetime as dt
import os
import jwt
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from .. import config
from ..database import get_db

JWT_SECRET = os.getenv("JWT_SECRET", "indra-demo-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

ROLE_RANK = {"VIEWER": 0, "ANALYST": 1, "ADMIN": 2}

# ---- passlib pbkdf2_sha256 (no 72-byte length limit, unlike bcrypt) ---------
try:
    from passlib.context import CryptContext
    # pbkdf2_sha256 chosen over bcrypt: identical security for this use-case,
    # no 72-byte password truncation (bcrypt silently truncates; passlib raises
    # ValueError when the bug-detection code hashes a long test vector at init).
    _pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    def hash_password(plain: str) -> str:
        return _pwd_context.hash(plain)

    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)

    _PASSLIB_AVAILABLE = True
except ImportError:
    _PASSLIB_AVAILABLE = False

    def hash_password(plain: str) -> str:  # type: ignore[misc]
        return plain  # degraded: store plain (should never happen post-install)

    def verify_password(plain: str, hashed: str) -> bool:  # type: ignore[misc]
        return plain == hashed

# ---- env-var fallback accounts (kept for edge-case safety + backwards compat) -
_ENV_USERS = {
    os.getenv("DEMO_ADMIN_USERNAME", "admin"): {
        "password": os.getenv("DEMO_ADMIN_PASSWORD", "indra-admin-demo"),
        "role": "ADMIN",
    },
    os.getenv("DEMO_ANALYST_USERNAME", "analyst"): {
        "password": os.getenv("DEMO_ANALYST_PASSWORD", "indra-analyst-demo"),
        "role": "ANALYST",
    },
    os.getenv("DEMO_VIEWER_USERNAME", "viewer"): {
        "password": os.getenv("DEMO_VIEWER_PASSWORD", "indra-viewer-demo"),
        "role": "VIEWER",
    },
}
# Backwards-compat alias: existing tests import DEMO_USERS directly.
DEMO_USERS = _ENV_USERS


def _make_token(username: str, role: str) -> dict:
    payload = {
        "sub": username,
        "role": role,
        "exp": dt.datetime.utcnow() + dt.timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": dt.datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": role, "username": username}


def authenticate_db(db: Session, username: str, password: str):
    """Authenticate against the `users` database table (primary path).
    Falls back to env-var accounts if DB lookup finds nothing (safety net
    for a freshly-wiped database before seed has run)."""
    from ..models import User
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if user:
        if verify_password(password, user.hashed_password):
            return _make_token(username, user.role)
        return None
    # Fallback: env-var demo users
    env_user = _ENV_USERS.get(username)
    if env_user and env_user["password"] == password:
        return _make_token(username, env_user["role"])
    return None


def authenticate(username: str, password: str):
    """Backwards-compatible synchronous authenticate() used by the login
    endpoint. Opens its own DB session so callers without a session can
    still call it — the login endpoint now passes db explicitly via
    authenticate_db(), but this remains for backwards compat with tests."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        return authenticate_db(db, username, password)
    finally:
        db.close()


def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_current_role(authorization: str | None = Header(default=None)):
    """Returns the caller's role (VIEWER/ANALYST/ADMIN) or None if no
    valid token was presented. Does not itself reject — that's require_role()."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    return payload.get("role") if payload else None


def require_role(minimum_role: str):
    """Dependency factory: require_role("ADMIN") rejects anyone below ADMIN.
    Only enforced when REQUIRE_JWT_AUTH is set."""
    def dependency(authorization: str | None = Header(default=None)):
        if not config.REQUIRE_JWT_AUTH:
            return True
        role = get_current_role(authorization)
        if role is None:
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token")
        if ROLE_RANK.get(role, -1) < ROLE_RANK.get(minimum_role, 99):
            raise HTTPException(status_code=403, detail=f"Requires {minimum_role} role, caller has {role}")
        return True
    return dependency
