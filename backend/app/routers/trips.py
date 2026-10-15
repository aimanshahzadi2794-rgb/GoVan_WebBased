from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import require_role, get_current_user
from ..geo import estimate_duration_minutes, haversine_distance_km
from ..notification_service import (
    notify_if_trip_delayed,
    notify_passenger_and_guardians,
    notify_trip_audience,
)

router = APIRouter(prefix="/trips", tags=["trips"])
STOP_RADIUS_KM = 0.05


@router.get("/", response_model=List[schemas.TripOut])
def list_trips(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Admins see every trip. Drivers see only their own. Passengers see
    active trips on routes with their own confirmed bookings."""
    q = db.query(models.Trip)
    if user.role == models.UserRole.driver:
        q = q.filter(models.Trip.driver_id == user.id)
    elif user.role == models.UserRole.passenger:
        booked_route_ids = db.query(models.Booking.route_id).filter(
            models.Booking.passenger_id == user.id,
            models.Booking.status == "confirmed",
        )
        q = q.filter(
            models.Trip.status == "active",
            models.Trip.route_id.in_(booked_route_ids),
        )
    elif user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Role is not permitted to view trips")
    return q.order_by(models.Trip.id.desc()).all()


@router.get(
    "/active-for-me",
    response_model=List[schemas.ActiveTripForPassengerOut],
)
def active_trips_for_passenger(
    passenger_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("passenger", "guardian")),
):
    if user.role == models.UserRole.passenger:
        if passenger_id is not None and passenger_id != user.id:
            raise HTTPException(status_code=403, detail="You can only view your own trips")
        passenger_ids = [user.id]
    else:
        linked_ids = {
            passenger_id_value
            for (passenger_id_value,) in db.query(models.GuardianLink.passenger_id).filter(
                models.GuardianLink.guardian_id == user.id
            ).all()
        }
        if passenger_id is not None:
            if passenger_id not in linked_ids:
                raise HTTPException(status_code=403, detail="Passenger is not linked to this guardian")
            passenger_ids = [passenger_id]
        else:
            passenger_ids = list(linked_ids)

    if not passenger_ids:
        return []

    rows = (
        db.query(models.Trip, models.Booking)
        .join(models.Route, models.Route.id == models.Trip.route_id)
        .join(
            models.Booking,
            models.Booking.route_id == models.Trip.route_id,
        )
        .options(
            joinedload(models.Trip.route).joinedload(models.Route.vehicle),
            joinedload(models.Trip.route).joinedload(models.Route.stops),
            joinedload(models.Trip.driver),
            joinedload(models.Booking.passenger),
            joinedload(models.Booking.boarding_stop),
        )
        .filter(
            models.Trip.status == "active",
            models.Booking.status == "confirmed",
            models.Booking.passenger_id.in_(passenger_ids),
            models.Booking.passenger.has(
                and_(
                    models.User.is_active.is_(True),
                    models.User.role == models.UserRole.passenger,
                )
            ),
        )
        .order_by(models.Trip.id.desc(), models.Booking.id.desc())
        .all()
    )

    trip_ids = {trip.id for trip, _ in rows}
    events_by_trip = {}
    if trip_ids:
        events = db.query(models.TripStopEvent).filter(
            models.TripStopEvent.trip_id.in_(trip_ids)
        ).all()
        for event in events:
            events_by_trip.setdefault(event.trip_id, set()).add(event.stop_id)

    result = []
    seen_trip_passengers = set()
    for trip, booking in rows:
        trip_passenger_key = (trip.id, booking.passenger_id)
        if trip_passenger_key in seen_trip_passengers:
            continue
        seen_trip_passengers.add(trip_passenger_key)

        stops = list(trip.route.stops)
        stop_events = events_by_trip.get(trip.id, set())
        passed_sequence = max(
            (
                stop.sequence
                for stop in stops
                if stop.id in stop_events
            ),
            default=None,
        )
        next_stop = next(
            (
                stop for stop in stops
                if passed_sequence is None or stop.sequence > passed_sequence
            ),
            None,
        )
        boarding_stop = booking.boarding_stop or next_stop
        boarding_stop_reached = (
            booking.boarding_stop_id is not None
            and booking.boarding_stop_id in stop_events
        )
        eta_minutes = None
        if (
            boarding_stop is not None
            and not boarding_stop_reached
            and trip.last_lat is not None
            and trip.last_lng is not None
        ):
            distance_km = haversine_distance_km(
                trip.last_lat,
                trip.last_lng,
                boarding_stop.lat,
                boarding_stop.lng,
            )
            eta_minutes = estimate_duration_minutes(distance_km)

        result.append({
            "id": trip.id,
            "route_id": trip.route_id,
            "route_name": trip.route.name,
            "driver_id": trip.driver_id,
            "driver_name": trip.driver.name,
            "vehicle_plate": trip.route.vehicle.plate_number if trip.route.vehicle else None,
            "passenger_id": booking.passenger_id,
            "passenger_name": booking.passenger.name,
            "status": trip.status,
            "last_lat": trip.last_lat,
            "last_lng": trip.last_lng,
            "last_location_at": trip.last_location_at,
            "boarding_stop_id": boarding_stop.id if boarding_stop else None,
            "boarding_stop_name": boarding_stop.name if boarding_stop else None,
            "next_stop_name": next_stop.name if next_stop else None,
            "eta_minutes": eta_minutes,
            "stops": stops,
        })
    return result


@router.post("/", response_model=schemas.TripOut, status_code=201)
def create_trip(
    payload: schemas.TripCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    route = db.get(models.Route, payload.route_id)
    driver = db.query(models.User).filter(
        models.User.id == payload.driver_id, models.User.role == models.UserRole.driver
    ).first()
    if not route or not driver:
        raise HTTPException(status_code=404, detail="Route or driver not found")
    if route.vehicle and route.vehicle.status != "active":
        raise HTTPException(status_code=400, detail="Route vehicle is not active")
    if route.vehicle and route.vehicle.compliance_status == "blocked":
        raise HTTPException(status_code=400, detail="Route vehicle is blocked by fleet compliance policy")
    trip = models.Trip(route_id=payload.route_id, driver_id=payload.driver_id, status="scheduled")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def _get_own_trip(trip_id: int, driver: models.User, db: Session) -> models.Trip:
    trip = db.get(models.Trip, trip_id)
    if not trip or trip.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("/{trip_id}/start", response_model=schemas.TripOut)
def start_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    driver: models.User = Depends(require_role("driver")),
):
    trip = _get_own_trip(trip_id, driver, db)
    if trip.status != "scheduled":
        raise HTTPException(status_code=400, detail="Only scheduled trips can be started")
    started_at = datetime.now(timezone.utc)
    trip.status = "active"
    trip.started_at = started_at
    notify_trip_audience(
        db,
        trip,
        event_key=f"trip:{trip.id}:started",
        title="Trip started",
        message=f"{trip.route.name} has started.",
        event_type="trip_started",
    )
    notify_if_trip_delayed(db, trip, started_at)
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/location", response_model=schemas.TripOut)
def update_location(
    trip_id: int,
    payload: schemas.LocationUpdate,
    db: Session = Depends(get_db),
    driver: models.User = Depends(require_role("driver")),
):
    """The high-frequency endpoint from the architecture diagram's
    'Tracking' module -- kept as a plain REST call for the MVP; a
    production build would upgrade this path to WebSocket/MQTT."""
    trip = _get_own_trip(trip_id, driver, db)
    if trip.status != "active":
        raise HTTPException(status_code=400, detail="Trip is not active")
    recorded_at = datetime.now(timezone.utc)
    trip.last_lat = payload.lat
    trip.last_lng = payload.lng
    trip.last_accuracy = payload.accuracy
    trip.last_location_at = recorded_at
    db.add(models.TripLocation(
        trip_id=trip.id,
        lat=payload.lat,
        lng=payload.lng,
        recorded_at=recorded_at,
    ))

    notify_if_trip_delayed(db, trip, recorded_at)
    approaching_bookings = db.query(models.Booking).filter(
        models.Booking.route_id == trip.route_id,
        models.Booking.status == "confirmed",
        models.Booking.boarding_stop_id.is_not(None),
    ).all()
    boarding_stop_ids = {booking.boarding_stop_id for booking in approaching_bookings}
    for stop in trip.route.stops:
        if stop.id not in boarding_stop_ids:
            continue
        distance_km = haversine_distance_km(payload.lat, payload.lng, stop.lat, stop.lng)
        if distance_km <= 0.5:
            for booking in approaching_bookings:
                if booking.boarding_stop_id != stop.id:
                    continue
                notify_passenger_and_guardians(
                    db,
                    booking.passenger_id,
                    event_key=f"trip:{trip.id}:approaching:{stop.id}:passenger:{booking.passenger_id}",
                    title="Vehicle approaching your stop",
                    message=f"{trip.route.name} is within 500 m of {stop.name}.",
                    event_type="vehicle_approaching",
                    trip_id=trip.id,
                )

    open_events = db.query(models.TripStopEvent).filter(
        models.TripStopEvent.trip_id == trip.id,
        models.TripStopEvent.departed_at.is_(None),
    ).all()
    open_events_by_stop = {event.stop_id: event for event in open_events}

    for stop in trip.route.stops:
        distance_km = haversine_distance_km(payload.lat, payload.lng, stop.lat, stop.lng)
        event = open_events_by_stop.get(stop.id)
        if distance_km <= STOP_RADIUS_KM and event is None:
            db.add(models.TripStopEvent(
                trip_id=trip.id,
                stop_id=stop.id,
                arrived_at=recorded_at,
            ))
        elif distance_km > STOP_RADIUS_KM and event is not None:
            event.departed_at = recorded_at

    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}/path", response_model=List[schemas.TripLocationOut])
def get_trip_path(
    trip_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    trip = db.get(models.Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return db.query(models.TripLocation).filter(
        models.TripLocation.trip_id == trip.id
    ).order_by(models.TripLocation.recorded_at, models.TripLocation.id).all()


@router.get("/{trip_id}/stops", response_model=List[schemas.TripStopEventOut])
def get_trip_stops(
    trip_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    trip = db.get(models.Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if user.role != models.UserRole.admin:
        if user.role != models.UserRole.driver:
            raise HTTPException(status_code=403, detail="Role is not permitted to view trip stops")
        _get_own_trip(trip_id, user, db)

    events = db.query(models.TripStopEvent).filter(
        models.TripStopEvent.trip_id == trip.id
    ).order_by(models.TripStopEvent.arrived_at, models.TripStopEvent.id).all()
    return [
        {
            "id": event.id,
            "trip_id": event.trip_id,
            "stop_id": event.stop_id,
            "stop_name": event.stop.name if event.stop else None,
            "arrived_at": event.arrived_at,
            "departed_at": event.departed_at,
            "dwell_seconds": event.dwell_seconds,
            "long_stop": event.long_stop,
        }
        for event in events
    ]


@router.post("/{trip_id}/stops/{stop_id}/reached", response_model=schemas.TripStopEventOut, status_code=201)
def mark_trip_stop_reached(
    trip_id: int,
    stop_id: int,
    db: Session = Depends(get_db),
    driver: models.User = Depends(require_role("driver")),
):
    trip = _get_own_trip(trip_id, driver, db)
    if trip.status != "active":
        raise HTTPException(status_code=400, detail="Stops can only be marked on an active trip")
    stop = db.get(models.Stop, stop_id)
    if not stop or stop.route_id != trip.route_id:
        raise HTTPException(status_code=404, detail="Stop not found on this trip route")
    existing = db.query(models.TripStopEvent).filter(
        models.TripStopEvent.trip_id == trip.id,
        models.TripStopEvent.stop_id == stop.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Stop has already been marked as reached")
    event = models.TripStopEvent(
        trip_id=trip.id,
        stop_id=stop.id,
        arrived_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "trip_id": event.trip_id,
        "stop_id": event.stop_id,
        "stop_name": stop.name,
        "arrived_at": event.arrived_at,
        "departed_at": event.departed_at,
        "dwell_seconds": event.dwell_seconds,
        "long_stop": event.long_stop,
    }


@router.post("/{trip_id}/end", response_model=schemas.TripOut)
def end_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    driver: models.User = Depends(require_role("driver")),
):
    trip = _get_own_trip(trip_id, driver, db)
    if trip.status != "active":
        raise HTTPException(status_code=400, detail="Only active trips can be ended")
    trip.status = "completed"
    trip.ended_at = datetime.now(timezone.utc)
    notify_trip_audience(
        db,
        trip,
        event_key=f"trip:{trip.id}:ended",
        title="Trip ended",
        message=f"{trip.route.name} has ended.",
        event_type="trip_ended",
    )
    db.commit()
    db.refresh(trip)
    return trip
