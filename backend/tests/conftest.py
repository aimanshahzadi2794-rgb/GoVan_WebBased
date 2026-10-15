import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app import models
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_govan.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


def register_and_login(client, email, password="Passw0rd!", role="passenger", name="Test User"):
    if role == "admin":
        db = TestingSessionLocal()
        try:
            db.add(models.User(
                name=name,
                email=email,
                hashed_password=hash_password(password),
                role=models.UserRole.admin,
            ))
            db.commit()
        finally:
            db.close()
    else:
        response = client.post(
            "/auth/register",
            json={"name": name, "email": email, "password": password, "role": role},
        )
        assert response.status_code == 201

    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
