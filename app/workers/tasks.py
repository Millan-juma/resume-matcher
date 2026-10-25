from app.core.db import SessionLocal
from app.models import Application, Job
from app.services.matcher import score


def score_application(application_id: str) -> None:
    db = SessionLocal()
    try:
        app_ = db.get(Application, application_id)
        if not app_:
            return
        job = db.get(Job, app_.job_id)
        result = score(app_.resume_text, job.description)
        app_.score = result["score"]
        app_.score_breakdown = result
        db.commit()
    finally:
        db.close()
