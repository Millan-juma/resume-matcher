import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models import Application, Job, LLMCache, Role, User
from app.services.llm import LLMUnavailable, get_provider, redact

router = APIRouter(prefix="/applications", tags=["explain"])
NOTE = "AI-generated decision support. A human should make the final decision."


@router.post("/{application_id}/explain")
def explain(application_id: str,
            user: User = Depends(require_roles(Role.admin, Role.recruiter)),
            db: Session = Depends(get_db)):
    app_ = db.scalar(select(Application).where(
        Application.id == application_id, Application.org_id == user.org_id))
    if not app_:
        raise HTTPException(404, "Application not found")
    if app_.score_breakdown is None:
        raise HTTPException(409, "Scoring not finished yet. Try again in a few seconds")

    job = db.get(Job, app_.job_id)
    provider = get_provider()
    resume = redact(app_.resume_text)
    key = hashlib.sha256(
        "\x00".join([user.org_id, provider.cache_id, resume, job.description]).encode()
    ).hexdigest()

    cached = db.get(LLMCache, key)
    if cached:
        return {**cached.response, "cached": True, "provider": provider.name, "note": NOTE}

    try:
        result = provider.explain(resume, job.description, app_.score_breakdown)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))

    db.add(LLMCache(key=key, org_id=user.org_id, response=result.model_dump()))
    db.commit()
    return {**result.model_dump(), "cached": False, "provider": provider.name, "note": NOTE}
