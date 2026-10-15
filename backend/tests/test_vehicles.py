from .conftest import register_and_login


def test_admin_can_create_vehicle(client):
    headers = register_and_login(client, "admin@govanmail.dev", role="admin")
    r = client.post("/vehicles/", json={"plate_number": "LEB-101", "model": "Hiace", "capacity": 14}, headers=headers)
    assert r.status_code == 201
    assert r.json()["plate_number"] == "LEB-101"


def test_passenger_cannot_create_vehicle(client):
    headers = register_and_login(client, "pax@govanmail.dev", role="passenger")
    r = client.post("/vehicles/", json={"plate_number": "LEB-102", "model": "Hiace", "capacity": 14}, headers=headers)
    assert r.status_code == 403


def test_duplicate_plate_rejected(client):
    headers = register_and_login(client, "admin3@govanmail.dev", role="admin")
    client.post("/vehicles/", json={"plate_number": "LEB-200", "model": "Hiace"}, headers=headers)
    r = client.post("/vehicles/", json={"plate_number": "LEB-200", "model": "Coaster"}, headers=headers)
    assert r.status_code == 400


def test_list_vehicles_requires_auth(client):
    r = client.get("/vehicles/")
    assert r.status_code == 401


def test_admin_can_edit_vehicle_and_restore_active_status(client):
    headers = register_and_login(client, "vehicle-edit-admin@govanmail.dev", role="admin")
    created = client.post("/vehicles/", json={
        "plate_number": "EDIT-101",
        "model": "Van",
        "capacity": 8,
    }, headers=headers)
    vehicle_id = created.json()["id"]

    edited = client.patch(f"/vehicles/{vehicle_id}", json={
        "plate_number": "EDIT-102",
        "model": "Updated Van",
        "capacity": 10,
        "ownership_type": "external",
    }, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["plate_number"] == "EDIT-102"
    assert edited.json()["model"] == "Updated Van"
    assert edited.json()["capacity"] == 10
    assert edited.json()["ownership_type"] == "external"

    assert client.patch(
        f"/vehicles/{vehicle_id}/status",
        json={"status": "offline"},
        headers=headers,
    ).status_code == 200
    reactivated = client.patch(
        f"/vehicles/{vehicle_id}/status",
        json={"status": "active"},
        headers=headers,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"


def test_vehicle_edit_rejects_duplicate_plate(client):
    headers = register_and_login(client, "vehicle-duplicate-admin@govanmail.dev", role="admin")
    first = client.post("/vehicles/", json={"plate_number": "DUP-1", "model": "Van"}, headers=headers).json()
    second = client.post("/vehicles/", json={"plate_number": "DUP-2", "model": "Van"}, headers=headers).json()
    response = client.patch(
        f"/vehicles/{second['id']}",
        json={"plate_number": "DUP-1"},
        headers=headers,
    )
    assert response.status_code == 400
    assert first["id"] != second["id"]


def test_non_admin_cannot_edit_vehicle(client):
    admin = register_and_login(client, "vehicle-permission-admin@govanmail.dev", role="admin")
    passenger = register_and_login(client, "vehicle-permission-passenger@govanmail.dev")
    vehicle = client.post(
        "/vehicles/",
        json={"plate_number": "PERM-101", "model": "Van"},
        headers=admin,
    ).json()
    response = client.patch(
        f"/vehicles/{vehicle['id']}",
        json={"model": "Unauthorized"},
        headers=passenger,
    )
    assert response.status_code == 403
