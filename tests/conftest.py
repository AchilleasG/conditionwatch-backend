import os
import shutil
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test-conditionwatch.db")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-jwt")
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("EVALUATION_FRAMES_DIR", "./data/test-evaluation-frames")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    shutil.rmtree("./data/test-evaluation-frames", ignore_errors=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    shutil.rmtree("./data/test-evaluation-frames", ignore_errors=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
