from fastapi import FastAPI

from app.api import auth, explain, jobs

app = FastAPI(title="Resume Matcher API", version="0.1.0")
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(explain.router)


@app.get("/health")
def health():
    return {"status": "ok"}
