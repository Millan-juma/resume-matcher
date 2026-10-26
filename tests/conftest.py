import os

os.environ["POSTGRES_DB"] = "resume_matcher_test"  # must be set before importing app

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
    yield


@pytest.fixture
def client():
    return TestClient(app)
