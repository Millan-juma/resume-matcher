from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models import Application, Job, Role, Stage, User
from app.schemas import ApplicationOut, JobCreate, JobOut, StageUpdate
from app.services.parser import extract_pdf_text
from app.workers.tasks import score_application

router = APIRouter(prefix="/jobs", tags=["jobs"])
MAX_PDF_BYTES = 5 * 1024 * 1024
STAFF = (Role.admin, Role.recruiter)


def _job_in_org(db: Session, job_id: str, user: User) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.org_id == user.org_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, user: User = Depends(require_roles(*STAFF)),
               db: Session = Depends(get_db)):
    job = Job(org_id=user.org_id, title=body.title,
              description=body.description, created_by=user.id)
    db.add(job)
    db.commit()
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Job).where(Job.org_id == user.org_id)
                      .order_by(Job.created_at.desc())).all()


@router.post("/{job_id}/apply", response_model=ApplicationOut, status_code=201)
async def apply(job_id: str, background: BackgroundTasks,
                resume: UploadFile = File(...),
                user: User = Depends(require_roles(Role.candidate)),
                db: Session = Depends(get_db)):
    job = _job_in_org(db, job_id, user)
    if resume.content_type != "application/pdf":
        raise HTTPException(415, "Only PDF resumes are supported")
    data = await resume.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "File too large (max 5 MB)")
    try:
        text = extract_pdf_text(data)
    except Exception:
        raise HTTPException(422, "Could not read this PDF")
    if len(text) < 50:
        raise HTTPException(422, "No readable text found. Scanned PDFs are not supported yet")
    if db.scalar(select(Application).where(
            Application.job_id == job.id, Application.candidate_id == user.id)):
        raise HTTPException(409, "You already applied to this job")
    application = Application(org_id=user.org_id, job_id=job.id,
                              candidate_id=user.id, resume_text=text)
    db.add(application)
    db.commit()
    background.add_task(score_application, application.id)
    return application


@router.get("/{job_id}/applications", response_model=list[ApplicationOut])
def ranked_applications(job_id: str, user: User = Depends(require_roles(*STAFF)),
                        db: Session = Depends(get_db)):
    job = _job_in_org(db, job_id, user)
    return db.scalars(
        select(Application)
        .where(Application.job_id == job.id, Application.org_id == user.org_id)
        .order_by(Application.score.desc().nulls_last())
    ).all()


@router.patch("/applications/{application_id}/stage", response_model=ApplicationOut)
def update_stage(application_id: str, body: StageUpdate,
                 user: User = Depends(require_roles(*STAFF)),
                 db: Session = Depends(get_db)):
    try:
        stage = Stage(body.stage)
    except ValueError:
        raise HTTPException(422, f"Stage must be one of {[s.value for s in Stage]}")
    application = db.scalar(select(Application).where(
        Application.id == application_id, Application.org_id == user.org_id))
    if not application:
        raise HTTPException(404, "Application not found")
    application.stage = stage
    db.commit()
    return application


@router.post("/{job_id}/rescore", status_code=202)
def rescore(job_id: str, background: BackgroundTasks,
            user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    job = _job_in_org(db, job_id, user)
    ids = db.scalars(select(Application.id).where(
        Application.job_id == job.id, Application.org_id == user.org_id)).all()
    for i in ids:
        background.add_task(score_application, i)
    return {"queued": len(ids)}
