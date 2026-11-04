import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken

REFRESH_DAYS = 14


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_refresh_token(db: Session, user_id: str) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user_id, token_hash=_hash(raw),
                        expires_at=_now() + timedelta(days=REFRESH_DAYS)))
    db.commit()
    return raw


def revoke_all(db: Session, user_id: str) -> None:
    db.execute(update(RefreshToken)
               .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=_now()))
    db.commit()


def revoke_one(db: Session, raw: str) -> None:
    db.execute(update(RefreshToken)
               .where(RefreshToken.token_hash == _hash(raw), RefreshToken.revoked_at.is_(None))
               .values(revoked_at=_now()))
    db.commit()


def rotate_refresh_token(db: Session, raw: str) -> tuple[str, str] | None:
    """Return (user_id, new_refresh_token), or None if the token is not usable."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if not row:
        return None
    if row.revoked_at is not None:
        revoke_all(db, row.user_id)  # an used token came back: treat it as stolen
        return None
    if row.expires_at < _now():
        return None
    row.revoked_at = _now()
    db.commit()
    return row.user_id, issue_refresh_token(db, row.user_id)
