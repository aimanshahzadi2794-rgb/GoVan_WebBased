from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import require_role, get_current_user

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/", response_model=List[schemas.BookingOut])
def list_bookings(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Booking)
    if user.role == models.UserRole.passenger:
        q = q.filter(models.Booking.passenger_id == user.id)
    elif user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Role is not permitted to view bookings")
    bookings = q.options(
        joinedload(models.Booking.route),
        joinedload(models.Booking.boarding_stop),
        joinedload(models.Booking.dropoff_stop),
    ).order_by(models.Booking.id.desc()).all()
    return [_booking_response(booking) for booking in bookings]


def _booking_response(booking: models.Booking):
    return {
        "id": booking.id,
        "passenger_id": booking.passenger_id,
        "route_id": booking.route_id,
        "route_name": booking.route.name,
        "boarding_stop_id": booking.boarding_stop_id,
        "boarding_stop_name": booking.boarding_stop.name if booking.boarding_stop else None,
        "dropoff_stop_id": booking.dropoff_stop_id,
        "dropoff_stop_name": booking.dropoff_stop.name if booking.dropoff_stop else None,
        "status": booking.status,
        "created_at": booking.created_at,
    }


@router.post("/", response_model=schemas.BookingOut, status_code=201)
def create_booking(
    payload: schemas.BookingCreate,
    db: Session = Depends(get_db),
    passenger: models.User = Depends(require_role("passenger")),
):
    route = db.get(models.Route, payload.route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if payload.boarding_stop_id is not None:
        boarding_stop = db.get(models.Stop, payload.boarding_stop_id)
        if not boarding_stop or boarding_stop.route_id != route.id:
            raise HTTPException(status_code=400, detail="Boarding stop must belong to the selected route")
    else:
        boarding_stop = None
    if payload.dropoff_stop_id is not None:
        dropoff_stop = db.get(models.Stop, payload.dropoff_stop_id)
        if not dropoff_stop or dropoff_stop.route_id != route.id:
            raise HTTPException(status_code=400, detail="Drop-off stop must belong to the selected route")
    else:
        dropoff_stop = None
    if (
        boarding_stop is not None
        and dropoff_stop is not None
        and dropoff_stop.sequence <= boarding_stop.sequence
    ):
        raise HTTPException(status_code=400, detail="Drop-off stop must be after the boarding stop")

    # Capacity check against the assigned vehicle, matching FR-BKG rules.
    if route.vehicle_id:
        vehicle = db.get(models.Vehicle, route.vehicle_id)
        active_count = db.query(models.Booking).filter(
            models.Booking.route_id == route.id, models.Booking.status == "confirmed"
        ).count()
        if vehicle and active_count >= vehicle.capacity:
            raise HTTPException(status_code=400, detail="This route is at full capacity")

    booking = models.Booking(
        passenger_id=passenger.id,
        route_id=payload.route_id,
        boarding_stop_id=payload.boarding_stop_id,
        dropoff_stop_id=payload.dropoff_stop_id,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return _booking_response(booking)


@router.patch("/{booking_id}/cancel", response_model=schemas.BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    passenger: models.User = Depends(require_role("passenger")),
):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id, models.Booking.passenger_id == passenger.id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return _booking_response(booking)
