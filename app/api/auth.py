from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Organization, Role, User
from app.schemas import LoginIn, RegisterCandidate, RegisterOrg, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User).where(User.email == email.lower())) is not None


@router.post("/register-org", response_model=TokenOut, status_code=201)
def register_org(body: RegisterOrg, db: Session = Depends(get_db)):
    if _email_taken(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if db.scalar(select(Organization).where(Organization.name == body.org_name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Organization name taken")
    org = Organization(name=body.org_name)
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=body.email.lower(),
                password_hash=hash_password(body.password), role=Role.admin)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, org.id, user.role.value))


@router.post("/register-candidate", response_model=TokenOut, status_code=201)
def register_candidate(body: RegisterCandidate, db: Session = Depends(get_db)):
    if not db.get(Organization, body.org_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if _email_taken(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(org_id=body.org_id, email=body.email.lower(),
                password_hash=hash_password(body.password), role=Role.candidate)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.org_id, user.role.value))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id, user.org_id, user.role.value))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
