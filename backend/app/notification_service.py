from datetime import datetime, time, timezone

from sqlalchemy.orm import Session

from . import models


def notify_users(
    db: Session,
    user_ids: set[int],
    *,
    event_key: str,
    title: str,
    message: str,
    event_type: str,
    trip_id: int | None = None,
    alert_id: int | None = None,
):
    pending_keys = {
        notification.event_key
        for notification in db.new
        if isinstance(notification, models.Notification)
    }
    for user_id in user_ids:
        key = f"{event_key}:user:{user_id}"
        if key in pending_keys:
            continue
        already_created = db.query(models.Notification.id).filter(
            models.Notification.event_key == key
        ).first()
        if already_created:
            continue
        db.add(models.Notification(
            user_id=user_id,
            title=title,
            message=message,
            event_type=event_type,
            trip_id=trip_id,
            alert_id=alert_id,
            event_key=key,
        ))
        pending_keys.add(key)


def notify_passenger_and_guardians(
    db: Session,
    passenger_id: int,
    *,
    event_key: str,
    title: str,
    message: str,
    event_type: str,
    trip_id: int | None = None,
    alert_id: int | None = None,
):
    user_ids = {passenger_id}
    guardian_ids = db.query(models.GuardianLink.guardian_id).filter(
        models.GuardianLink.passenger_id == passenger_id
    ).all()
    user_ids.update(guardian_id for (guardian_id,) in guardian_ids)
    notify_users(
        db,
        user_ids,
        event_key=event_key,
        title=title,
        message=message,
        event_type=event_type,
        trip_id=trip_id,
        alert_id=alert_id,
    )


def notify_trip_audience(
    db: Session,
    trip: models.Trip,
    *,
    event_key: str,
    title: str,
    message: str,
    event_type: str,
    include_driver: bool = False,
    alert_id: int | None = None,
):
    passenger_ids = {
        passenger_id
        for (passenger_id,) in db.query(models.Booking.passenger_id).filter(
            models.Booking.route_id == trip.route_id,
            models.Booking.status == "confirmed",
        ).all()
    }
    audience = set(passenger_ids)
    if passenger_ids:
        guardian_ids = db.query(models.GuardianLink.guardian_id).filter(
            models.GuardianLink.passenger_id.in_(passenger_ids)
        ).all()
        audience.update(guardian_id for (guardian_id,) in guardian_ids)
    if include_driver:
        audience.add(trip.driver_id)
    notify_users(
        db,
        audience,
        event_key=event_key,
        title=title,
        message=message,
        event_type=event_type,
        trip_id=trip.id,
        alert_id=alert_id,
    )


def scheduled_start_at(route: models.Route, current: datetime) -> datetime | None:
    if not route.pickup_time:
        return None
    try:
        scheduled_time = time.fromisoformat(route.pickup_time)
    except ValueError:
        return None
    local_now = current.astimezone()
    if route.days_of_week and (local_now.weekday() not in route.days_of_week):
        return None
    if route.valid_from and local_now.date() < route.valid_from:
        return None
    if route.valid_to and local_now.date() > route.valid_to:
        return None
    return datetime.combine(local_now.date(), scheduled_time).replace(tzinfo=local_now.tzinfo)


def notify_if_trip_delayed(db: Session, trip: models.Trip, current: datetime | None = None):
    current = current or datetime.now(timezone.utc)
    event_time = trip.started_at if trip.status == "active" else current
    if event_time is None:
        return
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    event_time_local = event_time.astimezone()
    scheduled = scheduled_start_at(trip.route, event_time)
    if scheduled is None or event_time_local <= scheduled:
        return
    delay_minutes = (event_time_local - scheduled).total_seconds() / 60
    if delay_minutes <= 10:
        return
    notify_trip_audience(
        db,
        trip,
        event_key=f"trip:{trip.id}:delayed",
        title="Trip delayed",
        message=f"{trip.route.name} is delayed by more than 10 minutes.",
        event_type="trip_delayed",
        include_driver=True,
    )


def notify_overdue_scheduled_trips(db: Session, current: datetime | None = None):
    current = current or datetime.now(timezone.utc)
    scheduled_trips = db.query(models.Trip).filter(
        models.Trip.status == "scheduled"
    ).all()
    for trip in scheduled_trips:
        notify_if_trip_delayed(db, trip, current)
