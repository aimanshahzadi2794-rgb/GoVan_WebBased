from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import ensure_organization_access, require_organization_manager

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/", response_model=List[schemas.MaintenanceRecordOut])
def list_maintenance(
    vehicle_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    q = db.query(models.MaintenanceRecord)
    if admin.role not in {models.UserRole.admin, models.UserRole.super_admin}:
        q = q.join(models.Vehicle).filter(models.Vehicle.organization_id == admin.organization_id)
    if vehicle_id is not None:
        q = q.filter(models.MaintenanceRecord.vehicle_id == vehicle_id)
    return q.order_by(models.MaintenanceRecord.id.desc()).all()


@router.post("/", response_model=schemas.MaintenanceRecordOut, status_code=201)
def create_maintenance_record(
    payload: schemas.MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    vehicle = db.get(models.Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    ensure_organization_access(admin, vehicle.organization_id)
    record = models.MaintenanceRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{record_id}/complete", response_model=schemas.MaintenanceRecordOut)
def complete_maintenance_record(
    record_id: int,
    payload: Optional[schemas.MaintenanceComplete] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    record = db.get(models.MaintenanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    ensure_organization_access(admin, record.vehicle.organization_id)
    record.status = "completed"
    record.completed_at = datetime.now(timezone.utc)
    if payload and payload.notes:
        record.notes = payload.notes
    db.commit()
    db.refresh(record)
    return record
