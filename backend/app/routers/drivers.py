from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_role, get_current_user

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.patch("/me/profile", response_model=schemas.UserOut)
def update_driver_profile(
    payload: schemas.DriverProfileUpdate,
    db: Session = Depends(get_db),
    driver: models.User = Depends(require_role("driver")),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(driver, field, value)
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/", response_model=List[schemas.UserOut])
def list_drivers(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.User).filter(models.User.role == models.UserRole.driver).all()


@router.patch("/{driver_id}/assign", response_model=schemas.UserOut)
def assign_vehicle(
    driver_id: int,
    payload: schemas.DriverAssign,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    driver = db.query(models.User).filter(
        models.User.id == driver_id, models.User.role == models.UserRole.driver
    ).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if payload.vehicle_id is not None:
        vehicle = db.get(models.Vehicle, payload.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
    driver.vehicle_id = payload.vehicle_id
    db.commit()
    db.refresh(driver)
    return driver
