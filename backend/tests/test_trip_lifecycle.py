from datetime import timedelta

from .conftest import TestingSessionLocal, models, register_and_login


def test_full_trip_and_booking_flow(client):
    admin = register_and_login(client, "admin4@govanmail.dev", role="admin")
    driver = register_and_login(client, "driver4@govanmail.dev", role="driver")
    passenger = register_and_login(client, "pax4@govanmail.dev", role="passenger")

    # Admin sets up a vehicle and route.
    v = client.post("/vehicles/", json={"plate_number": "LEB-300", "model": "Hiace", "capacity": 1}, headers=admin).json()
    r = client.post("/routes/", json={
        "name": "Campus loop",
        "stops": [
            {"name": "Gate", "lat": 31.52, "lng": 74.35, "sequence": 0},
            {"name": "Library", "lat": 31.53, "lng": 74.36, "sequence": 1},
            {"name": "Hostel", "lat": 31.54, "lng": 74.37, "sequence": 2},
        ],
        "vehicle_id": v["id"],
    }, headers=admin).json()

    # Admin assigns the driver to the vehicle.
    driver_me = client.get("/auth/me", headers=driver).json()
    client.patch(f"/drivers/{driver_me['id']}/assign", json={"vehicle_id": v["id"]}, headers=admin)

    # Passenger books a seat (capacity=1, so this should succeed).
    b = client.post("/bookings/", json={"route_id": r["id"]}, headers=passenger)
    assert b.status_code == 201

    # A second passenger should be rejected -- capacity is full.
    passenger2 = register_and_login(client, "pax5@govanmail.dev", role="passenger")
    b2 = client.post("/bookings/", json={"route_id": r["id"]}, headers=passenger2)
    assert b2.status_code == 400

    # Admin schedules a trip for the driver.
    t = client.post("/trips/", json={"route_id": r["id"], "driver_id": driver_me["id"]}, headers=admin).json()

    # Driver starts the trip, sends a location ping, then ends it.
    started = client.post(f"/trips/{t['id']}/start", headers=driver).json()
    assert started["status"] == "active"

    for lat, lng, accuracy in [
        (31.5201, 74.35, 8),
        (31.5202, 74.35, 8),
        (31.522, 74.35, 8),
    ]:
        location = client.post(
            f"/trips/{t['id']}/location",
            json={"lat": lat, "lng": lng, "accuracy": accuracy},
            headers=driver,
        ).json()
    assert location["last_lat"] == 31.522
    assert location["last_accuracy"] == 8

    active_path = client.get(f"/trips/{t['id']}/path", headers=admin)
    assert active_path.status_code == 200
    assert len(active_path.json()) == 3

    stop_events_response = client.get(f"/trips/{t['id']}/stops", headers=admin)
    assert stop_events_response.status_code == 200
    assert len(stop_events_response.json()) == 1
    stop_event = stop_events_response.json()[0]
    assert stop_event["stop_id"] == r["stops"][0]["id"]
    assert stop_event["departed_at"] is not None
    assert stop_event["dwell_seconds"] is not None
    assert stop_event["long_stop"] is False

    db = TestingSessionLocal()
    try:
        event = db.query(models.TripStopEvent).filter(
            models.TripStopEvent.trip_id == t["id"]
        ).one()
        event.arrived_at = event.departed_at - timedelta(seconds=300)
        db.commit()
    finally:
        db.close()

    boundary_response = client.get(f"/trips/{t['id']}/stops", headers=admin)
    assert boundary_response.status_code == 200
    boundary_event = boundary_response.json()[0]
    assert boundary_event["dwell_seconds"] == 300
    assert boundary_event["long_stop"] is False

    db = TestingSessionLocal()
    try:
        event = db.query(models.TripStopEvent).filter(
            models.TripStopEvent.trip_id == t["id"]
        ).one()
        event.arrived_at = event.departed_at - timedelta(seconds=301)
        db.commit()
    finally:
        db.close()

    long_stop_response = client.get(f"/trips/{t['id']}/stops", headers=admin)
    assert long_stop_response.status_code == 200
    long_stop = long_stop_response.json()[0]
    assert long_stop["dwell_seconds"] == 301
    assert long_stop["long_stop"] is True

    ended = client.post(f"/trips/{t['id']}/end", headers=driver).json()
    assert ended["status"] == "completed"

    completed_path = client.get(f"/trips/{t['id']}/path", headers=admin)
    assert completed_path.status_code == 200
    assert [point["lat"] for point in completed_path.json()] == [31.5201, 31.5202, 31.522]

    passenger_history_path = client.get(f"/trips/{t['id']}/path", headers=passenger)
    assert passenger_history_path.status_code == 403
    passenger_stops = client.get(f"/trips/{t['id']}/stops", headers=passenger)
    assert passenger_stops.status_code == 403
    assert client.post(f"/trips/{t['id']}/start", headers=driver).status_code == 400
    assert client.post(f"/trips/{t['id']}/end", headers=driver).status_code == 400

    # Passenger can see it as trip history via the list endpoint (role-scoped).
    trips_for_passenger = client.get("/trips/", headers=passenger).json()
    assert isinstance(trips_for_passenger, list)


