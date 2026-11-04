from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models import Application, Job, Role, Stage, User
from app.schemas import ApplicationOut, JobCreate, JobOut, StageUpdate
from app.services.parser import extract_pdf_text
from app.services.queue import dispatch_scoring

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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You already applied to this job")
    dispatch_scoring(background, application.id)
    return application


@router.get("/{job_id}/applications", response_model=list[ApplicationOut])
def ranked_applications(job_id: str, user: User = Depends(require_roles(*STAFF)),
                        db: Session = Depends(get_db),
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    job = _job_in_org(db, job_id, user)
    return db.scalars(
        select(Application)
        .where(Application.job_id == job.id, Application.org_id == user.org_id)
        .order_by(Application.score.desc().nulls_last(), Application.created_at)
        .limit(limit).offset(offset)
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
def rescore(job_id: str, background: BackgroundTasks, only_unfinished: bool = False,
            user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    """Re-queue scoring. With only_unfinished=true, only pending or failed applications."""
    job = _job_in_org(db, job_id, user)
    q = select(Application).where(Application.job_id == job.id, Application.org_id == user.org_id)
    if only_unfinished:
        q = q.where(Application.scoring_status != "done")
    apps = db.scalars(q).all()
    for a in apps:
        a.scoring_status = "pending"
        a.scoring_error = None
    db.commit()
    for a in apps:
        dispatch_scoring(background, a.id)
    return {"queued": len(apps)}


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _job_in_org(db, job_id, user)
