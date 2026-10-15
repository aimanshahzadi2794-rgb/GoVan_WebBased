"""
Seed the database with realistic demo data so you don't have to manually
register 3 accounts and click through the whole setup every time you want
to demo or test the app.

Usage (from the backend/ folder, with dependencies installed):
    python seed.py

Safe to re-run: it skips creating anything that already exists (matched by
email for users, plate number for vehicles), so running it twice never
creates duplicates.
"""
from datetime import date, timedelta

from app.database import SessionLocal, Base, engine, ensure_sqlite_schema
from app import models
from app.auth import hash_password

Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

db = SessionLocal()

DEMO_PASSWORD = "Passw0rd!"


def get_or_create_user(name, email, role):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        return user, False
    user = models.User(name=name, email=email, hashed_password=hash_password(DEMO_PASSWORD), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True


def get_or_create_vehicle(
    plate_number,
    model,
    capacity,
    vehicle_type="van",
    fuel_type="petrol",
    ownership_type="internal",
    odometer_km=0,
    insurance_expiry=None,
    fitness_expiry=None,
    permit_expiry=None,
    next_service_due=None,
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == plate_number).first()
    if vehicle:
        vehicle.vehicle_type = vehicle_type
        vehicle.fuel_type = fuel_type
        vehicle.ownership_type = ownership_type
        vehicle.odometer_km = odometer_km
        vehicle.insurance_expiry = insurance_expiry
        vehicle.fitness_expiry = fitness_expiry
        vehicle.permit_expiry = permit_expiry
        vehicle.next_service_due = next_service_due
        db.commit()
        db.refresh(vehicle)
        return vehicle, False
    vehicle = models.Vehicle(
        plate_number=plate_number,
        model=model,
        capacity=capacity,
        vehicle_type=vehicle_type,
        fuel_type=fuel_type,
        ownership_type=ownership_type,
        odometer_km=odometer_km,
        insurance_expiry=insurance_expiry,
        fitness_expiry=fitness_expiry,
        permit_expiry=permit_expiry,
        next_service_due=next_service_due,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle, True


def get_or_create_route(name, stops, pickup_time, drop_time, vehicle_id):
    """stops: list of (name, lat, lng) tuples, in order."""
    route = db.query(models.Route).filter(models.Route.name == name).first()
    if route:
        return route, False
    route = models.Route(name=name, pickup_time=pickup_time, drop_time=drop_time, vehicle_id=vehicle_id)
    db.add(route)
    db.commit()
    db.refresh(route)

    for i, (stop_name, lat, lng) in enumerate(stops):
        db.add(models.Stop(route_id=route.id, name=stop_name, lat=lat, lng=lng, sequence=i))
    db.commit()
    db.refresh(route)
    return route, True


def get_or_create_maintenance(vehicle_id, title, category, due_at, odometer_km=None, cost=None, notes=""):
    record = db.query(models.MaintenanceRecord).filter(
        models.MaintenanceRecord.vehicle_id == vehicle_id,
        models.MaintenanceRecord.title == title,
    ).first()
    if record:
        return record, False
    record = models.MaintenanceRecord(
        vehicle_id=vehicle_id,
        title=title,
        category=category,
        due_at=due_at,
        odometer_km=odometer_km,
        cost=cost,
        notes=notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, True


def main():
    created = []

    admin, is_new = get_or_create_user("Admin User", "admin@govan.dev", models.UserRole.admin)
    created.append(("admin", admin.email, is_new))

    driver1, is_new = get_or_create_user("Dave Driver", "dave@govan.dev", models.UserRole.driver)
    created.append(("driver", driver1.email, is_new))

    driver2, is_new = get_or_create_user("Sana Driver", "sana@govan.dev", models.UserRole.driver)
    created.append(("driver", driver2.email, is_new))

    pax1, is_new = get_or_create_user("Pat Passenger", "pat@govan.dev", models.UserRole.passenger)
    created.append(("passenger", pax1.email, is_new))

    pax2, is_new = get_or_create_user("Ali Passenger", "ali@govan.dev", models.UserRole.passenger)
    created.append(("passenger", pax2.email, is_new))

    today = date.today()

    v1, is_new = get_or_create_vehicle(
        "LEB-101",
        "Toyota Hiace",
        14,
        vehicle_type="van",
        fuel_type="petrol",
        ownership_type="internal",
        odometer_km=84250,
        insurance_expiry=today + timedelta(days=92),
        fitness_expiry=today + timedelta(days=44),
        permit_expiry=today + timedelta(days=120),
        next_service_due=today + timedelta(days=9),
    )
    created.append(("vehicle", v1.plate_number, is_new))

    v2, is_new = get_or_create_vehicle(
        "LEB-202",
        "Coaster Mini Bus",
        20,
        vehicle_type="bus",
        fuel_type="diesel",
        ownership_type="external",
        odometer_km=126700,
        insurance_expiry=today + timedelta(days=21),
        fitness_expiry=today + timedelta(days=76),
        permit_expiry=today + timedelta(days=35),
        next_service_due=today + timedelta(days=28),
    )
    created.append(("vehicle", v2.plate_number, is_new))

    # Assign drivers to vehicles.
    if driver1.vehicle_id is None:
        driver1.vehicle_id = v1.id
        db.commit()
    if driver2.vehicle_id is None:
        driver2.vehicle_id = v2.id
        db.commit()

    r1, is_new = get_or_create_route(
      "Campus Loop",
      [
        ("Main Gate", 31.4805, 74.3030),
        ("Library", 31.4818, 74.3045),
        ("Hostel Block A", 31.4830, 74.3060),
        ("Hostel Block B", 31.4842, 74.3072),
      ],
      "8:00 AM", "4:30 PM", v1.id,
    )
    created.append(("route", r1.name, is_new))

    r2, is_new = get_or_create_route(
      "City Express",
      [
        ("DHA Phase 5", 31.4736, 74.4142),
        ("Model Town", 31.4820, 74.3235),
        ("Johar Town", 31.4697, 74.2728),
        ("University Road", 31.4805, 74.2871),
     ],
     "7:30 AM", "5:00 PM", v2.id,
    )
    created.append(("route", r2.name, is_new))

    # Give the passengers a booking each, if they don't already have one.
    existing_booking_1 = db.query(models.Booking).filter(
        models.Booking.passenger_id == pax1.id, models.Booking.route_id == r1.id
    ).first()
    if not existing_booking_1:
        db.add(models.Booking(passenger_id=pax1.id, route_id=r1.id))
        created.append(("booking", f"{pax1.email} -> {r1.name}", True))

    existing_booking_2 = db.query(models.Booking).filter(
        models.Booking.passenger_id == pax2.id, models.Booking.route_id == r2.id
    ).first()
    if not existing_booking_2:
        db.add(models.Booking(passenger_id=pax2.id, route_id=r2.id))
        created.append(("booking", f"{pax2.email} -> {r2.name}", True))

    db.commit()

    m1, is_new = get_or_create_maintenance(
        v1.id,
        "Oil and brake inspection",
        "service",
        today + timedelta(days=9),
        odometer_km=84500,
        cost=8500,
        notes="Scheduled before the next weekly route cycle.",
    )
    created.append(("maintenance", m1.title, is_new))

    m2, is_new = get_or_create_maintenance(
        v2.id,
        "Insurance renewal follow-up",
        "inspection",
        today + timedelta(days=21),
        odometer_km=126700,
        notes="External fleet partner must submit renewed document.",
    )
    created.append(("maintenance", m2.title, is_new))

    print("\nSeed complete. Demo accounts (all use password: {}):\n".format(DEMO_PASSWORD))
    print(f"  Admin:     admin@govan.dev")
    print(f"  Driver 1:  dave@govan.dev   (assigned to {v1.plate_number}, route: {r1.name})")
    print(f"  Driver 2:  sana@govan.dev   (assigned to {v2.plate_number}, route: {r2.name})")
    print(f"  Passenger 1: pat@govan.dev  (booked on {r1.name})")
    print(f"  Passenger 2: ali@govan.dev  (booked on {r2.name})")
    print("\nLog in as any of these at http://localhost:5173 and everything is already wired up.")
    print("\nDetail:")
    for kind, label, is_new in created:
        status = "created" if is_new else "already existed, skipped"
        print(f"  [{kind}] {label} -- {status}")


if __name__ == "__main__":
    main()
    db.close()
