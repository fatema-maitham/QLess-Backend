# tests/conftest.py

import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database import get_db
from models.base import Base
from tests.lib import seed_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

# A Monday at 10:00 in Bahrain: every seeded branch is open at this time
MONDAY_10AM = datetime(2026, 10, 5, 10, 0, tzinfo=ZoneInfo("Asia/Bahrain"))

@pytest.fixture(autouse=True)
def branches_are_open(monkeypatch):
    """Joining a queue needs the branch to be open right now.
    Pretend it's Monday 10:00 so the tests pass at any time of day.
    A test can change the time again with monkeypatch."""
    monkeypatch.setattr("services.opening_hours.now_local", lambda: MONDAY_10AM)

@pytest.fixture(scope="module")
def test_app():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def test_db() -> Session:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_db(db)
    yield db
    db.close()

@pytest.fixture(scope="module")
def override_get_db(test_db):
    def _get_db_override():
        return test_db
    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides = {}