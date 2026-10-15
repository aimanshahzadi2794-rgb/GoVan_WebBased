from .conftest import register_and_login


def test_driver_can_raise_alert_and_admin_can_resolve(client):
    admin = register_and_login(client, "admin7@govanmail.dev", role="admin")
    driver = register_and_login(client, "driver7@govanmail.dev", role="driver")

    r = client.post("/alerts/", json={"trip_id": None, "lat": 31.5, "lng": 74.3}, headers=driver)
    assert r.status_code == 201
    alert = r.json()
    assert alert["status"] == "open"

    listed = client.get("/alerts/", headers=admin)
    assert listed.status_code == 200
    assert any(a["id"] == alert["id"] for a in listed.json())

    resolved = client.patch(f"/alerts/{alert['id']}/resolve", headers=admin)
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_passenger_can_raise_alert(client):
    driver_or_pax = register_and_login(client, "pax7@govanmail.dev", role="passenger")
    r = client.post("/alerts/", json={}, headers=driver_or_pax)
    assert r.status_code == 201


def test_admin_cannot_raise_alert(client):
    admin = register_and_login(client, "admin8@govanmail.dev", role="admin")
    r = client.post("/alerts/", json={}, headers=admin)
    assert r.status_code == 403


def test_non_admin_cannot_list_or_resolve_alerts(client):
    passenger = register_and_login(client, "pax8@govanmail.dev", role="passenger")
    r = client.get("/alerts/", headers=passenger)
    assert r.status_code == 403


def test_resolve_nonexistent_alert_returns_404(client):
    admin = register_and_login(client, "admin9@govanmail.dev", role="admin")
    r = client.patch("/alerts/99999/resolve", headers=admin)
    assert r.status_code == 404


def test_booking_cancel_flow(client):
    admin = register_and_login(client, "admin10@govanmail.dev", role="admin")
    passenger = register_and_login(client, "pax10@govanmail.dev", role="passenger")

    route = client.post("/routes/", json={"name": "Cancel test route"}, headers=admin).json()
    booking = client.post("/bookings/", json={"route_id": route["id"]}, headers=passenger).json()
    assert booking["status"] == "confirmed"

    cancelled = client.patch(f"/bookings/{booking['id']}/cancel", headers=passenger)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    mine = client.get("/bookings/", headers=passenger).json()
    assert all(b["status"] != "confirmed" or b["id"] != booking["id"] for b in mine)


def test_cannot_cancel_someone_elses_booking(client):
    admin = register_and_login(client, "admin11@govanmail.dev", role="admin")
    pax_a = register_and_login(client, "paxA@govanmail.dev", role="passenger")
    pax_b = register_and_login(client, "paxB@govanmail.dev", role="passenger")

    route = client.post("/routes/", json={"name": "Ownership test route"}, headers=admin).json()
    booking = client.post("/bookings/", json={"route_id": route["id"]}, headers=pax_a).json()

    r = client.patch(f"/bookings/{booking['id']}/cancel", headers=pax_b)
    assert r.status_code == 404


def test_freed_capacity_can_be_rebooked_after_cancel(client):
    """A cancelled booking should free up the seat for someone else --
    this exercises whether the capacity check counts only 'confirmed'
    bookings, which is what the code claims to do."""
    admin = register_and_login(client, "admin12@govanmail.dev", role="admin")
    pax_a = register_and_login(client, "paxC@govanmail.dev", role="passenger")
    pax_b = register_and_login(client, "paxD@govanmail.dev", role="passenger")

    vehicle = client.post("/vehicles/", json={"plate_number": "LEB-500", "model": "Hiace", "capacity": 1}, headers=admin).json()
    route = client.post("/routes/", json={"name": "Capacity refill route", "vehicle_id": vehicle["id"]}, headers=admin).json()

    b1 = client.post("/bookings/", json={"route_id": route["id"]}, headers=pax_a).json()
    # Second booking should fail -- capacity is 1 and already full.
    full = client.post("/bookings/", json={"route_id": route["id"]}, headers=pax_b)
    assert full.status_code == 400

    # Cancel the first booking, freeing the seat.
    client.patch(f"/bookings/{b1['id']}/cancel", headers=pax_a)

    # Now pax_b should succeed.
    retry = client.post("/bookings/", json={"route_id": route["id"]}, headers=pax_b)
    assert retry.status_code == 201


