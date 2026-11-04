import os

os.environ["POSTGRES_DB"] = "resume_matcher_test"
os.environ["QUEUE_MODE"] = "inline"  # must be set before importing app

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa
from app.core.db import Base, engine
from app.main import app

assert engine.url.database.endswith("_test"), "Tests must run on the test database"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        from app.core.ratelimit import r
        for k in r.scan_iter('rl:*'):
            r.delete(k)
    except Exception:
        pass
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sent_emails(monkeypatch):
    box = []
    monkeypatch.setattr("app.api.password.send_reset_email",
                        lambda to, token: box.append((to, token)))
    return box
