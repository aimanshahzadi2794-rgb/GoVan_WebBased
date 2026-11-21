def test_register_passenger_and_login(client):
    r = client.post("/auth/register", json={
        "name": "Passenger One", "email": "passenger@govanmail.dev", "password": "Passw0rd!", "role": "passenger"
    })
    assert r.status_code == 201
    assert r.json()["email"] == "passenger@govanmail.dev"
    assert r.json()["role"] == "passenger"

    r = client.post("/auth/login", data={"username": "passenger@govanmail.dev", "password": "Passw0rd!"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_driver(client):
    r = client.post("/auth/register", json={
        "name": "Driver One", "email": "driver@govanmail.dev", "password": "Passw0rd!", "role": "driver"
    })
    assert r.status_code == 201
    assert r.json()["role"] == "driver"


def test_only_first_admin_can_register(client):
    first_admin = client.post("/auth/register", json={
        "name": "Admin One", "email": "admin@govanmail.dev", "password": "Passw0rd!", "role": "admin"
    })
    assert first_admin.status_code == 201
    assert first_admin.json()["role"] == "admin"

    second_admin = client.post("/auth/register", json={
        "name": "Admin Two", "email": "admin2@govanmail.dev", "password": "Passw0rd!", "role": "admin"
    })
    assert second_admin.status_code == 403

    second_super_admin = client.post("/auth/register", json={
        "name": "Admin Three", "email": "admin3@govanmail.dev",
        "password": "Passw0rd!", "role": "super_admin",
    })
    assert second_super_admin.status_code == 403

    login = client.post("/auth/login", data={
        "username": "admin@govanmail.dev", "password": "Passw0rd!"
    })
    assert login.status_code == 200


def test_login_wrong_password_rejected(client):
    client.post("/auth/register", json={
        "name": "Passenger One", "email": "passenger2@govanmail.dev", "password": "Passw0rd!", "role": "passenger"
    })
    r = client.post("/auth/login", data={"username": "passenger2@govanmail.dev", "password": "wrong"})
    assert r.status_code == 401


def test_duplicate_email_rejected(client):
    payload = {"name": "A", "email": "dup@govanmail.dev", "password": "Passw0rd!", "role": "passenger"}
    client.post("/auth/register", json=payload)
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 400


def test_me_requires_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth import ALGORITHM, SECRET_KEY




def test_invalid_expired_and_malformed_subject_tokens_are_unauthorized(client):
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    malformed_subject = jwt.encode(
        {"sub": "not-an-integer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    for token in ("not-a-jwt", expired, malformed_subject):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_registration_rejects_weak_password(client):
    response = client.post("/auth/register", json={
        "name": "Weak Password", "email": "weak@example.com",
        "password": "short", "role": "passenger",
    })
    assert response.status_code == 422


def test_cors_allows_local_app_but_not_arbitrary_origins(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/health", headers={"Origin": "https://attacker.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert denied.headers.get("access-control-allow-origin") is None
