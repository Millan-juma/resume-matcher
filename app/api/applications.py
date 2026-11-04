from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models import Application, Job, Role, User

router = APIRouter(prefix="/applications", tags=["applications"])


class MyApplicationOut(BaseModel):
    id: str
    job_id: str
    job_title: str
    stage: str
    created_at: datetime


@router.get("/me", response_model=list[MyApplicationOut])
def my_applications(user: User = Depends(require_roles(Role.candidate)),
                    db: Session = Depends(get_db)):
    rows = db.execute(
        select(Application, Job.title)
        .join(Job, Job.id == Application.job_id)
        .where(Application.candidate_id == user.id, Application.org_id == user.org_id)
        .order_by(Application.created_at.desc())
    ).all()
    return [MyApplicationOut(id=a.id, job_id=a.job_id, job_title=title,
                             stage=a.stage.value, created_at=a.created_at)
            for a, title in rows]
