from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..security.jwt_auth import authenticate, hash_password, require_role
from ..database import get_db
from .. import models
from ..security.auth import require_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])

VALID_ROLES = {"ADMIN", "ANALYST", "VIEWER"}


class LoginIn(BaseModel):
    username: str
    password: str


class CreateUserIn(BaseModel):
    username: str
    password: str
    role: str  # ADMIN, ANALYST, VIEWER


@router.post("/login")
def login(payload: LoginIn):
    result = authenticate(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return result


@router.post("/users")
def create_user(
    payload: CreateUserIn,
    db: Session = Depends(get_db),
    _admin: bool = Depends(require_admin),
    _role: bool = Depends(require_role("ADMIN")),
):
    """Create a new user account (ADMIN-only).

    §6 UPGRADE: admin can now create additional accounts via API without
    editing env vars or restarting the server. The three demo accounts
    seeded from DEMO_* env vars are unaffected.
    """
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {sorted(VALID_ROLES)}")
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
        "note": "Account created. Log in via POST /api/auth/login.",
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: bool = Depends(require_admin),
    _role: bool = Depends(require_role("ADMIN")),
):
    """List all user accounts (ADMIN-only). Passwords are never returned."""
    rows = db.query(models.User).all()
    return {"items": [
        {"id": u.id, "username": u.username, "role": u.role,
         "is_active": u.is_active, "created_at": u.created_at.isoformat()}
        for u in rows
    ]}


@router.get("/demo-credentials")
def demo_credentials():
    """Convenience endpoint for the demo — shows the three demo accounts."""
    import os
    return {
        "note": "Demo credentials only — override via DEMO_*_USERNAME/PASSWORD env vars for any real deployment.",
        "accounts": [
            {"username": os.getenv("DEMO_ADMIN_USERNAME", "admin"), "role": "ADMIN"},
            {"username": os.getenv("DEMO_ANALYST_USERNAME", "analyst"), "role": "ANALYST"},
            {"username": os.getenv("DEMO_VIEWER_USERNAME", "viewer"), "role": "VIEWER"},
        ],
    }
