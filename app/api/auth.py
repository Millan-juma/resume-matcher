from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.ratelimit import limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Application, Organization, Role, User
from app.schemas import LoginIn, RefreshIn, RegisterCandidate, RegisterOrg, TokenOut, UserOut
from app.services.tokens import issue_refresh_token, revoke_all, revoke_one, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User).where(User.email == email.lower())) is not None


def _tokens(db: Session, user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.org_id, user.role.value),
        refresh_token=issue_refresh_token(db, user.id),
    )


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


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
    return _tokens(db, user)


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
    return _tokens(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    limit(f"login:{_ip(request)}:{body.email.lower()}", 5, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _tokens(db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    limit(f"refresh:{_ip(request)}", 30, 300)
    result = rotate_refresh_token(db, body.refresh_token)
    if not result:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    user_id, new_refresh = result
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    return TokenOut(
        access_token=create_access_token(user.id, user.org_id, user.role.value),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    """Revoke this session's refresh token."""
    revoke_one(db, body.refresh_token)


@router.post("/logout-all", status_code=204)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke every session for the current user."""
    revoke_all(db, user.id)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.delete("/me", status_code=204)
def delete_my_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Right to erasure: removes a candidate, their applications, resume text and sessions."""
    if user.role != Role.candidate:
        raise HTTPException(400, "Staff accounts must be removed by an organization admin")
    db.execute(delete(Application).where(Application.candidate_id == user.id))
    db.delete(user)
    db.commit()
