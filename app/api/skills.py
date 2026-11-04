from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models import Role, Skill, User
from app.services.matcher import DEFAULT_SKILLS

router = APIRouter(prefix="/skills", tags=["skills"])
STAFF = (Role.admin, Role.recruiter)


class SkillsIn(BaseModel):
    names: list[str] = Field(min_length=1, max_length=200)


@router.get("")
def list_skills(user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    rows = db.scalars(select(Skill).where(Skill.org_id == user.org_id).order_by(Skill.name)).all()
    return {
        "custom": [{"id": r.id, "name": r.name} for r in rows],
        "using_defaults": len(rows) == 0,
        "defaults": sorted(DEFAULT_SKILLS) if not rows else [],
    }


@router.post("", status_code=201)
def add_skills(body: SkillsIn, user: User = Depends(require_roles(*STAFF)),
               db: Session = Depends(get_db)):
    names = {n.strip().lower() for n in body.names if n.strip()}
    if any(len(n) > 100 for n in names):
        raise HTTPException(422, "Skill names must be 100 characters or fewer")
    existing = set(db.scalars(select(Skill.name).where(Skill.org_id == user.org_id)))
    added = sorted(names - existing)
    for n in added:
        db.add(Skill(org_id=user.org_id, name=n))
    db.commit()
    return {"added": added, "already_existed": sorted(names & existing)}


@router.delete("/{skill_id}", status_code=204)
def delete_skill(skill_id: str, user: User = Depends(require_roles(*STAFF)),
                 db: Session = Depends(get_db)):
    skill = db.scalar(select(Skill).where(Skill.id == skill_id, Skill.org_id == user.org_id))
    if not skill:
        raise HTTPException(404, "Skill not found")
    db.delete(skill)
    db.commit()
