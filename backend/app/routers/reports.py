from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import require_role

router = APIRouter(prefix="/reports", tags=["reports"])
DELAY_THRESHOLD_MINUTES = 5


def _as_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


def _trip_delay_minutes(trip: models.Trip) -> Optional[float]:
    if not trip.started_at or not trip.route.pickup_time:
        return None
    try:
        scheduled_time = time.fromisoformat(trip.route.pickup_time)
    except ValueError:
        return None

    started_at = _as_naive(trip.started_at)
    scheduled_at = datetime.combine(started_at.date(), scheduled_time)
    return round(max(0.0, (started_at - scheduled_at).total_seconds() / 60), 2)


@router.get("/summary", response_model=schemas.ReportSummaryOut)
def report_summary(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    route_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    unassigned_organization: bool = False,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    """Summarize trips, bookings, and SOS alerts for the selected date range.

    Trips are assigned to their start date, falling back to end/creation date.
    A trip is delayed when its start is more than five minutes after the route's
    scheduled pickup time; early starts count as zero minutes of delay.
    """
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from must be on or before to")

    report_date = func.coalesce(
        models.Trip.started_at,
        models.Trip.ended_at,
        models.Trip.created_at,
    )
    trip_query = db.query(models.Trip).join(models.Route).options(
        joinedload(models.Trip.route).joinedload(models.Route.vehicle),
        joinedload(models.Trip.driver),
    )
    if from_date:
        trip_query = trip_query.filter(
            report_date >= datetime.combine(from_date, time.min)
        )
    if to_date:
        trip_query = trip_query.filter(
            report_date < datetime.combine(to_date + timedelta(days=1), time.min)
        )
    if route_id is not None:
        trip_query = trip_query.filter(models.Trip.route_id == route_id)
    if vehicle_id is not None:
        trip_query = trip_query.filter(models.Route.vehicle_id == vehicle_id)
    if driver_id is not None:
        trip_query = trip_query.filter(models.Trip.driver_id == driver_id)
    if organization_id is not None and unassigned_organization:
        raise HTTPException(
            status_code=400,
            detail="organization_id and unassigned_organization cannot both be set",
        )
    if organization_id is not None:
        trip_query = trip_query.filter(models.Route.organization_id == organization_id)
    elif unassigned_organization:
        trip_query = trip_query.filter(models.Route.organization_id.is_(None))

    filtered_trips = trip_query.order_by(models.Trip.id).all()

    trip_counts_by_day = {}
    for trip in filtered_trips:
        event_at = trip.started_at or trip.ended_at or trip.created_at
        day = _as_naive(event_at).date()
        trip_counts_by_day[day] = trip_counts_by_day.get(day, 0) + 1

    statuses = {"completed": 0, "cancelled": 0}
    for trip in filtered_trips:
        if trip.status in statuses:
            statuses[trip.status] += 1

    durations = []
    delays = []
    delayed_count = 0
    trip_history = []
    history_by_trip_id = {}
    for trip in filtered_trips:
        duration = None
        if trip.started_at and trip.ended_at:
            duration = round(
                (_as_naive(trip.ended_at) - _as_naive(trip.started_at)).total_seconds() / 60,
                2,
            )
            durations.append(duration)

        delay = _trip_delay_minutes(trip)
        if delay is not None:
            delays.append(delay)
            if delay > DELAY_THRESHOLD_MINUTES:
                delayed_count += 1

        history_item = {
            "trip_id": trip.id,
            "route_id": trip.route_id,
            "route_name": trip.route.name,
            "vehicle_id": trip.route.vehicle_id,
            "vehicle_plate": trip.route.vehicle.plate_number if trip.route.vehicle else None,
            "driver_id": trip.driver_id,
            "driver_name": trip.driver.name,
            "status": trip.status,
            "created_at": trip.created_at,
            "started_at": trip.started_at,
            "ended_at": trip.ended_at,
            "duration_minutes": duration,
            "delay_minutes": delay,
            "passengers_booked": 0,
        }
        trip_history.append(history_item)
        history_by_trip_id[trip.id] = history_item

    report_route_ids = None
    if driver_id is not None:
        report_route_ids = {trip.route_id for trip in filtered_trips}

    booking_query = db.query(models.Booking).join(models.Route)
    if route_id is not None:
        booking_query = booking_query.filter(models.Booking.route_id == route_id)
    if vehicle_id is not None:
        booking_query = booking_query.filter(models.Route.vehicle_id == vehicle_id)
    if organization_id is not None:
        booking_query = booking_query.filter(models.Route.organization_id == organization_id)
    elif unassigned_organization:
        booking_query = booking_query.filter(models.Route.organization_id.is_(None))
    if report_route_ids is not None:
        if report_route_ids:
            booking_query = booking_query.filter(models.Booking.route_id.in_(report_route_ids))
        else:
            booking_query = booking_query.filter(models.Booking.route_id == -1)
    if from_date:
        booking_query = booking_query.filter(
            models.Booking.created_at >= datetime.combine(from_date, time.min)
        )
    if to_date:
        booking_query = booking_query.filter(
            models.Booking.created_at < datetime.combine(to_date + timedelta(days=1), time.min)
        )
    bookings = booking_query.all()
    booking_counts = {}
    for booking in bookings:
        if booking.status == "confirmed":
            booking_counts[booking.route_id] = booking_counts.get(booking.route_id, 0) + 1

    route_query = db.query(models.Route)
    if route_id is not None:
        route_query = route_query.filter(models.Route.id == route_id)
    if vehicle_id is not None:
        route_query = route_query.filter(models.Route.vehicle_id == vehicle_id)
    if organization_id is not None:
        route_query = route_query.filter(models.Route.organization_id == organization_id)
    elif unassigned_organization:
        route_query = route_query.filter(models.Route.organization_id.is_(None))
    if report_route_ids is not None:
        if report_route_ids:
            route_query = route_query.filter(models.Route.id.in_(report_route_ids))
        else:
            route_query = route_query.filter(models.Route.id == -1)
    route_names = {
        route.id: route.name for route in route_query.order_by(models.Route.name).all()
    }
    passengers_per_route = [
        {
            "route_id": selected_route_id,
            "route_name": route_names[selected_route_id],
            "passengers_booked": booking_counts.get(selected_route_id, 0),
        }
        for selected_route_id in route_names
    ]
    for trip in filtered_trips:
        history_by_trip_id[trip.id]["passengers_booked"] = booking_counts.get(trip.route_id, 0)

    alert_query = db.query(models.EmergencyAlert)
    if from_date:
        alert_query = alert_query.filter(
            models.EmergencyAlert.created_at >= datetime.combine(from_date, time.min)
        )
    if to_date:
        alert_query = alert_query.filter(
            models.EmergencyAlert.created_at < datetime.combine(to_date + timedelta(days=1), time.min)
        )
    alerts = alert_query.all()
    has_trip_filters = route_id is not None or vehicle_id is not None or driver_id is not None
    filtered_trip_ids = {trip.id for trip in filtered_trips}
    sos_count = sum(
        1 for alert in alerts
        if not has_trip_filters or alert.trip_id in filtered_trip_ids
    )

    return {
        "trips_per_day": [
            {"date": day, "trips": count}
            for day, count in sorted(trip_counts_by_day.items())
        ],
        "completed_vs_cancelled": statuses,
        "on_time_vs_delayed": {
            "on_time": len(delays) - delayed_count,
            "delayed": delayed_count,
        },
        "average_duration_minutes": round(sum(durations) / len(durations), 2) if durations else None,
        "average_delay_minutes": round(sum(delays) / len(delays), 2) if delays else None,
        "passengers_booked_per_route": passengers_per_route,
        "sos_count": sos_count,
        "trip_history": trip_history,
    }
