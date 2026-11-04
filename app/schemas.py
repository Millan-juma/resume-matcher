from pydantic import BaseModel, EmailStr, Field


class RegisterOrg(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterCandidate(BaseModel):
    org_id: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    org_id: str

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=20)


class JobOut(BaseModel):
    id: str
    title: str
    description: str
    org_id: str

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    stage: str
    score: float | None
    score_breakdown: dict | None
    scoring_status: str

    model_config = {"from_attributes": True}


class StageUpdate(BaseModel):
    stage: str
