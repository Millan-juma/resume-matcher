import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Application, Job, Skill
from app.services.matcher import score

log = logging.getLogger(__name__)


def score_application(application_id: str) -> None:
    db = SessionLocal()
    try:
        app_ = db.get(Application, application_id)
        if not app_:
            return
        try:
            job = db.get(Job, app_.job_id)
            skills = set(db.scalars(select(Skill.name).where(Skill.org_id == app_.org_id)))
            result = score(app_.resume_text, job.description, skills or None)
            app_.score = result["score"]
            app_.score_breakdown = result
            app_.scoring_status = "done"
            app_.scoring_error = None
        except Exception as e:
            log.exception("Scoring failed for application %s", application_id)
            db.rollback()
            app_ = db.get(Application, application_id)
            if app_:
                app_.scoring_status = "failed"
                app_.scoring_error = type(e).__name__  # class name only, no internal details
        db.commit()
    finally:
        db.close()
