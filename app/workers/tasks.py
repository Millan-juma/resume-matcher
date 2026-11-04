import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Application, Job, Skill
from app.services.matcher import score
from app.services.ocr import ocr_pdf

log = logging.getLogger(__name__)


class PermanentError(Exception):
    """A failure that retrying cannot fix."""


def score_application(application_id: str) -> bool:
    """OCR if needed, then score. Returns False only when a retry could help."""
    db = SessionLocal()
    try:
        app_ = db.get(Application, application_id)
        if not app_:
            return True  # deleted in the meantime
        try:
            if not app_.resume_text:
                if app_.resume_pdf is None:
                    raise PermanentError("NoReadableText")
                text = ocr_pdf(app_.resume_pdf)
                if len(text) < 50:
                    raise PermanentError("NoReadableText")
                app_.resume_text = text
                app_.resume_pdf = None  # drop the stored scan as soon as the text is extracted
                db.commit()
            job = db.get(Job, app_.job_id)
            skills = set(db.scalars(select(Skill.name).where(Skill.org_id == app_.org_id)))
            result = score(app_.resume_text, job.description, skills or None)
            app_.score = result["score"]
            app_.score_breakdown = result
            app_.scoring_status = "done"
            app_.scoring_error = None
            db.commit()
            return True
        except PermanentError as e:
            db.rollback()
            app_ = db.get(Application, application_id)
            if app_:
                app_.resume_pdf = None
                app_.scoring_status = "failed"
                app_.scoring_error = str(e)
                db.commit()
            return True  # nothing to retry
        except Exception as e:
            log.exception("Scoring failed for application %s", application_id)
            db.rollback()
            app_ = db.get(Application, application_id)
            if app_:
                app_.scoring_status = "failed"
                app_.scoring_error = type(e).__name__  # class name only, no internal details
                db.commit()
            return False
    finally:
        db.close()


def score_job(application_id: str) -> None:
    """Queue entry point. Raising tells the worker to retry."""
    if not score_application(application_id):
        raise RuntimeError("Scoring failed")