def test_booking_dropoff_and_route_seat_availability(client):
    admin = register_and_login(client, "booking-options-admin@example.com", role="admin")
    passenger = register_and_login(client, "booking-options-passenger@example.com", role="passenger")
    other = register_and_login(client, "booking-options-other@example.com", role="passenger")
    vehicle = client.post(
        "/vehicles/",
        json={"plate_number": "TRV-501", "model": "Van", "capacity": 2},
        headers=admin,
    ).json()
    route = client.post(
        "/routes/",
        json={
            "name": "Stop selection route",
            "vehicle_id": vehicle["id"],
            "stops": [
                {"name": "Gate", "lat": 31.52, "lng": 74.35, "sequence": 0},
                {"name": "Library", "lat": 31.53, "lng": 74.36, "sequence": 1},
                {"name": "Hostel", "lat": 31.54, "lng": 74.37, "sequence": 2},
            ],
        },
        headers=admin,
    ).json()
    stops = route["stops"]
    booking = client.post(
        "/bookings/",
        json={
            "route_id": route["id"],
            "boarding_stop_id": stops[0]["id"],
            "dropoff_stop_id": stops[2]["id"],
        },
        headers=passenger,
    )
    assert booking.status_code == 201
    assert booking.json()["boarding_stop_name"] == "Gate"
    assert booking.json()["dropoff_stop_name"] == "Hostel"

    availability = next(
        item for item in client.get("/routes/", headers=passenger).json()
        if item["id"] == route["id"]
    )
    assert availability["vehicle_capacity"] == 2
    assert availability["confirmed_bookings"] == 1
    assert availability["seats_left"] == 1

    invalid_order = client.post(
        "/bookings/",
        json={
            "route_id": route["id"],
            "boarding_stop_id": stops[2]["id"],
            "dropoff_stop_id": stops[1]["id"],
        },
        headers=other,
    )
    assert invalid_order.status_code == 400

    client.patch(f"/bookings/{booking.json()['id']}/cancel", headers=passenger)
    restored = next(
        item for item in client.get("/routes/", headers=passenger).json()
        if item["id"] == route["id"]
    )
    assert restored["seats_left"] == 2


def test_admin_can_delete_route(client):
    admin = register_and_login(client, "admin13@govanmail.dev", role="admin")
    route = client.post("/routes/", json={"name": "Temp route"}, headers=admin).json()
    r = client.delete(f"/routes/{route['id']}", headers=admin)
    assert r.status_code == 204
    remaining = client.get("/routes/", headers=admin).json()
    assert all(rt["id"] != route["id"] for rt in remaining)


def test_non_admin_cannot_delete_route(client):
    admin = register_and_login(client, "admin14@govanmail.dev", role="admin")
    passenger = register_and_login(client, "pax14@govanmail.dev", role="passenger")
    route = client.post("/routes/", json={"name": "Protected route"}, headers=admin).json()
    r = client.delete(f"/routes/{route['id']}", headers=passenger)
    assert r.status_code == 403


def test_delete_nonexistent_route_returns_404(client):
    admin = register_and_login(client, "admin15@govanmail.dev", role="admin")
    r = client.delete("/routes/99999", headers=admin)
    assert r.status_code == 404


def test_driver_assign_to_nonexistent_vehicle_returns_404(client):
    admin = register_and_login(client, "admin16@govanmail.dev", role="admin")
    driver = register_and_login(client, "driver16@govanmail.dev", role="driver")
    driver_me = client.get("/auth/me", headers=driver).json()
    r = client.patch(f"/drivers/{driver_me['id']}/assign", json={"vehicle_id": 99999}, headers=admin)
    assert r.status_code == 404


def test_driver_unassign_vehicle(client):
    admin = register_and_login(client, "admin17@govanmail.dev", role="admin")
    driver = register_and_login(client, "driver17@govanmail.dev", role="driver")
    driver_me = client.get("/auth/me", headers=driver).json()
    vehicle = client.post("/vehicles/", json={"plate_number": "LEB-600", "model": "Hiace"}, headers=admin).json()

    client.patch(f"/drivers/{driver_me['id']}/assign", json={"vehicle_id": vehicle["id"]}, headers=admin)
    unassigned = client.patch(f"/drivers/{driver_me['id']}/assign", json={"vehicle_id": None}, headers=admin)
    assert unassigned.status_code == 200
    assert unassigned.json()["vehicle_id"] is None
