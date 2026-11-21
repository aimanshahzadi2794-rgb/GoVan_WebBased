from .conftest import register_and_login


def _create_organization(client, headers, name):
    response = client.post(
        "/organizations/",
        json={"name": name, "type": "company"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_user(client, headers, name, email, role, organization_id):
    response = client.post(
        "/users/",
        json={
            "name": name,
            "email": email,
            "password": "Passw0rd!",
            "role": role,
            "organization_id": organization_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_organization_managers_are_scoped_on_lists_and_direct_ids(client):
    super_admin = register_and_login(
        client, "tenant-super@example.com", role="super_admin"
    )
    org_a = _create_organization(client, super_admin, "North School")
    org_b = _create_organization(client, super_admin, "South School")

    manager_a = _create_user(
        client, super_admin, "Manager A", "manager-a@example.com",
        "fleet_manager", org_a["id"],
    )
    manager_b = _create_user(
        client, super_admin, "Manager B", "manager-b@example.com",
        "organization_admin", org_b["id"],
    )
    # Manager accounts are provisioned by the platform administrator; obtain
    # their sessions without going through public registration.
    login_a = client.post("/auth/login", data={
        "username": manager_a["email"], "password": "Passw0rd!",
    })
    login_b = client.post("/auth/login", data={
        "username": manager_b["email"], "password": "Passw0rd!",
    })
    manager_a_headers = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    manager_b_headers = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    driver_a = _create_user(
        client, super_admin, "Driver A", "driver-a@example.com", "driver", org_a["id"]
    )
    driver_b = _create_user(
        client, super_admin, "Driver B", "driver-b@example.com", "driver", org_b["id"]
    )
    passenger_a = _create_user(
        client, super_admin, "Passenger A", "passenger-a@example.com", "passenger", org_a["id"]
    )

    vehicle_a = client.post("/vehicles/", json={
        "plate_number": "TENANT-A-1", "model": "Van", "capacity": 8,
        "organization_id": org_a["id"],
    }, headers=super_admin).json()
    vehicle_b = client.post("/vehicles/", json={
        "plate_number": "TENANT-B-1", "model": "Van", "capacity": 8,
        "organization_id": org_b["id"],
    }, headers=super_admin).json()
    route_a = client.post("/routes/", json={
        "name": "North Route", "organization_id": org_a["id"],
        "vehicle_id": vehicle_a["id"],
        "stops": [{"name": "North Gate", "lat": 31.52, "lng": 74.35, "sequence": 0}],
    }, headers=super_admin).json()
    route_b = client.post("/routes/", json={
        "name": "South Route", "organization_id": org_b["id"],
        "vehicle_id": vehicle_b["id"],
        "stops": [{"name": "South Gate", "lat": 31.53, "lng": 74.36, "sequence": 0}],
    }, headers=super_admin).json()
    trip_b = client.post("/trips/", json={
        "route_id": route_b["id"], "driver_id": driver_b["id"],
    }, headers=super_admin).json()

    assert [v["id"] for v in client.get("/vehicles/", headers=manager_a_headers).json()] == [vehicle_a["id"]]
    assert [r["id"] for r in client.get("/routes/", headers=manager_a_headers).json()] == [route_a["id"]]
    assert {u["id"] for u in client.get("/users/", headers=manager_a_headers).json()} == {
        manager_a["id"], driver_a["id"], passenger_a["id"]
    }

    assert client.patch(
        f"/vehicles/{vehicle_b['id']}", json={"model": "Changed"}, headers=manager_a_headers
    ).status_code == 404
    assert client.patch(
        f"/routes/{route_b['id']}", json={"name": "Changed"}, headers=manager_a_headers
    ).status_code == 404
    assert client.patch(
        f"/users/{driver_b['id']}", json={"name": "Changed"}, headers=manager_a_headers
    ).status_code == 404
    assert client.get(
        f"/trips/{trip_b['id']}/path", headers=manager_a_headers
    ).status_code == 404
    assert client.patch(
        f"/drivers/{driver_a['id']}/assign",
        json={"vehicle_id": vehicle_b["id"]},
        headers=manager_a_headers,
    ).status_code == 404
    assert client.post(
        "/trips/",
        json={"route_id": route_b["id"], "driver_id": driver_a["id"]},
        headers=manager_a_headers,
    ).status_code == 404
    assert client.get(
        f"/reports/summary?organization_id={org_b['id']}", headers=manager_a_headers
    ).status_code == 404
    passenger_login = client.post("/auth/login", data={
        "username": passenger_a["email"], "password": "Passw0rd!",
    })
    passenger_a_headers = {"Authorization": f"Bearer {passenger_login.json()['access_token']}"}
    assert client.post(
        "/bookings/", json={"route_id": route_b["id"]},
        headers=passenger_a_headers,
    ).status_code == 404

    own_logs = client.get("/audit-logs/", headers=manager_a_headers)
    assert own_logs.status_code == 200
    assert all(entry["organization_id"] == org_a["id"] for entry in own_logs.json())


def test_public_registration_cannot_assign_an_organization(client):
    admin = register_and_login(client, "registration-super@example.com", role="super_admin")
    organization = _create_organization(client, admin, "Protected School")
    response = client.post("/auth/register", json={
        "name": "Injected Manager",
        "email": "injected-manager@example.com",
        "password": "Passw0rd!",
        "role": "passenger",
        "organization_id": organization["id"],
    })
    assert response.status_code == 403


def test_suspended_organization_blocks_existing_sessions_and_login(client):
    super_admin = register_and_login(
        client, "suspend-super@example.com", role="super_admin"
    )
    organization = _create_organization(client, super_admin, "Suspension School")
    manager = _create_user(
        client, super_admin, "Suspended Manager", "suspended-manager@example.com",
        "fleet_manager", organization["id"],
    )
    login = client.post("/auth/login", data={
        "username": manager["email"], "password": "Passw0rd!",
    })
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    suspended = client.patch(
        f"/organizations/{organization['id']}", json={"is_active": False}, headers=super_admin
    )
    assert suspended.status_code == 200
    assert suspended.json()["is_active"] is False
    assert client.get("/users/", headers=manager_headers).status_code == 403
    assert client.post("/auth/login", data={
        "username": manager["email"], "password": "Passw0rd!",
    }).status_code == 403
