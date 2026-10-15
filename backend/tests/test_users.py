def test_first_admin_bootstrap_and_registration_lockout(client):
    status = client.get("/auth/bootstrap-status")
    assert status.status_code == 200
    assert status.json() == {"needs_first_admin": True}

    first_admin = client.post("/auth/register", json={
        "name": "First Admin",
        "email": "first-admin@example.com",
        "password": "Passw0rd!",
        "role": "admin",
    })
    assert first_admin.status_code == 201
    assert first_admin.json()["role"] == "admin"

    status = client.get("/auth/bootstrap-status")
    assert status.json() == {"needs_first_admin": False}

    second_admin = client.post("/auth/register", json={
        "name": "Second Admin",
        "email": "second-admin@example.com",
        "password": "Passw0rd!",
        "role": "admin",
    })
    assert second_admin.status_code == 403
    assert second_admin.json()["detail"] == "The first administrator has already been created"


def test_admin_can_manage_users_but_not_demote_or_deactivate_self(client):
    from .conftest import register_and_login

    admin_headers = register_and_login(client, "users-admin@example.com", role="admin")
    created = client.post("/users/", json={
        "name": "Managed Driver",
        "email": "managed-driver@example.com",
        "password": "Passw0rd!",
        "role": "driver",
    }, headers=admin_headers)
    assert created.status_code == 201
    managed_user = created.json()
    assert managed_user["role"] == "driver"
    assert managed_user["is_active"] is True
    assert managed_user["created_at"]

    users = client.get("/users/", headers=admin_headers)
    assert users.status_code == 200
    assert any(user["id"] == managed_user["id"] for user in users.json())

    updated = client.patch(f"/users/{managed_user['id']}", json={
        "name": "Updated Driver",
        "role": "passenger",
        "is_active": False,
        "license_number": "LIC-123",
        "phone": "+1-555-0100",
        "license_expiry": "2030-01-15",
    }, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Driver"
    assert updated.json()["role"] == "passenger"
    assert updated.json()["is_active"] is False
    assert updated.json()["license_number"] == "LIC-123"
    assert updated.json()["phone"] == "+1-555-0100"
    assert updated.json()["license_expiry"] == "2030-01-15"

    cleared_profile = client.patch(
        f"/users/{managed_user['id']}",
        json={"license_number": None, "phone": None, "license_expiry": None},
        headers=admin_headers,
    )
    assert cleared_profile.status_code == 200
    assert cleared_profile.json()["license_number"] is None
    assert cleared_profile.json()["phone"] is None
    assert cleared_profile.json()["license_expiry"] is None

    self_id = client.get("/auth/me", headers=admin_headers).json()["id"]
    demote_self = client.patch(f"/users/{self_id}", json={"role": "driver"}, headers=admin_headers)
    assert demote_self.status_code == 400
    deactivate_self = client.patch(
        f"/users/{self_id}", json={"is_active": False}, headers=admin_headers
    )
    assert deactivate_self.status_code == 400

    inactive_login = client.post("/auth/login", data={
        "username": "managed-driver@example.com",
        "password": "Passw0rd!",
    })
    assert inactive_login.status_code == 403


def test_users_endpoints_require_admin(client):
    from .conftest import register_and_login

    passenger_headers = register_and_login(client, "users-passenger@example.com")
    assert client.get("/users/", headers=passenger_headers).status_code == 403
    assert client.post("/users/", json={
        "name": "Attempted Admin",
        "email": "attempted-admin@example.com",
        "password": "Passw0rd!",
        "role": "admin",
    }, headers=passenger_headers).status_code == 403
    assert client.patch("/users/1", json={"name": "Not allowed"}, headers=passenger_headers).status_code == 403
