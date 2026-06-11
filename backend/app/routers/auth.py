from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..pipeline import log
from ..security import ROLE_PERMISSIONS, create_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    log(db, "user_logged_in", actor_id=user.id, actor_role=user.role, message=f"{user.name} signed in")
    db.commit()
    return {"token": create_token(user.id, user.role),
            "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
                     "permissions": sorted(ROLE_PERMISSIONS.get(user.role, set()))}}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "permissions": sorted(ROLE_PERMISSIONS.get(user.role, set()))}


@router.get("/demo-users")
def demo_users(db: Session = Depends(get_db)):
    """Convenience endpoint for the login page (simulation environment only)."""
    return [{"email": u.email, "name": u.name, "role": u.role} for u in db.query(models.User).all()]
