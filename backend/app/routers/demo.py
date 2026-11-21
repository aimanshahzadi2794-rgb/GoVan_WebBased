"""Tenant-scoped Lahore demo controls. Demo records are owned by one named org."""
from datetime import datetime, timedelta, timezone, time as clock_time
import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import hash_password
from ..database import get_db
from ..deps import ensure_organization_access, is_platform_admin, require_organization_manager
from ..routing import route_metrics

router = APIRouter(prefix="/demo", tags=["demo"])
DEMO_ORG = "GoVan Lahore Demo Fleet"
DEMO_MANAGER = "fleet.manager@demo-govan.com"
DEMO_PASSWORD = "GoVanDemo2026!"
DESTINATION = (31.4449894092, 74.3063399426)  # Official QIE map center; campus street address confirmed by Riphah.

# Fixed locality/POI anchors; repeated students assigned to one named stop intentionally share it.
# Coordinates come from the cited map/address sources in DEMO_SETUP.md. These are locality
# anchors, not individual student homes or claimed door entrances. Road geometry is OSRM when configured.
STOPS = [
    ("Bahria Town Gate / Qs Galleria", 31.363371, 74.173385),
    ("Canal Gardens Main Road", 31.390159, 74.175447),
    ("Adda Plot / Raiwind Road", 31.4283, 74.2307),
    ("Jubilee Town Main Entrance", 31.4050, 74.1830),
    ("LDA Avenue locality anchor", 31.417767, 74.216242),
    ("Dream Gardens locality anchor", 31.4020, 74.2380),
    ("Punjab Society, Jamia Masjid area", 31.4438, 74.2873),
    ("PCSIR Main Boulevard", 31.451179, 74.265072),
    ("WAPDA Town locality center", 31.43688, 74.26998),
    ("UCP / Khayaban-e-Jinnah", 31.4469, 74.2682),
    ("Marghzar Colony locality anchor", 31.504032, 74.249688),
]
ROUTE_GROUPS = [(0, 1, 2, 3), (4, 5, 7, 8), (6, 9, 10)]
_simulation = {"state": "stopped", "indices": {}}
_traffic_scenario = "low"


def _demo_org(db):
    return db.query(models.Organization).filter(models.Organization.name == DEMO_ORG).first()


def _guard_demo(user, organization):
    if not organization:
        raise HTTPException(status_code=404, detail="Demo environment has not been initialized")
    ensure_organization_access(user, organization.id)
    if not is_platform_admin(user) and user.organization_id != organization.id:
        raise HTTPException(status_code=404, detail="Demo environment not found")


def _status(db, org):
    users = db.query(models.User).filter(models.User.organization_id == org.id).all()
    routes = db.query(models.Route).filter(models.Route.organization_id == org.id).all()
    route_ids = [r.id for r in routes]
    trips = db.query(models.Trip).filter(models.Trip.route_id.in_(route_ids)).all() if route_ids else []
    trip_ids = [trip.id for trip in trips]
    return {
        "enabled": True, "organization_id": org.id, "organization": org.name,
        "students": sum(u.role == models.UserRole.passenger for u in users),
        "guardians": sum(u.role == models.UserRole.guardian for u in users),
        "drivers": sum(u.role == models.UserRole.driver for u in users),
        "vehicles": db.query(models.Vehicle).filter(models.Vehicle.organization_id == org.id).count(),
        "routes": len(routes), "trips": len(trips),
        "trip_statuses": {name: sum(trip.status == name for trip in trips)
                           for name in ("scheduled", "active", "completed")},
        "notifications": db.query(models.Notification).filter(models.Notification.trip_id.in_(trip_ids)).count() if trip_ids else 0,
        "open_alerts": db.query(models.EmergencyAlert).filter(
            models.EmergencyAlert.trip_id.in_(trip_ids), models.EmergencyAlert.status == "open"
        ).count() if trip_ids else 0,
        "simulation": _simulation["state"],
    }


@router.get("/status")
def status(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db)
    if not org:
        return {"enabled": False, "simulation": "stopped"}
    _guard_demo(user, org)
    return _status(db, org)


@router.post("/initialize")
def initialize(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    global _traffic_scenario
    org = _demo_org(db)
    if org:
        _guard_demo(user, org)
        return {**_status(db, org), "message": "Demo dataset already initialized."}
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="A platform administrator must initialize the demo fleet first")
    org = models.Organization(name=DEMO_ORG, type=models.OrganizationType.university,
                              contact_email=DEMO_MANAGER)
    db.add(org)
    db.flush()
    _populate_demo(db, org)
    db.commit()
    _simulation["state"] = "stopped"; _simulation["indices"] = {}
    _traffic_scenario = "low"
    return {**_status(db, org), "message": "Lahore demo dataset initialized."}


