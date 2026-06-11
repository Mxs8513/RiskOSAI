"""Auth: PBKDF2 password hashing (stdlib) + JWT bearer tokens + RBAC."""
from __future__ import annotations

import hashlib
import os
import time
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db

settings = get_settings()
bearer = HTTPBearer(auto_error=False)

# ---- password hashing (PBKDF2-HMAC-SHA256, stdlib, no native deps) ----

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
        return dk.hex() == dk_hex
    except ValueError:
        return False

# ---- JWT ----

def create_token(user_id: int, role: str) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": int(time.time()) + settings.jwt_expire_minutes * 60}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
):
    from .models import User

    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


# ---- RBAC ----
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "fraud_analyst": {"overview", "transactions", "investigations", "review", "audit:limited", "intelligence"},
    "risk_manager": {"overview", "transactions", "investigations", "review", "override", "metrics", "rules", "rules:edit", "audit", "intelligence"},
    "developer": {"overview", "developer", "rules", "audit:limited", "transactions", "intelligence"},
    "admin": {"*"},
}


def has_permission(role: str, perm: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return "*" in perms or perm in perms or (perm.endswith(":limited") and perm.split(":")[0] in perms)


def require(perm: str):
    def checker(user=Depends(get_current_user)):
        if not has_permission(user.role, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role}' lacks permission '{perm}'")
        return user
    return checker
