from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_role, get_current_user
from ..notification_service import (
    notify_passenger_and_guardians,
    notify_trip_audience,
    notify_users,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=List[schemas.AlertOut])
def list_alerts(db: Session = Depends(get_db), admin: models.User = Depends(require_role("admin"))):
    return db.query(models.EmergencyAlert).order_by(models.EmergencyAlert.id.desc()).all()


@router.get("/mine", response_model=List[schemas.AlertOut])
def list_my_alerts(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("driver", "passenger")),
):
    return db.query(models.EmergencyAlert).filter(
        models.EmergencyAlert.raised_by_id == user.id
    ).order_by(models.EmergencyAlert.created_at.desc(), models.EmergencyAlert.id.desc()).all()


@router.post("/", response_model=schemas.AlertOut, status_code=201)
def raise_alert(
    payload: schemas.AlertCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("driver", "passenger")),
):
    trip = None
    if payload.trip_id is not None:
        trip = db.get(models.Trip, payload.trip_id)
        if not trip or trip.status != "active":
            raise HTTPException(status_code=400, detail="SOS trip must be active")
        if user.role == models.UserRole.driver and trip.driver_id != user.id:
            raise HTTPException(status_code=403, detail="You can only raise an SOS for your own trip")
        if user.role == models.UserRole.passenger:
            booking = db.query(models.Booking.id).filter(
                models.Booking.passenger_id == user.id,
                models.Booking.route_id == trip.route_id,
                models.Booking.status == "confirmed",
            ).first()
            if not booking:
                raise HTTPException(status_code=403, detail="You are not booked on this trip")

    alert = models.EmergencyAlert(raised_by_id=user.id, **payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    if trip:
        notify_trip_audience(
            db,
            trip,
            event_key=f"alert:{alert.id}:sos",
            title="SOS emergency alert",
            message=f"An SOS alert was raised for {trip.route.name}.",
            event_type="sos",
            include_driver=True,
            alert_id=alert.id,
        )
    if user.role == models.UserRole.passenger and trip is None:
        notify_passenger_and_guardians(
            db,
            user.id,
            event_key=f"alert:{alert.id}:sos-raiser",
            title="SOS emergency alert",
            message=f"{user.name} has raised an SOS alert.",
            event_type="sos",
            trip_id=trip.id if trip else None,
            alert_id=alert.id,
        )
    admin_ids = {
        admin_id
        for (admin_id,) in db.query(models.User.id).filter(
            models.User.role == models.UserRole.admin,
            models.User.is_active.is_(True),
        ).all()
    }
    notify_users(
        db,
        admin_ids,
        event_key=f"alert:{alert.id}:admin-sos",
        title="SOS emergency alert",
        message=f"{user.name} raised an emergency alert.",
        event_type="sos",
        trip_id=trip.id if trip else None,
        alert_id=alert.id,
    )
    db.commit()
    return alert


@router.patch("/{alert_id}/resolve", response_model=schemas.AlertOut)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    alert = db.get(models.EmergencyAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    db.commit()
    db.refresh(alert)
    return alert
