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
