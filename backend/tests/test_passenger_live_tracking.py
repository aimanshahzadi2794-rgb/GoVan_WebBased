from .conftest import register_and_login


def _create_route(client, admin_headers, name, plate):
    vehicle = client.post(
        "/vehicles/",
        json={"plate_number": plate, "model": "Van"},
        headers=admin_headers,
    ).json()
    route = client.post(
        "/routes/",
        json={
            "name": name,
            "vehicle_id": vehicle["id"],
            "stops": [
                {"name": "Gate", "lat": 31.52, "lng": 74.35, "sequence": 0},
                {"name": "Library", "lat": 31.53, "lng": 74.36, "sequence": 1},
            ],
        },
        headers=admin_headers,
    ).json()
    return route


def _start_trip(client, admin_headers, driver_headers, route):
    driver_id = client.get("/auth/me", headers=driver_headers).json()["id"]
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_id},
        headers=admin_headers,
    ).json()
    assert client.post(f"/trips/{trip['id']}/start", headers=driver_headers).status_code == 200
    location = client.post(
        f"/trips/{trip['id']}/location",
        json={"lat": 31.50, "lng": 74.30},
        headers=driver_headers,
    )
    assert location.status_code == 200
    return trip


def test_passenger_tracking_is_scoped_to_confirmed_booked_routes(client):
    admin = register_and_login(client, "live-admin@example.com", role="admin")
    driver = register_and_login(client, "live-driver@example.com", role="driver")
    passenger = register_and_login(client, "live-passenger@example.com")
    other_passenger = register_and_login(client, "live-other-passenger@example.com")

    booked_route = _create_route(client, admin, "Booked route", "LIVE-101")
    unbooked_route = _create_route(client, admin, "Unbooked route", "LIVE-202")
    booking = client.post(
        "/bookings/",
        json={
            "route_id": booked_route["id"],
            "boarding_stop_id": booked_route["stops"][1]["id"],
        },
        headers=passenger,
    )
    assert booking.status_code == 201
    assert booking.json()["boarding_stop_id"] == booked_route["stops"][1]["id"]
    other_booking = client.post(
        "/bookings/",
        json={"route_id": unbooked_route["id"]},
        headers=other_passenger,
    )
    assert other_booking.status_code == 201

    booked_trip = _start_trip(client, admin, driver, booked_route)
    _start_trip(client, admin, driver, unbooked_route)

    response = client.get("/trips/active-for-me", headers=passenger)
    assert response.status_code == 200
    trips = response.json()
    assert len(trips) == 1
    assert trips[0]["id"] == booked_trip["id"]
    assert trips[0]["route_name"] == "Booked route"
    assert trips[0]["driver_name"] == "Test User"
    assert trips[0]["vehicle_plate"] == "LIVE-101"
    assert trips[0]["status"] == "active"
    assert trips[0]["boarding_stop_name"] == "Library"
    assert trips[0]["next_stop_name"] == "Gate"
    assert isinstance(trips[0]["eta_minutes"], int)
    assert [stop["name"] for stop in trips[0]["stops"]] == ["Gate", "Library"]

    passenger_trip_list = client.get("/trips/", headers=passenger)
    assert {trip["route_id"] for trip in passenger_trip_list.json()} == {booked_route["id"]}
    other_passenger_id = client.get("/auth/me", headers=other_passenger).json()["id"]
    assert client.get(
        f"/trips/active-for-me?passenger_id={other_passenger_id}",
        headers=passenger,
    ).status_code == 403


def test_guardian_tracking_requires_link_and_only_returns_linked_passenger(client):
    admin = register_and_login(client, "guardian-live-admin@example.com", role="admin")
    driver = register_and_login(client, "guardian-live-driver@example.com", role="driver")
    guardian = register_and_login(client, "guardian-live@example.com", role="guardian")
    linked_passenger = register_and_login(client, "linked-live-passenger@example.com")
    unlinked_passenger = register_and_login(client, "unlinked-live-passenger@example.com")
    linked_passenger_id = client.get("/auth/me", headers=linked_passenger).json()["id"]
    unlinked_passenger_id = client.get("/auth/me", headers=unlinked_passenger).json()["id"]
    guardian_id = client.get("/auth/me", headers=guardian).json()["id"]

    route = _create_route(client, admin, "Guardian route", "GUARD-101")
    booking = client.post(
        "/bookings/",
        json={"route_id": route["id"]},
        headers=linked_passenger,
    )
    assert booking.status_code == 201
    trip = _start_trip(client, admin, driver, route)
    linked = client.post(
        f"/users/{linked_passenger_id}/guardians",
        json={"guardian_id": guardian_id, "relationship": "Parent"},
        headers=admin,
    )
    assert linked.status_code == 201

    all_linked = client.get("/trips/active-for-me", headers=guardian)
    assert all_linked.status_code == 200
    assert len(all_linked.json()) == 1
    assert all_linked.json()[0]["id"] == trip["id"]
    assert all_linked.json()[0]["passenger_id"] == linked_passenger_id
    assert client.get(
        f"/trips/active-for-me?passenger_id={linked_passenger_id}",
        headers=guardian,
    ).status_code == 200
    assert client.get(
        f"/trips/active-for-me?passenger_id={unlinked_passenger_id}",
        headers=guardian,
    ).status_code == 403
    assert client.get("/trips/active-for-me", headers=admin).status_code == 403
    assert client.get("/trips/active-for-me").status_code == 401


def test_booking_rejects_boarding_stop_from_another_route(client):
    admin = register_and_login(client, "boarding-stop-admin@example.com", role="admin")
    passenger = register_and_login(client, "boarding-stop-passenger@example.com")
    first_route = _create_route(client, admin, "First boarding route", "BOARD-101")
    second_route = _create_route(client, admin, "Second boarding route", "BOARD-202")
    response = client.post(
        "/bookings/",
        json={
            "route_id": first_route["id"],
            "boarding_stop_id": second_route["stops"][0]["id"],
        },
        headers=passenger,
    )
    assert response.status_code == 400
