import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import PasswordReset

RESET_HOURS = 1


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_reset_token(db: Session, user_id: str) -> str:
    # one live token per user: invalidate older unused ones
    db.execute(update(PasswordReset)
               .where(PasswordReset.user_id == user_id, PasswordReset.used_at.is_(None))
               .values(used_at=_now()))
    raw = secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user_id, token_hash=_hash(raw),
                         expires_at=_now() + timedelta(hours=RESET_HOURS)))
    db.commit()
    return raw


def consume_reset_token(db: Session, raw: str) -> str | None:
    """Atomically mark a valid token as used and return its user id, else None."""
    row = db.execute(
        update(PasswordReset)
        .where(PasswordReset.token_hash == _hash(raw),
               PasswordReset.used_at.is_(None),
               PasswordReset.expires_at > _now())
        .values(used_at=_now())
        .returning(PasswordReset.user_id)
    ).first()
    db.commit()
    return row[0] if row else None