def test_driver_cannot_control_another_drivers_trip(client):
    admin = register_and_login(client, "admin6@govanmail.dev", role="admin")
    driver_a = register_and_login(client, "driverA@govanmail.dev", role="driver")
    driver_b = register_and_login(client, "driverB@govanmail.dev", role="driver")

    v = client.post("/vehicles/", json={"plate_number": "LEB-400", "model": "Hiace"}, headers=admin).json()
    r = client.post("/routes/", json={"name": "Route X", "vehicle_id": v["id"]}, headers=admin).json()
    a_me = client.get("/auth/me", headers=driver_a).json()
    t = client.post("/trips/", json={"route_id": r["id"], "driver_id": a_me["id"]}, headers=admin).json()

    # Driver B tries to start Driver A's trip.
    resp = client.post(f"/trips/{t['id']}/start", headers=driver_b)
    assert resp.status_code == 404
    path_resp = client.get(f"/trips/{t['id']}/path", headers=driver_b)
    assert path_resp.status_code == 403
    stops_resp = client.get(f"/trips/{t['id']}/stops", headers=driver_a)
    assert stops_resp.status_code == 200
    assert client.get(f"/trips/{t['id']}/stops", headers=driver_b).status_code == 404


def test_driver_can_mark_next_stop_and_edit_own_profile(client):
    admin = register_and_login(client, "driver-actions-admin@example.com", role="admin")
    driver = register_and_login(client, "driver-actions-driver@example.com", role="driver")
    passenger = register_and_login(client, "driver-actions-passenger@example.com", role="passenger")
    driver_user = client.get("/auth/me", headers=driver).json()
    route = client.post(
        "/routes/",
        json={
            "name": "Driver action route",
            "stops": [
                {"name": "First", "lat": 31.52, "lng": 74.35, "sequence": 0},
                {"name": "Second", "lat": 31.53, "lng": 74.36, "sequence": 1},
            ],
        },
        headers=admin,
    ).json()
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_user["id"]},
        headers=admin,
    ).json()

    assert client.post(f"/trips/{trip['id']}/end", headers=driver).status_code == 400
    assert client.post(f"/trips/{trip['id']}/start", headers=driver).status_code == 200
    assert client.post(f"/trips/{trip['id']}/start", headers=driver).status_code == 400

    reached = client.post(
        f"/trips/{trip['id']}/stops/{route['stops'][0]['id']}/reached",
        headers=driver,
    )
    assert reached.status_code == 201
    assert reached.json()["stop_name"] == "First"
    assert client.post(
        f"/trips/{trip['id']}/stops/{route['stops'][0]['id']}/reached",
        headers=driver,
    ).status_code == 409
    assert client.post(
        f"/trips/{trip['id']}/stops/{route['stops'][1]['id']}/reached",
        headers=passenger,
    ).status_code == 403

    events = client.get(f"/trips/{trip['id']}/stops", headers=driver)
    assert events.status_code == 200
    assert events.json()[0]["stop_name"] == "First"

    profile = client.patch(
        "/drivers/me/profile",
        json={
            "phone": "+1-555-0100",
            "license_number": "LIC-54321",
            "license_expiry": "2030-12-31",
        },
        headers=driver,
    )
    assert profile.status_code == 200
    assert profile.json()["phone"] == "+1-555-0100"
    assert profile.json()["license_number"] == "LIC-54321"
    assert profile.json()["license_expiry"] == "2030-12-31"
    assert client.patch(
        "/drivers/me/profile",
        json={"phone": "unauthorized"},
        headers=passenger,
    ).status_code == 403


def test_admin_trip_path_returns_three_locations_in_order(client):
    admin = register_and_login(client, "path-admin@govanmail.dev", role="admin")
    driver = register_and_login(client, "path-driver@govanmail.dev", role="driver")
    driver_me = client.get("/auth/me", headers=driver).json()
    route = client.post("/routes/", json={"name": "Path route"}, headers=admin).json()
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_me["id"]},
        headers=admin,
    ).json()
    client.post(f"/trips/{trip['id']}/start", headers=driver)

    points = [
        {"lat": 31.1, "lng": 74.1},
        {"lat": 31.2, "lng": 74.2},
        {"lat": 31.3, "lng": 74.3},
    ]
    for point in points:
        response = client.post(f"/trips/{trip['id']}/location", json=point, headers=driver)
        assert response.status_code == 200

    path_response = client.get(f"/trips/{trip['id']}/path", headers=admin)
    assert path_response.status_code == 200
    path = path_response.json()
    assert len(path) == 3
    assert [(point["lat"], point["lng"]) for point in path] == [
        (point["lat"], point["lng"]) for point in points
    ]
    assert [point["recorded_at"] for point in path] == sorted(
        point["recorded_at"] for point in path
    )
