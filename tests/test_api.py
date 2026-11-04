def register_org(client, org, email):
    r = client.post("/auth/register-org",
                    json={"org_name": org, "email": email, "password": "StrongPass123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


JOB = {"title": "Backend Engineer",
       "description": "We need Python and FastAPI experience with PostgreSQL."}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_and_me(client):
    h = register_org(client, "Acme", "admin@acme.com")
    me = client.get("/auth/me", headers=h).json()
    assert me["role"] == "admin" and me["email"] == "admin@acme.com"


def test_duplicate_email_rejected(client):
    register_org(client, "Acme", "admin@acme.com")
    r = client.post("/auth/register-org",
                    json={"org_name": "Other", "email": "admin@acme.com", "password": "StrongPass123"})
    assert r.status_code == 409


def test_wrong_password_rejected(client):
    register_org(client, "Acme", "admin@acme.com")
    r = client.post("/auth/login", json={"email": "admin@acme.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_candidate_cannot_create_job(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    org_id = client.get("/auth/me", headers=admin).json()["org_id"]
    r = client.post("/auth/register-candidate",
                    json={"org_id": org_id, "email": "c@acme.com", "password": "StrongPass123"})
    cand = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/jobs", json=JOB, headers=cand).status_code == 403


def test_orgs_are_isolated(client):
    a = register_org(client, "Org A", "a@a.com")
    b = register_org(client, "Org B", "b@b.com")
    job_id = client.post("/jobs", json=JOB, headers=a).json()["id"]
    assert client.get("/jobs", headers=b).json() == []
    assert client.get(f"/jobs/{job_id}/applications", headers=b).status_code == 404


def test_login_rate_limited(client):
    register_org(client, "Acme", "admin@acme.com")
    codes = [client.post("/auth/login",
                         json={"email": "admin@acme.com", "password": "wrong-password"}).status_code
             for _ in range(7)]
    assert codes[:5] == [401] * 5
    assert 429 in codes[5:]


def test_candidate_can_delete_account(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    org_id = client.get("/auth/me", headers=admin).json()["org_id"]
    r = client.post("/auth/register-candidate",
                    json={"org_id": org_id, "email": "c@acme.com", "password": "StrongPass123"})
    cand = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.delete("/auth/me", headers=cand).status_code == 204
    assert client.get("/auth/me", headers=cand).status_code == 401
    assert client.delete("/auth/me", headers=admin).status_code == 400


def test_skills_are_per_org(client):
    a = register_org(client, "Org A", "a@a.com")
    b = register_org(client, "Org B", "b@b.com")
    r = client.post("/skills", json={"names": ["Terraform", " terraform ", "Ansible"]}, headers=a)
    assert r.status_code == 201 and r.json()["added"] == ["ansible", "terraform"]
    assert len(client.get("/skills", headers=a).json()["custom"]) == 2
    assert client.get("/skills", headers=b).json()["using_defaults"] is True


def test_account_deletion_removes_cached_explanations(client):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Application, Job, LLMCache

    admin = register_org(client, "Acme", "admin@acme.com")
    me = client.get("/auth/me", headers=admin).json()
    r = client.post("/auth/register-candidate",
                    json={"org_id": me["org_id"], "email": "c@acme.com", "password": "StrongPass123"})
    cand = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cand_id = client.get("/auth/me", headers=cand).json()["id"]

    with SessionLocal() as db:
        job = Job(org_id=me["org_id"], title="Dev",
                  description="Python developer needed for APIs.", created_by=me["id"])
        db.add(job)
        db.flush()
        a = Application(org_id=me["org_id"], job_id=job.id, candidate_id=cand_id,
                        resume_text="resume text", score=50.0,
                        score_breakdown={"matched_skills": [], "missing_skills": [], "score": 50.0})
        db.add(a)
        db.flush()
        db.add(LLMCache(key="k" * 64, org_id=me["org_id"], application_id=a.id,
                        response={"summary": "x"}))
        db.commit()
        assert db.scalar(select(LLMCache)) is not None

    assert client.delete("/auth/me", headers=cand).status_code == 204

    with SessionLocal() as db:
        assert db.scalar(select(LLMCache)) is None


def _make_application(client):
    from app.core.db import SessionLocal
    from app.models import Application, Job

    admin = register_org(client, "Acme", "admin@acme.com")
    me = client.get("/auth/me", headers=admin).json()
    r = client.post("/auth/register-candidate",
                    json={"org_id": me["org_id"], "email": "c@acme.com", "password": "StrongPass123"})
    cand = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cand_id = client.get("/auth/me", headers=cand).json()["id"]
    with SessionLocal() as db:
        job = Job(org_id=me["org_id"], title="Dev",
                  description="Python developer needed for APIs.", created_by=me["id"])
        db.add(job)
        db.flush()
        a = Application(org_id=me["org_id"], job_id=job.id, candidate_id=cand_id,
                        resume_text="Python developer with API experience.")
        db.add(a)
        db.commit()
        return a.id


def test_scoring_failure_is_recorded(client, monkeypatch):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    app_id = _make_application(client)

    def boom(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(tasks, "score", boom)
    tasks.score_application(app_id)
    with SessionLocal() as db:
        a = db.get(Application, app_id)
        assert a.scoring_status == "failed" and a.scoring_error == "RuntimeError"


def test_scoring_success_is_recorded(client, monkeypatch):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    app_id = _make_application(client)
    fake = {"score": 70.0, "matched_skills": ["python"], "missing_skills": []}
    monkeypatch.setattr(tasks, "score", lambda *a, **k: fake)
    tasks.score_application(app_id)
    with SessionLocal() as db:
        a = db.get(Application, app_id)
        assert a.scoring_status == "done" and a.score == 70.0 and a.scoring_error is None


def _register_org_tokens(client):
    r = client.post("/auth/register-org",
                    json={"org_name": "Acme", "email": "admin@acme.com", "password": "StrongPass123"})
    assert r.status_code == 201
    return r.json()


def test_refresh_rotates_and_detects_reuse(client):
    t1 = _register_org_tokens(client)["refresh_token"]
    r2 = client.post("/auth/refresh", json={"refresh_token": t1})
    assert r2.status_code == 200
    t2 = r2.json()["refresh_token"]
    assert t2 != t1
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
    assert me.status_code == 200
    # replaying the old token fails and revokes the whole session family
    assert client.post("/auth/refresh", json={"refresh_token": t1}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": t2}).status_code == 401


def test_logout_revokes_refresh_token(client):
    t = _register_org_tokens(client)["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": t}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": t}).status_code == 401


def test_garbage_refresh_token_rejected(client):
    assert client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"}).status_code == 401


def test_deleting_account_kills_sessions(client):
    admin = register_org(client, "Acme2", "admin2@acme.com")
    org_id = client.get("/auth/me", headers=admin).json()["org_id"]
    r = client.post("/auth/register-candidate",
                    json={"org_id": org_id, "email": "c2@acme.com", "password": "StrongPass123"})
    cand = {"Authorization": f"Bearer {r.json()['access_token']}"}
    rt = r.json()["refresh_token"]
    assert client.delete("/auth/me", headers=cand).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_forgot_password_is_silent_for_unknown_email(client, sent_emails):
    register_org(client, "Acme", "admin@acme.com")
    a = client.post("/auth/forgot-password", json={"email": "admin@acme.com"})
    b = client.post("/auth/forgot-password", json={"email": "nobody@acme.com"})
    assert a.status_code == b.status_code == 202
    assert a.json() == b.json()
    assert [to for to, _ in sent_emails] == ["admin@acme.com"]


def test_password_reset_flow(client, sent_emails):
    t = _register_org_tokens(client)
    client.post("/auth/forgot-password", json={"email": "admin@acme.com"})
    token = sent_emails[0][1]
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "BrandNewPass456"})
    assert r.status_code == 204
    old = client.post("/auth/login", json={"email": "admin@acme.com", "password": "StrongPass123"})
    new = client.post("/auth/login", json={"email": "admin@acme.com", "password": "BrandNewPass456"})
    assert old.status_code == 401 and new.status_code == 200
    again = client.post("/auth/reset-password", json={"token": token, "new_password": "AnotherPass789"})
    assert again.status_code == 400
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_expired_reset_token_rejected(client, sent_emails):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from app.core.db import SessionLocal
    from app.models import PasswordReset

    register_org(client, "Acme", "admin@acme.com")
    client.post("/auth/forgot-password", json={"email": "admin@acme.com"})
    token = sent_emails[0][1]
    with SessionLocal() as db:
        db.execute(update(PasswordReset).values(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "BrandNewPass456"})
    assert r.status_code == 400


def test_weak_password_does_not_burn_the_token(client, sent_emails):
    register_org(client, "Acme", "admin@acme.com")
    client.post("/auth/forgot-password", json={"email": "admin@acme.com"})
    token = sent_emails[0][1]
    assert client.post("/auth/reset-password",
                       json={"token": token, "new_password": "short"}).status_code == 422
    assert client.post("/auth/reset-password",
                       json={"token": token, "new_password": "BrandNewPass456"}).status_code == 204


def test_forgot_password_rate_limited(client, sent_emails):
    register_org(client, "Acme", "admin@acme.com")
    codes = [client.post("/auth/forgot-password", json={"email": "admin@acme.com"}).status_code
             for _ in range(4)]
    assert codes == [202, 202, 202, 429]


def test_cors_allows_configured_origin_only(client):
    hdr = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    ok = client.options("/jobs", headers={**hdr, "Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/jobs", headers={**hdr, "Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_admin_creates_recruiter_who_can_post_jobs(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    body = {"email": "rec@acme.com", "password": "StrongPass123", "role": "recruiter"}
    assert client.post("/users/staff", json=body, headers=admin).status_code == 201
    login = client.post("/auth/login", json={"email": "rec@acme.com", "password": "StrongPass123"})
    rec = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.post("/jobs", json=JOB, headers=rec).status_code == 201
    other_body = {"email": "x@acme.com", "password": "StrongPass123", "role": "recruiter"}
    assert client.post("/users/staff", json=other_body, headers=rec).status_code == 403
    assert len(client.get("/users/staff", headers=admin).json()) == 2
    other = register_org(client, "Other", "o@o.com")
    assert len(client.get("/users/staff", headers=other).json()) == 1


def test_deactivated_staff_loses_access(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    creds = {"email": "rec@acme.com", "password": "StrongPass123"}
    rec_id = client.post("/users/staff", json={**creds, "role": "recruiter"}, headers=admin).json()["id"]
    login = client.post("/auth/login", json=creds).json()
    rec = {"Authorization": f"Bearer {login['access_token']}"}
    assert client.get("/auth/me", headers=rec).status_code == 200

    admin_id = client.get("/auth/me", headers=admin).json()["id"]
    assert client.post(f"/users/{admin_id}/deactivate", headers=admin).status_code == 400
    other = register_org(client, "Other", "o@o.com")
    assert client.post(f"/users/{rec_id}/deactivate", headers=other).status_code == 404

    assert client.post(f"/users/{rec_id}/deactivate", headers=admin).status_code == 204
    assert client.get("/auth/me", headers=rec).status_code == 401
    assert client.post("/auth/login", json=creds).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401

    assert client.post(f"/users/{rec_id}/reactivate", headers=admin).status_code == 204
    assert client.post("/auth/login", json=creds).status_code == 200


def test_candidate_sees_only_own_applications_without_scores(client):
    _make_application(client)
    cand = client.post("/auth/login", json={"email": "c@acme.com", "password": "StrongPass123"})
    h = {"Authorization": f"Bearer {cand.json()['access_token']}"}
    r = client.get("/applications/me", headers=h)
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["job_title"] == "Dev" and "score" not in r.json()[0]
    adm = client.post("/auth/login", json={"email": "admin@acme.com", "password": "StrongPass123"})
    ah = {"Authorization": f"Bearer {adm.json()['access_token']}"}
    assert client.get("/applications/me", headers=ah).status_code == 403


def test_applicants_pagination_bounds(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    job_id = client.post("/jobs", json=JOB, headers=admin).json()["id"]
    assert client.get(f"/jobs/{job_id}/applications?limit=0", headers=admin).status_code == 422
    assert client.get(f"/jobs/{job_id}/applications?limit=500", headers=admin).status_code == 422
    assert client.get(f"/jobs/{job_id}/applications?limit=10&offset=0", headers=admin).status_code == 200


def test_job_detail_is_org_scoped(client):
    a = register_org(client, "Org A", "a@a.com")
    b = register_org(client, "Org B", "b@b.com")
    job_id = client.post("/jobs", json=JOB, headers=a).json()["id"]
    assert client.get(f"/jobs/{job_id}", headers=a).json()["title"] == "Backend Engineer"
    assert client.get(f"/jobs/{job_id}", headers=b).status_code == 404


class _FakeBackground:
    def __init__(self):
        self.calls = []

    def add_task(self, fn, *args):
        self.calls.append((fn.__name__, args))


def test_dispatch_falls_back_when_redis_is_down(monkeypatch):
    from redis.exceptions import ConnectionError as RedisDown

    from app.core.config import settings
    from app.services import queue as q

    def down(*a, **k):
        raise RedisDown("down")

    monkeypatch.setattr(settings, "queue_mode", "redis")
    monkeypatch.setattr(q.queue, "enqueue", down)
    bg = _FakeBackground()
    q.dispatch_scoring(bg, "abc")
    assert bg.calls == [("score_application", ("abc",))]


def test_dispatch_uses_queue_when_available(monkeypatch):
    from app.core.config import settings
    from app.services import queue as q

    sent = []
    monkeypatch.setattr(settings, "queue_mode", "redis")
    monkeypatch.setattr(q.queue, "enqueue", lambda *a, **k: sent.append(a))
    bg = _FakeBackground()
    q.dispatch_scoring(bg, "abc")
    assert sent and sent[0][1] == "abc" and bg.calls == []


def test_inline_mode_never_touches_the_queue(monkeypatch):
    from app.core.config import settings
    from app.services import queue as q

    def forbidden(*a, **k):
        raise AssertionError("queue must not be used in inline mode")

    monkeypatch.setattr(settings, "queue_mode", "inline")
    monkeypatch.setattr(q.queue, "enqueue", forbidden)
    bg = _FakeBackground()
    q.dispatch_scoring(bg, "abc")
    assert bg.calls == [("score_application", ("abc",))]


def test_failed_scoring_raises_so_the_queue_retries(client, monkeypatch):
    import pytest

    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    app_id = _make_application(client)

    def boom(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(tasks, "score", boom)
    with pytest.raises(RuntimeError):
        tasks.score_job(app_id)
    with SessionLocal() as db:
        assert db.get(Application, app_id).scoring_status == "failed"


def test_job_runs_through_real_redis_queue(client, monkeypatch):
    from redis import Redis
    from rq import Queue

    from app.core.config import settings
    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    app_id = _make_application(client)
    fake = {"score": 81.0, "matched_skills": ["python"], "missing_skills": []}
    monkeypatch.setattr(tasks, "score", lambda *a, **k: fake)
    q = Queue("test-scoring", connection=Redis.from_url(settings.redis_url), is_async=False)
    q.enqueue(tasks.score_job, app_id)  # is_async=False runs it immediately, via real Redis
    with SessionLocal() as db:
        a = db.get(Application, app_id)
        assert a.scoring_status == "done" and a.score == 81.0


def _scanned_pdf(text="Senior Python developer with FastAPI PostgreSQL and Docker experience"):
    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (2400, 300), "white")
    ImageDraw.Draw(img).text((40, 110), text, fill="black", font=ImageFont.load_default(size=56))
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue()


def _job_and_candidate(client):
    admin = register_org(client, "Acme", "admin@acme.com")
    me = client.get("/auth/me", headers=admin).json()
    job_id = client.post("/jobs", json=JOB, headers=admin).json()["id"]
    r = client.post("/auth/register-candidate",
                    json={"org_id": me["org_id"], "email": "c@acme.com", "password": "StrongPass123"})
    return job_id, {"Authorization": f"Bearer {r.json()['access_token']}"}


def _apply_scan(client, job_id, cand):
    return client.post(f"/jobs/{job_id}/apply", headers=cand,
                       files={"resume": ("cv.pdf", _scanned_pdf(), "application/pdf")})


def test_scanned_pdf_rejected_when_ocr_unavailable(client, monkeypatch):
    monkeypatch.setattr("app.api.jobs.ocr_available", lambda: False)
    job_id, cand = _job_and_candidate(client)
    assert _apply_scan(client, job_id, cand).status_code == 422


def test_scanned_pdf_is_ocrd_then_scored(client, monkeypatch):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    monkeypatch.setattr("app.api.jobs.ocr_available", lambda: True)
    monkeypatch.setattr(tasks, "ocr_pdf",
                        lambda data: "Python developer who builds FastAPI services with PostgreSQL and Docker.")
    monkeypatch.setattr(tasks, "score",
                        lambda *a, **k: {"score": 77.0, "matched_skills": ["python"], "missing_skills": []})
    job_id, cand = _job_and_candidate(client)
    r = _apply_scan(client, job_id, cand)
    assert r.status_code == 201
    with SessionLocal() as db:
        a = db.get(Application, r.json()["id"])
        assert a.scoring_status == "done" and a.score == 77.0
        assert a.resume_text.startswith("Python developer")
        assert a.resume_pdf is None  # the scan is not kept once the text is extracted


def test_unreadable_scan_fails_without_retry(client, monkeypatch):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.workers import tasks

    monkeypatch.setattr("app.api.jobs.ocr_available", lambda: True)
    monkeypatch.setattr(tasks, "ocr_pdf", lambda data: "  ")
    job_id, cand = _job_and_candidate(client)
    r = _apply_scan(client, job_id, cand)
    assert r.status_code == 201
    app_id = r.json()["id"]
    with SessionLocal() as db:
        a = db.get(Application, app_id)
        assert a.scoring_status == "failed" and a.scoring_error == "NoReadableText"
        assert a.resume_pdf is None
    tasks.score_job(app_id)  # a permanent failure must not raise, or the queue would retry it


import shutil  # noqa: E402

import pytest  # noqa: E402


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_real_ocr_reads_an_image_pdf():
    from app.services.ocr import ocr_pdf

    text = ocr_pdf(_scanned_pdf()).lower()
    assert "fastapi" in text and "python" in text
