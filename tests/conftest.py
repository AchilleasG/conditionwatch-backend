import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test-conditionwatch.db")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-jwt")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
