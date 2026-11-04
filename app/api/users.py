from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.core.security import hash_password
from app.models import Role, User
from app.services.tokens import revoke_all

router = APIRouter(prefix="/users", tags=["users"])
STAFF_ROLES = (Role.admin, Role.recruiter)


class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "recruiter"] = "recruiter"


class StaffOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


def _staff_in_org(db: Session, user_id: str, admin: User) -> User:
    u = db.scalar(select(User).where(
        User.id == user_id, User.org_id == admin.org_id, User.role.in_(STAFF_ROLES)))
    if not u:
        raise HTTPException(404, "Staff member not found")
    return u


@router.post("/staff", response_model=StaffOut, status_code=201)
def create_staff(body: StaffCreate, admin: User = Depends(require_roles(Role.admin)),
                 db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(org_id=admin.org_id, email=email,
                password_hash=hash_password(body.password), role=Role(body.role))
    db.add(user)
    db.commit()
    return user


@router.get("/staff", response_model=list[StaffOut])
def list_staff(admin: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(
        User.org_id == admin.org_id, User.role.in_(STAFF_ROLES)).order_by(User.created_at)).all()


@router.post("/{user_id}/deactivate", status_code=204)
def deactivate(user_id: str, admin: User = Depends(require_roles(Role.admin)),
               db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    user = _staff_in_org(db, user_id, admin)
    user.is_active = False
    db.commit()
    revoke_all(db, user.id)


@router.post("/{user_id}/reactivate", status_code=204)
def reactivate(user_id: str, admin: User = Depends(require_roles(Role.admin)),
               db: Session = Depends(get_db)):
    user = _staff_in_org(db, user_id, admin)
    user.is_active = True
    db.commit()