def _populate_demo(db, org):
    manager = db.query(models.User).filter(models.User.email == DEMO_MANAGER).first()
    if manager and manager.organization_id != org.id:
        raise HTTPException(status_code=409, detail="Demo Fleet Manager email is already assigned to another organization")
    if not manager:
        manager = models.User(name="GoVan Demo Fleet Manager", email=DEMO_MANAGER,
                              hashed_password=hash_password(DEMO_PASSWORD), role=models.UserRole.fleet_manager,
                              organization_id=org.id)
        db.add(manager)
        db.flush()
    vehicles, drivers = [], []
    for i, capacity in enumerate((10, 10, 12), 1):
        vehicle = models.Vehicle(plate_number=f"DEMO-LHR-{i:02d}", model=("Toyota Hiace", "Suzuki APV", "Coaster")[i-1],
                                 vehicle_type="van" if i < 3 else "bus", fuel_type="diesel", capacity=capacity,
                                 status="active", organization_id=org.id)
        db.add(vehicle); db.flush(); vehicles.append(vehicle)
        driver = models.User(name=f"Demo Driver {i}", email=f"driver{i}@demo-govan.com",
                             hashed_password=hash_password(DEMO_PASSWORD), role=models.UserRole.driver,
                             organization_id=org.id, vehicle_id=vehicle.id, license_number=f"DEMO-LIC-{i:03d}")
        db.add(driver); db.flush(); drivers.append(driver)
    students = []
    for i in range(1, 31):
        student = models.User(name=f"User{i}", email=f"user{i}@demo-govan.com",
                              hashed_password=hash_password(DEMO_PASSWORD), role=models.UserRole.passenger,
                              organization_id=org.id)
        db.add(student); db.flush(); students.append(student)
    guardians = []
    for i in range(1, 11):
        guardian = models.User(name=f"Demo Guardian {i}", email=f"guardian{i}@demo-govan.com",
                               hashed_password=hash_password(DEMO_PASSWORD), role=models.UserRole.guardian,
                               organization_id=org.id)
        db.add(guardian); db.flush(); guardians.append(guardian)
        for student in students[(i-1)*3:i*3]:
            db.add(models.GuardianLink(guardian_id=guardian.id, passenger_id=student.id,
                                       relationship_label="parent/guardian"))
    all_stops = {}
    for route_index, stop_indices in enumerate(ROUTE_GROUPS):
        route = models.Route(name=f"QIE Demo Route {route_index+1}", organization_id=org.id,
                             vehicle_id=vehicles[route_index].id, pickup_time="07:00",
                             drop_time="08:30", days_of_week=[0, 1, 2, 3, 4])
        db.add(route); db.flush()
        route_stops = []
        for seq, stop_index in enumerate(stop_indices):
            name, lat, lng = STOPS[stop_index]
            stop = models.Stop(route_id=route.id, name=name, lat=lat, lng=lng, sequence=seq)
            db.add(stop); db.flush(); route_stops.append(stop); all_stops[stop_index] = stop
        dest = models.Stop(route_id=route.id, name="Riphah International University — QIE Campus",
                           lat=DESTINATION[0], lng=DESTINATION[1], sequence=len(route_stops))
        db.add(dest); db.flush(); route_stops.append(dest)
        # Ten students per route; two students share each locality stop.
        for local_index, student_index in enumerate(range(route_index*10, (route_index+1)*10)):
            stop_index = min(len(route_stops) - 2, (local_index * (len(route_stops) - 1)) // 10)
            stop = route_stops[stop_index]
            db.add(models.Booking(passenger_id=students[student_index].id, route_id=route.id,
                                  boarding_stop_id=stop.id, dropoff_stop_id=dest.id, status="confirmed"))
        trip_status = ("active", "scheduled", "completed")[route_index]
        trip = models.Trip(route_id=route.id, driver_id=drivers[route_index].id, status=trip_status)
        db.add(trip); db.flush()
        if trip_status == "active":
            trip.started_at = datetime.now(timezone.utc)
            trip.last_lat, trip.last_lng = route_stops[0].lat, route_stops[0].lng
            trip.last_location_at = datetime.now(timezone.utc)
            db.add(models.TripLocation(trip_id=trip.id, lat=trip.last_lat, lng=trip.last_lng))
            db.add(models.Notification(
                user_id=manager.id, title="Demo traffic advisory",
                message="A simulated moderate-traffic scenario is available in Demo Control Center.",
                event_type="demo_traffic", trip_id=trip.id, event_key="demo:traffic-advisory",
            ))
        elif trip_status == "completed":
            trip.started_at = datetime.now(timezone.utc)-timedelta(hours=2)
            trip.ended_at = datetime.now(timezone.utc)-timedelta(hours=1)
            trip.last_lat, trip.last_lng = DESTINATION
    db.flush()


@router.post("/reset")
def reset(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    global _traffic_scenario
    org = _demo_org(db); _guard_demo(user, org)
    routes = db.query(models.Route.id).filter(models.Route.organization_id == org.id).all()
    route_ids = [r[0] for r in routes]
    trips = db.query(models.Trip.id).filter(models.Trip.route_id.in_(route_ids)).all() if route_ids else []
    trip_ids = [t[0] for t in trips]
    demo_user_ids = [u[0] for u in db.query(models.User.id).filter(models.User.organization_id == org.id).all()]
    vehicle_ids = [v[0] for v in db.query(models.Vehicle.id).filter(models.Vehicle.organization_id == org.id).all()]
    if demo_user_ids:
        db.query(models.EmergencyAlert).filter(models.EmergencyAlert.raised_by_id.in_(demo_user_ids)).delete(synchronize_session=False)
        db.query(models.Notification).filter(models.Notification.user_id.in_(demo_user_ids)).delete(synchronize_session=False)
    if vehicle_ids:
        db.query(models.MaintenanceRecord).filter(models.MaintenanceRecord.vehicle_id.in_(vehicle_ids)).delete(synchronize_session=False)
    db.query(models.Notification).filter(models.Notification.trip_id.in_(trip_ids)).delete(synchronize_session=False)
    db.query(models.TripStopEvent).filter(models.TripStopEvent.trip_id.in_(trip_ids)).delete(synchronize_session=False)
    db.query(models.TripLocation).filter(models.TripLocation.trip_id.in_(trip_ids)).delete(synchronize_session=False)
    db.query(models.Trip).filter(models.Trip.id.in_(trip_ids)).delete(synchronize_session=False)
    db.query(models.Booking).filter(models.Booking.route_id.in_(route_ids)).delete(synchronize_session=False)
    db.query(models.Stop).filter(models.Stop.route_id.in_(route_ids)).delete(synchronize_session=False)
    db.query(models.Route).filter(models.Route.id.in_(route_ids)).delete(synchronize_session=False)
    db.query(models.GuardianLink).filter(models.GuardianLink.passenger_id.in_(
        db.query(models.User.id).filter(models.User.organization_id == org.id)
    )).delete(synchronize_session=False)
    db.query(models.User).filter(
        models.User.organization_id == org.id,
        models.User.role != models.UserRole.fleet_manager,
    ).delete(synchronize_session=False)
    db.query(models.Vehicle).filter(models.Vehicle.organization_id == org.id).delete(synchronize_session=False)
    db.flush()
    _populate_demo(db, org)
    db.commit()
    _simulation["state"] = "stopped"; _simulation["indices"] = {}
    _traffic_scenario = "low"
    return {**_status(db, org), "message": "Demo scenario restored from its original seed. Other organizations were not changed."}


def _routes_and_bookings(db, org):
    routes = db.query(models.Route).filter(models.Route.organization_id == org.id).all()
    data = []
    for route in routes:
        stops = sorted(route.stops, key=lambda s: s.sequence)
        bookings = db.query(models.Booking).filter(models.Booking.route_id == route.id,
                                                   models.Booking.status == "confirmed").all()
        distance, duration, geometry, source, _, _ = route_metrics(stops)
        data.append({"route": route, "stops": stops, "bookings": bookings, "distance": distance,
                     "duration": duration, "geometry": geometry, "source": source})
    return data


@router.post("/cluster")
def cluster(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    points = [(s, b) for data in _routes_and_bookings(db, org) for b in data["bookings"]
              for s in [b.boarding_stop] if s]
    # Deterministic K-means (k=3) on pickup coordinates, with actual assignment output.
    k = min(3, len(points)); centers = [points[round(i*(len(points)-1)/max(1, k-1))][0] for i in range(k)]
    labels = []
    for _ in range(20):
        labels = [min(range(k), key=lambda j: (p.lat-centers[j].lat)**2+(p.lng-centers[j].lng)**2) for p, _ in points]
        for j in range(k):
            members = [points[i][0] for i, label in enumerate(labels) if label == j]
            if members:
                centers[j] = type("Point", (), {"lat": sum(p.lat for p in members)/len(members),
                                                  "lng": sum(p.lng for p in members)/len(members)})()
    groups = [{"cluster": j+1, "passengers": [b.passenger.name for (_, b), label in zip(points, labels) if label == j],
               "center": [centers[j].lat, centers[j].lng]} for j in range(k)]
    return {"algorithm": "K-means", "passengers_clustered": len(points), "groups": groups}


@router.post("/compare")
def compare(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    data = _routes_and_bookings(db, org)
    original_distance = sum(d["distance"] for d in data)
    original_duration = sum(d["duration"] for d in data)
    optimized_distance = optimized_duration = 0
    assignments = []
    violations = []
    for d in data:
        vehicle = d["route"].vehicle
        count = len(d["bookings"])
        if vehicle and count > vehicle.capacity:
            violations.append(f"{d['route'].name} exceeds vehicle capacity")
        # Actual route stops are ordered by nearest-neighbor distance from start; destination fixed last.
        if len(d["stops"]) > 2:
            pending = d["stops"][1:-1]
            ordered = [d["stops"][0]]
            while pending:
                prev = ordered[-1]
                nxt = min(pending, key=lambda s: (s.lat-prev.lat)**2+(s.lng-prev.lng)**2)
                ordered.append(nxt); pending.remove(nxt)
            ordered.append(d["stops"][-1])
        else:
            ordered = d["stops"]
        distance, duration, _, source, _, _ = route_metrics(ordered)
        optimized_distance += distance; optimized_duration += duration
        assignments.append({"route": d["route"].name, "students": count,
                            "capacity": vehicle.capacity if vehicle else 0,
                            "utilization_pct": round(100*count/vehicle.capacity, 1) if vehicle and vehicle.capacity else 0,
                            "optimized_stop_order": [s.name for s in ordered], "routing_source": source})
    return {"original": {"distance_km": original_distance, "duration_min": original_duration,
                          "vehicles": len(data), "students": sum(len(d["bookings"]) for d in data)},
            "optimized": {"distance_km": optimized_distance, "duration_min": optimized_duration,
                          "vehicles": len(data), "students": sum(len(d["bookings"]) for d in data)},
            "distance_saved_km": round(original_distance-optimized_distance, 2),
            "time_saved_min": original_duration-optimized_duration,
            "constraints_violations": violations, "assignments": assignments}


@router.get("/map")
def demo_map(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    routes = []
    for data in _routes_and_bookings(db, org):
        routes.append({"id": data["route"].id, "name": data["route"].name,
                       "geometry": data["geometry"], "routing_source": data["source"],
                       "markers": [{"lat": s.lat, "lng": s.lng, "label": s.name} for s in data["stops"]]})
    return {"routes": routes}


@router.get("/eta")
def eta(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    estimates = []
    multiplier = {"low": 1.0, "moderate": 1.2, "heavy": 1.5}[_traffic_scenario]
    for trip in db.query(models.Trip).join(models.Route).filter(models.Route.organization_id == org.id,
                                                                 models.Trip.status == "active").all():
        stops = sorted(trip.route.stops, key=lambda stop: stop.sequence)
        if trip.last_lat is None or trip.last_lng is None or not stops:
            continue
        current = type("Point", (), {"lat": trip.last_lat, "lng": trip.last_lng})()
        next_index = min(range(len(stops)), key=lambda i: (stops[i].lat-trip.last_lat)**2+(stops[i].lng-trip.last_lng)**2)
        remaining = [current, *stops[next_index:]]
        distance, minutes, _, source, _, _ = route_metrics(remaining)
        estimates.append({"trip_id": trip.id, "route": trip.route.name, "eta_minutes": round(minutes*multiplier),
                          "distance_km": distance, "routing_source": source, "traffic_scenario": _traffic_scenario})
    return {"estimates": estimates, "traffic_scenario": _traffic_scenario}


@router.post("/schedule")
def schedule(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    data = _routes_and_bookings(db, org)
    resource_intervals = {}
    results = []
    for d in sorted(data, key=lambda item: item["route"].pickup_time or ""):
        route = d["route"]
        driver = route.vehicle.driver_user if route.vehicle else None
        try:
            start = clock_time.fromisoformat(route.pickup_time or "07:00")
        except ValueError:
            start = clock_time(7, 0)
        start_minute = start.hour*60 + start.minute
        duration = max(1, d["duration"])
        end_minute = start_minute + duration
        weekdays = tuple(route.days_of_week or [0, 1, 2, 3, 4])
        resources = [resource for resource in (("driver", driver.id) if driver else None,
                                               ("vehicle", route.vehicle_id) if route.vehicle_id else None)
                     if resource is not None]
        conflict = False
        for resource in resources:
            for prior_start, prior_end, prior_days in resource_intervals.get(resource, []):
                if start_minute < prior_end and prior_start < end_minute and set(weekdays).intersection(prior_days):
                    conflict = True
            resource_intervals.setdefault(resource, []).append((start_minute, end_minute, weekdays))
        results.append({"route": route.name, "pickup_time": route.pickup_time,
                        "estimated_duration_min": duration,
                        "driver": driver.name if driver else None,
                        "vehicle": route.vehicle.plate_number if route.vehicle else None,
                        "capacity_ok": not route.vehicle or len(d["bookings"]) <= route.vehicle.capacity,
                        "conflict": conflict})
    return {"scheduled_routes": results}


@router.post("/traffic/{scenario}")
def traffic(scenario: str, db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    global _traffic_scenario
    _guard_demo(user, _demo_org(db))
    if scenario not in {"low", "moderate", "heavy"}:
        raise HTTPException(status_code=400, detail="Scenario must be low, moderate, or heavy")
    _traffic_scenario = scenario
    return {"scenario": scenario, "message": f"Demo traffic set to {scenario}; GoVan ETA estimates apply the demo multiplier."}


@router.post("/simulation/control/{action}")
def simulation(action: str, db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    if action not in {"start", "pause", "resume", "stop"}:
        raise HTTPException(status_code=400, detail="Unknown simulation action")
    if action == "start":
        _simulation["indices"] = {}
        for trip in db.query(models.Trip).join(models.Route).filter(models.Route.organization_id == org.id,
                                                                      models.Trip.status == "active").all():
            _simulation["indices"][trip.id] = 0
    if action == "resume" and not _simulation["indices"]:
        raise HTTPException(status_code=409, detail="Start the simulation before resuming")
    _simulation["state"] = "running" if action in {"start", "resume"} else "stopped" if action == "stop" else "paused"
    return {"state": _simulation["state"], "message": f"GPS simulation {action}ed."}


@router.post("/simulation/tick")
def simulation_tick(db: Session = Depends(get_db), user: models.User = Depends(require_organization_manager())):
    org = _demo_org(db); _guard_demo(user, org)
    if _simulation["state"] != "running":
        return {"state": _simulation["state"], "updated": 0}
    updated = []
    for trip_id, index in list(_simulation["indices"].items()):
        trip = db.get(models.Trip, trip_id)
        if not trip or trip.status != "active":
            continue
        route = trip.route; stops = sorted(route.stops, key=lambda s: s.sequence)
        _, _, geometry, source, _, _ = route_metrics(stops)
        if len(geometry) < 2:
            continue
        index = index + max(1, len(geometry)//30)
        if index >= len(geometry):
            index = len(geometry) - 1
            trip.status = "completed"
            trip.ended_at = datetime.now(timezone.utc)
            _simulation["indices"].pop(trip_id, None)
        _simulation["indices"][trip_id] = index
        lat, lng = geometry[index]
        now = datetime.now(timezone.utc)
        trip.last_lat, trip.last_lng, trip.last_location_at = lat, lng, now
        db.add(models.TripLocation(trip_id=trip.id, lat=lat, lng=lng, recorded_at=now))
        for stop in stops:
            distance_km = math.hypot((lat-stop.lat)*111, (lng-stop.lng)*92)
            event = db.query(models.TripStopEvent).filter(
                models.TripStopEvent.trip_id == trip.id, models.TripStopEvent.stop_id == stop.id,
                models.TripStopEvent.departed_at.is_(None),
            ).first()
            if distance_km <= 0.08 and event is None:
                db.add(models.TripStopEvent(trip_id=trip.id, stop_id=stop.id, arrived_at=now))
            elif distance_km > 0.08 and event is not None:
                event.departed_at = now
        updated.append({"trip_id": trip.id, "lat": lat, "lng": lng, "routing_source": source})
    db.commit()
    return {"state": "running", "updated": len(updated), "vehicles": updated}

