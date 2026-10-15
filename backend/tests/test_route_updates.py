from .conftest import register_and_login


def test_admin_can_edit_route_stops_and_schedule(client):
    admin = register_and_login(client, "route-edit-admin@example.com", role="admin")
    created = client.post("/routes/", json={
        "name": "Weekday route",
        "pickup_time": "08:00",
        "drop_time": "09:00",
        "days_of_week": [0, 2, 4],
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "stops": [{"name": "Old stop", "lat": 31.5, "lng": 74.3, "sequence": 0}],
    }, headers=admin)
    assert created.status_code == 201
    route_id = created.json()["id"]

    updated = client.patch(f"/routes/{route_id}", json={
        "name": "Updated weekday route",
        "pickup_time": "07:30",
        "drop_time": "08:30",
        "days_of_week": [1, 3, 5],
        "valid_from": "2026-02-01",
        "valid_to": "2026-11-30",
        "stops": [
            {"name": "First", "lat": 31.51, "lng": 74.31, "sequence": 0},
            {"name": "Second", "lat": 31.52, "lng": 74.32, "sequence": 1},
        ],
    }, headers=admin)
    assert updated.status_code == 200
    result = updated.json()
    assert result["name"] == "Updated weekday route"
    assert result["pickup_time"] == "07:30"
    assert result["days_of_week"] == [1, 3, 5]
    assert result["valid_from"] == "2026-02-01"
    assert result["valid_to"] == "2026-11-30"
    assert [stop["name"] for stop in result["stops"]] == ["First", "Second"]


def test_route_schedule_rejects_invalid_dates_and_weekdays(client):
    admin = register_and_login(client, "route-validation-admin@example.com", role="admin")
    invalid_dates = client.post("/routes/", json={
        "name": "Invalid date route",
        "valid_from": "2026-12-31",
        "valid_to": "2026-01-01",
    }, headers=admin)
    assert invalid_dates.status_code == 422

    invalid_weekday = client.post("/routes/", json={
        "name": "Invalid weekday route",
        "days_of_week": [7],
    }, headers=admin)
    assert invalid_weekday.status_code == 422


def test_route_cannot_be_edited_or_deleted_during_active_trip(client):
    admin = register_and_login(client, "route-active-admin@example.com", role="admin")
    driver = register_and_login(client, "route-active-driver@example.com", role="driver")
    driver_id = client.get("/auth/me", headers=driver).json()["id"]
    route = client.post("/routes/", json={"name": "Active route"}, headers=admin).json()
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_id},
        headers=admin,
    ).json()
    assert client.post(f"/trips/{trip['id']}/start", headers=driver).status_code == 200

    edit = client.patch(f"/routes/{route['id']}", json={"name": "Changed"}, headers=admin)
    assert edit.status_code == 409
    delete = client.delete(f"/routes/{route['id']}", headers=admin)
    assert delete.status_code == 409

    assert client.post(f"/trips/{trip['id']}/end", headers=driver).status_code == 200
    edit_after_trip = client.patch(f"/routes/{route['id']}", json={"name": "Changed"}, headers=admin)
    assert edit_after_trip.status_code == 200


def test_non_admin_cannot_edit_route(client):
    admin = register_and_login(client, "route-permission-admin@example.com", role="admin")
    passenger = register_and_login(client, "route-permission-passenger@example.com")
    route = client.post(
        "/routes/",
        json={"name": "Protected route"},
        headers=admin,
    ).json()
    response = client.patch(
        f"/routes/{route['id']}",
        json={"name": "Unauthorized edit"},
        headers=passenger,
    )
    assert response.status_code == 403
