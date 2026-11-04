from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

from app.api import applications, users  # noqa: F401
from app.api import auth, explain, jobs, skills, password

app = FastAPI(title="Resume Matcher API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(explain.router)
app.include_router(skills.router)
app.include_router(password.router)
app.include_router(users.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {"status": "ok"}
