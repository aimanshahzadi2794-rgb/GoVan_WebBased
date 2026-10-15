from .conftest import register_and_login


def _create_user(client, headers, name, email, role):
    response = client.post("/users/", json={
        "name": name,
        "email": email,
        "password": "Passw0rd!",
        "role": role,
    }, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_admin_can_link_list_and_unlink_guardian(client):
    admin_headers = register_and_login(client, "guardians-admin@example.com", role="admin")
    guardian = _create_user(
        client, admin_headers, "Guardian Account", "guardian@example.com", "guardian"
    )
    passenger = _create_user(
        client, admin_headers, "Passenger Account", "passenger@example.com", "passenger"
    )

    linked = client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "Mother"},
        headers=admin_headers,
    )
    assert linked.status_code == 201
    assert linked.json() == {
        "id": linked.json()["id"],
        "guardian_id": guardian["id"],
        "passenger_id": passenger["id"],
        "relationship": "Mother",
    }

    listed = client.get(f"/users/{passenger['id']}/guardians", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json() == [linked.json()]

    duplicate = client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "Parent"},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409

    unlinked = client.delete(
        f"/users/{passenger['id']}/guardians/{guardian['id']}",
        headers=admin_headers,
    )
    assert unlinked.status_code == 204
    assert client.get(
        f"/users/{passenger['id']}/guardians", headers=admin_headers
    ).json() == []


def test_guardian_links_require_admin_and_correct_roles(client):
    admin_headers = register_and_login(client, "guardians-role-admin@example.com", role="admin")
    passenger_headers = register_and_login(client, "guardians-user@example.com")
    guardian = _create_user(
        client, admin_headers, "Role Guardian", "role-guardian@example.com", "guardian"
    )
    passenger = _create_user(
        client, admin_headers, "Role Passenger", "role-passenger@example.com", "passenger"
    )
    driver = _create_user(
        client, admin_headers, "Role Driver", "role-driver@example.com", "driver"
    )

    assert client.get(
        f"/users/{passenger['id']}/guardians", headers=passenger_headers
    ).status_code == 403
    assert client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "Parent"},
        headers=passenger_headers,
    ).status_code == 403
    linked = client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "Parent"},
        headers=admin_headers,
    )
    assert linked.status_code == 201
    assert client.delete(
        f"/users/{passenger['id']}/guardians/{guardian['id']}",
        headers=passenger_headers,
    ).status_code == 403
    assert client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": driver["id"], "relationship": "Parent"},
        headers=admin_headers,
    ).status_code == 400
    assert client.post(
        f"/users/{driver['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "Parent"},
        headers=admin_headers,
    ).status_code == 400
    assert client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian["id"], "relationship": "   "},
        headers=admin_headers,
    ).status_code == 400


def test_guardian_can_only_list_linked_passengers(client):
    admin_headers = register_and_login(client, "guardian-list-admin@example.com", role="admin")
    guardian_headers = register_and_login(client, "guardian-list-user@example.com", role="guardian")
    other_guardian_headers = register_and_login(
        client, "guardian-list-other@example.com", role="guardian"
    )
    passenger = _create_user(
        client, admin_headers, "Linked Passenger", "linked-passenger@example.com", "passenger"
    )
    unlinked = _create_user(
        client, admin_headers, "Unlinked Passenger", "unlinked-passenger@example.com", "passenger"
    )
    guardian_id = client.get("/auth/me", headers=guardian_headers).json()["id"]
    admin_link = client.post(
        f"/users/{passenger['id']}/guardians",
        json={"guardian_id": guardian_id, "relationship": "Father"},
        headers=admin_headers,
    )
    assert admin_link.status_code == 201

    listed = client.get("/guardian/passengers", headers=guardian_headers)
    assert listed.status_code == 200
    assert listed.json() == [{
        "id": passenger["id"],
        "name": passenger["name"],
        "email": passenger["email"],
        "relationship": "Father",
    }]
    assert all(item["id"] != unlinked["id"] for item in listed.json())
    assert client.get("/guardian/passengers", headers=other_guardian_headers).json() == []
    assert client.get("/guardian/passengers", headers=admin_headers).status_code == 403
    assert client.get(
        "/guardian/passengers",
        headers=register_and_login(client, "guardian-list-passenger@example.com"),
    ).status_code == 403
