from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limit
from app.core.security import hash_password
from app.models import User
from app.services.email import send_reset_email
from app.services.password_reset import consume_reset_token, create_reset_token
from app.services.tokens import revoke_all

router = APIRouter(prefix="/auth", tags=["password"])

GENERIC = {"detail": "If that email is registered, a reset message has been sent."}


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/forgot-password", status_code=202)
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    email = body.email.lower()
    limit(f"forgot:ip:{_ip(request)}", 10, 3600)
    limit(f"forgot:email:{email}", 3, 3600)
    user = db.scalar(select(User).where(User.email == email))
    if user:
        token = create_reset_token(db, user.id)
        background.add_task(send_reset_email, user.email, token)
    return GENERIC  # identical whether or not the account exists


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    limit(f"reset:{_ip(request)}", 10, 900)
    user_id = consume_reset_token(db, body.token)
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(400, "Invalid or expired reset token")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke_all(db, user.id)  # log out every session
