from datetime import datetime, time, timedelta, timezone

from app import models
from app.notification_service import notify_if_trip_delayed
from .conftest import TestingSessionLocal, register_and_login


def test_trip_notifications_reach_passengers_and_guardians(client):
    admin = register_and_login(client, "notifications-admin@example.com", role="admin")
    driver = register_and_login(client, "notifications-driver@example.com", role="driver")
    passenger = register_and_login(client, "notifications-passenger@example.com", role="passenger")
    guardian = register_and_login(client, "notifications-guardian@example.com", role="guardian")
    passenger_user = client.get("/auth/me", headers=passenger).json()
    driver_user = client.get("/auth/me", headers=driver).json()
    guardian_user = client.get("/auth/me", headers=guardian).json()

    route = client.post(
        "/routes/",
        json={
            "name": "Notification loop",
            "pickup_time": "23:59",
            "stops": [
                {"name": "Gate", "lat": 31.52, "lng": 74.35, "sequence": 0},
                {"name": "Library", "lat": 31.53, "lng": 74.36, "sequence": 1},
            ],
        },
        headers=admin,
    ).json()
    link = client.post(
        f"/users/{passenger_user['id']}/guardians",
        json={"guardian_id": guardian_user["id"], "relationship": "Parent"},
        headers=admin,
    )
    assert link.status_code == 201
    booking = client.post(
        "/bookings/",
        json={
            "route_id": route["id"],
            "boarding_stop_id": route["stops"][0]["id"],
        },
        headers=passenger,
    )
    assert booking.status_code == 201
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_user["id"]},
        headers=admin,
    ).json()

    started = client.post(f"/trips/{trip['id']}/start", headers=driver)
    assert started.status_code == 200
    for headers in (passenger, guardian):
        notifications = client.get("/notifications/", headers=headers)
        assert notifications.status_code == 200
        assert any(item["event_type"] == "trip_started" for item in notifications.json())

    location = client.post(
        f"/trips/{trip['id']}/location",
        json={"lat": 31.5201, "lng": 74.3501},
        headers=driver,
    )
    assert location.status_code == 200
    for headers in (passenger, guardian):
        notifications = client.get("/notifications/", headers=headers).json()
        assert any(item["event_type"] == "vehicle_approaching" for item in notifications)

    ended = client.post(f"/trips/{trip['id']}/end", headers=driver)
    assert ended.status_code == 200
    for headers in (passenger, guardian):
        notifications = client.get("/notifications/", headers=headers).json()
        assert any(item["event_type"] == "trip_ended" for item in notifications)

    passenger_notifications = client.get("/notifications/", headers=passenger).json()
    unread = next(item for item in passenger_notifications if item["event_type"] == "trip_started")
    marked = client.patch(f"/notifications/{unread['id']}/read", headers=passenger)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert client.patch(f"/notifications/{unread['id']}/read", headers=guardian).status_code == 404


def test_delayed_trip_notifies_driver_passenger_and_guardian(client):
    admin = register_and_login(client, "delay-admin@example.com", role="admin")
    driver = register_and_login(client, "delay-driver@example.com", role="driver")
    passenger = register_and_login(client, "delay-passenger@example.com", role="passenger")
    guardian = register_and_login(client, "delay-guardian@example.com", role="guardian")
    driver_user = client.get("/auth/me", headers=driver).json()
    passenger_user = client.get("/auth/me", headers=passenger).json()
    guardian_user = client.get("/auth/me", headers=guardian).json()
    pickup = (datetime.now().astimezone() - timedelta(minutes=12)).strftime("%H:%M")
    route = client.post(
        "/routes/",
        json={"name": "Delayed route", "pickup_time": pickup},
        headers=admin,
    ).json()
    client.post(
        f"/users/{passenger_user['id']}/guardians",
        json={"guardian_id": guardian_user["id"], "relationship": "Parent"},
        headers=admin,
    )
    client.post("/bookings/", json={"route_id": route["id"]}, headers=passenger)
    client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_user["id"]},
        headers=admin,
    )

    for headers in (driver, passenger, guardian):
        notifications = client.get("/notifications/", headers=headers)
        assert notifications.status_code == 200
        assert any(item["event_type"] == "trip_delayed" for item in notifications.json())


