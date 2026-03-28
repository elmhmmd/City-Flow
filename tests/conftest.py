import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base
from api.dependencies import get_db

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

MOCK_WEATHER = {"temperature_c": 20.0, "precipitation_mm": 0.0, "windspeed_kmh": 10.0}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_admin_test():
    from api.auth import hash_password
    from api.models import User
    db = TestingSessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", hashed_password=hash_password("admin"), role="admin"))
            db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    with (
        patch("api.predictor.predictor.load", return_value=None),
        patch("api.predictor.predictor.predict", return_value=(5.0, 3.0, 7.0, MOCK_WEATHER)),
        patch("api.main._seed_admin", side_effect=_seed_admin_test),
    ):
        from api.main import app

        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
