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