def test_on_time_active_trip_is_not_marked_delayed(client):
    admin = register_and_login(client, "ontime-admin@example.com", role="admin")
    driver = register_and_login(client, "ontime-driver@example.com", role="driver")
    driver_user = client.get("/auth/me", headers=driver).json()
    route = client.post(
        "/routes/",
        json={"name": "On-time route", "pickup_time": "09:00"},
        headers=admin,
    ).json()
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_user["id"]},
        headers=admin,
    ).json()
    local_tz = datetime.now().astimezone().tzinfo
    scheduled = datetime.combine(
        datetime.now().astimezone().date(),
        time(9, 0),
    ).replace(tzinfo=local_tz)
    db = TestingSessionLocal()
    try:
        trip_record = db.get(models.Trip, trip["id"])
        trip_record.status = "active"
        trip_record.started_at = scheduled.astimezone(timezone.utc)
        db.commit()
        notify_if_trip_delayed(
            db,
            trip_record,
            current=scheduled + timedelta(minutes=30),
        )
        db.commit()
        assert db.query(models.Notification).filter(
            models.Notification.event_type == "trip_delayed"
        ).count() == 0
    finally:
        db.close()


def test_sos_alert_notifies_trip_passengers_guardians_and_tracks_mine(client):
    admin = register_and_login(client, "sos-notify-admin@example.com", role="admin")
    driver = register_and_login(client, "sos-notify-driver@example.com", role="driver")
    passenger = register_and_login(client, "sos-notify-passenger@example.com", role="passenger")
    guardian = register_and_login(client, "sos-notify-guardian@example.com", role="guardian")
    driver_user = client.get("/auth/me", headers=driver).json()
    passenger_user = client.get("/auth/me", headers=passenger).json()
    guardian_user = client.get("/auth/me", headers=guardian).json()
    route = client.post("/routes/", json={"name": "SOS route"}, headers=admin).json()
    client.post(
        f"/users/{passenger_user['id']}/guardians",
        json={"guardian_id": guardian_user["id"], "relationship": "Parent"},
        headers=admin,
    )
    client.post("/bookings/", json={"route_id": route["id"]}, headers=passenger)
    trip = client.post(
        "/trips/",
        json={"route_id": route["id"], "driver_id": driver_user["id"]},
        headers=admin,
    ).json()
    client.post(f"/trips/{trip['id']}/start", headers=driver)

    alert_response = client.post(
        "/alerts/",
        json={"trip_id": trip["id"], "lat": 31.5, "lng": 74.3},
        headers=passenger,
    )
    assert alert_response.status_code == 201
    alert = alert_response.json()
    assert alert["status"] == "open"

    own_alerts = client.get("/alerts/mine", headers=passenger)
    assert own_alerts.status_code == 200
    assert [item["id"] for item in own_alerts.json()] == [alert["id"]]
    assert client.get("/alerts/mine", headers=driver).json() == []
    for headers in (guardian, driver, admin):
        notifications = client.get("/notifications/", headers=headers)
        assert any(item["event_type"] == "sos" for item in notifications.json())

    assert client.get("/alerts/mine", headers=admin).status_code == 403
    unrelated_passenger = register_and_login(
        client,
        "sos-unrelated@example.com",
        role="passenger",
    )
    assert client.get("/alerts/mine", headers=unrelated_passenger).json() == []
    assert client.get("/notifications/").status_code == 401
    passenger_notification = next(
        item for item in client.get("/notifications/", headers=passenger).json()
        if item["event_type"] == "trip_started"
    )
    assert client.patch(
        f"/notifications/{passenger_notification['id']}/read",
        headers=unrelated_passenger,
    ).status_code == 404
    assert client.post(
        "/alerts/",
        json={"trip_id": trip["id"]},
        headers=register_and_login(client, "sos-outsider@example.com", role="passenger"),
    ).status_code == 403
    resolved = client.patch(f"/alerts/{alert['id']}/resolve", headers=admin)
    assert resolved.status_code == 200
    refreshed_alert = client.get("/alerts/mine", headers=passenger).json()[0]
    assert refreshed_alert["status"] == "resolved"
