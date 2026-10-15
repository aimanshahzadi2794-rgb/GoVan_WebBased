from datetime import datetime

from .conftest import TestingSessionLocal, models, register_and_login


def test_admin_report_summary_calculates_filtered_metrics(client):
    admin_headers = register_and_login(client, "reports-admin@example.com", role="admin")
    db = TestingSessionLocal()
    try:
        driver_one = models.User(
            name="Report Driver One",
            email="report-driver-one@example.com",
            hashed_password="not-used",
            role=models.UserRole.driver,
        )
        driver_two = models.User(
            name="Report Driver Two",
            email="report-driver-two@example.com",
            hashed_password="not-used",
            role=models.UserRole.driver,
        )
        vehicle_one = models.Vehicle(plate_number="REP-101", model="Van")
        vehicle_two = models.Vehicle(plate_number="REP-202", model="Bus")
        db.add_all([driver_one, driver_two, vehicle_one, vehicle_two])
        db.flush()
        route_one = models.Route(
            name="Morning Route",
            pickup_time="08:00",
            vehicle_id=vehicle_one.id,
        )
        route_two = models.Route(
            name="Campus Route",
            pickup_time="09:00",
            vehicle_id=vehicle_two.id,
        )
        db.add_all([route_one, route_two])
        db.flush()

        report_day = datetime(2025, 6, 1)
        trip_one = models.Trip(
            route_id=route_one.id,
            driver_id=driver_one.id,
            status="completed",
            created_at=report_day,
            started_at=datetime(2025, 6, 1, 8, 10),
            ended_at=datetime(2025, 6, 1, 9, 10),
        )
        trip_two = models.Trip(
            route_id=route_two.id,
            driver_id=driver_two.id,
            status="completed",
            created_at=report_day,
            started_at=datetime(2025, 6, 1, 9, 4),
            ended_at=datetime(2025, 6, 1, 9, 8),
        )
        trip_cancelled = models.Trip(
            route_id=route_one.id,
            driver_id=driver_one.id,
            status="cancelled",
            created_at=datetime(2025, 6, 1, 12),
        )
        db.add_all([trip_one, trip_two, trip_cancelled])
        db.flush()
        db.add_all([
            models.Booking(
                passenger_id=driver_one.id,
                route_id=route_one.id,
                status="confirmed",
                created_at=datetime(2025, 6, 1, 7),
            ),
            models.Booking(
                passenger_id=driver_two.id,
                route_id=route_one.id,
                status="cancelled",
                created_at=datetime(2025, 6, 1, 7),
            ),
            models.Booking(
                passenger_id=driver_one.id,
                route_id=route_two.id,
                status="confirmed",
                created_at=datetime(2025, 6, 1, 8),
            ),
        ])
        db.add_all([
            models.EmergencyAlert(
                raised_by_id=driver_one.id,
                trip_id=trip_one.id,
                created_at=datetime(2025, 6, 1, 8, 30),
            ),
            models.EmergencyAlert(
                raised_by_id=driver_two.id,
                trip_id=trip_two.id,
                created_at=datetime(2025, 6, 1, 9, 5),
            ),
        ])
        db.commit()
        route_one_id = route_one.id
        vehicle_one_id = vehicle_one.id
        driver_one_id = driver_one.id
    finally:
        db.close()

    response = client.get(
        "/reports/summary?from=2025-06-01&to=2025-06-01",
        headers=admin_headers,
    )
    assert response.status_code == 200
    report = response.json()
    assert report["trips_per_day"] == [{"date": "2025-06-01", "trips": 3}]
    assert report["completed_vs_cancelled"] == {"completed": 2, "cancelled": 1}
    assert report["on_time_vs_delayed"] == {"on_time": 1, "delayed": 1}
    assert report["average_duration_minutes"] == 32
    assert report["average_delay_minutes"] == 7
    assert report["passengers_booked_per_route"] == [
        {"route_id": route_one_id + 1, "route_name": "Campus Route", "passengers_booked": 1},
        {"route_id": route_one_id, "route_name": "Morning Route", "passengers_booked": 1},
    ]
    assert report["sos_count"] == 2
    assert len(report["trip_history"]) == 3
    assert report["trip_history"][0]["passengers_booked"] == 1

    filtered = client.get(
        f"/reports/summary?from=2025-06-01&to=2025-06-01&route_id={route_one_id}"
        f"&vehicle_id={vehicle_one_id}&driver_id={driver_one_id}",
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    filtered_report = filtered.json()
    assert len(filtered_report["trip_history"]) == 2
    assert filtered_report["sos_count"] == 1
    assert len(filtered_report["passengers_booked_per_route"]) == 1
    assert filtered_report["passengers_booked_per_route"][0]["passengers_booked"] == 1


def test_reports_require_admin_and_reject_invalid_date_range(client):
    passenger_headers = register_and_login(client, "reports-passenger@example.com")
    forbidden = client.get("/reports/summary", headers=passenger_headers)
    assert forbidden.status_code == 403

    admin_headers = register_and_login(client, "reports-date-admin@example.com", role="admin")
    invalid = client.get(
        "/reports/summary?from=2025-06-02&to=2025-06-01",
        headers=admin_headers,
    )
    assert invalid.status_code == 400
