from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_role, get_current_user

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _ensure_organization_exists(db: Session, organization_id: int | None):
    if organization_id is not None and db.get(models.Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")


def _vehicle_occupied_capacity(db: Session, vehicle: models.Vehicle) -> int:
    route_ids = [r.id for r in db.query(models.Route).filter(models.Route.vehicle_id == vehicle.id).all()]
    if not route_ids:
        return 0
    return db.query(models.Booking).filter(
        models.Booking.route_id.in_(route_ids),
        models.Booking.status == "confirmed",
    ).count()


def _vehicle_is_on_route(db: Session, vehicle: models.Vehicle) -> bool:
    route_ids = [r.id for r in db.query(models.Route).filter(models.Route.vehicle_id == vehicle.id).all()]
    if not route_ids:
        return False
    return db.query(models.Trip).filter(
        models.Trip.route_id.in_(route_ids),
        models.Trip.status == "active",
    ).first() is not None


def _enrich_vehicle(db: Session, vehicle: models.Vehicle) -> models.Vehicle:
    occupied = _vehicle_occupied_capacity(db, vehicle)
    vehicle.occupied_capacity = occupied
    vehicle.available_capacity = max((vehicle.capacity or 0) - occupied, 0)
    vehicle.on_route = _vehicle_is_on_route(db, vehicle)
    return vehicle


@router.get("/", response_model=List[schemas.VehicleOut])
def list_vehicles(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    vehicles = db.query(models.Vehicle).all()
    return [_enrich_vehicle(db, v) for v in vehicles]


@router.get("/summary", response_model=schemas.FleetSummary)
def fleet_summary(db: Session = Depends(get_db), admin: models.User = Depends(require_role("admin"))):
    vehicles = db.query(models.Vehicle).all()
    enriched = [_enrich_vehicle(db, v) for v in vehicles]

    on_route = sum(1 for v in enriched if v.on_route)
    idle = sum(1 for v in enriched if not v.on_route and v.status == "idle")
    maintenance = sum(1 for v in enriched if v.status == "maintenance")
    offline = sum(1 for v in enriched if v.status == "offline")

    total_capacity = sum(v.capacity or 0 for v in enriched)
    occupied_capacity = sum(v.occupied_capacity for v in enriched)
    available_capacity = max(total_capacity - occupied_capacity, 0)

    on_route_vehicles = [v for v in enriched if v.on_route]
    if on_route_vehicles:
        avg_occ = sum(
            (v.occupied_capacity / v.capacity * 100) if v.capacity else 0
            for v in on_route_vehicles
        ) / len(on_route_vehicles)
    else:
        avg_occ = 0.0

    return schemas.FleetSummary(
        total_vehicles=len(vehicles),
        active_vehicles=sum(1 for v in vehicles if v.status == "active"),
        internal_vehicles=sum(1 for v in vehicles if v.ownership_type == "internal"),
        external_vehicles=sum(1 for v in vehicles if v.ownership_type == "external"),
        blocked_vehicles=sum(1 for v in vehicles if v.compliance_status == "blocked"),
        attention_vehicles=sum(1 for v in vehicles if v.compliance_status in {"attention", "service_due"}),
        total_capacity=total_capacity,
        on_route=on_route,
        idle=idle,
        maintenance=maintenance,
        offline=offline,
        utilization_pct=round((on_route / len(vehicles) * 100) if vehicles else 0, 1),
        average_occupancy_pct=round(avg_occ, 1),
        occupied_capacity=occupied_capacity,
        available_capacity=available_capacity,
    )


@router.post("/", response_model=schemas.VehicleOut, status_code=201)
def create_vehicle(
    payload: schemas.VehicleCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    _ensure_organization_exists(db, payload.organization_id)
    fuel_type = payload.fuel_type.strip().lower()
    ownership_type = payload.ownership_type.strip().lower()
    if fuel_type == "cng":
        raise HTTPException(status_code=400, detail="CNG vehicles cannot be activated for GoVan fleet operations")
    if ownership_type not in {"internal", "external"}:
        raise HTTPException(status_code=400, detail="Ownership type must be internal or external")

    existing = db.query(models.Vehicle).filter(models.Vehicle.plate_number == payload.plate_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plate number already registered")
    data = payload.model_dump()
    data["fuel_type"] = fuel_type
    data["ownership_type"] = ownership_type
    data["vehicle_type"] = data["vehicle_type"].strip().lower() or "van"
    vehicle = models.Vehicle(**data)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}/status", response_model=schemas.VehicleOut)
def set_vehicle_status(
    vehicle_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    status = payload.get("status")
    if status not in {"active", "idle", "maintenance", "offline"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    if _vehicle_is_on_route(db, vehicle) and status != vehicle.status:
        raise HTTPException(status_code=400, detail="Cannot change status while vehicle is on an active trip")
    vehicle.status = status
    db.commit()
    db.refresh(vehicle)
    return _enrich_vehicle(db, vehicle)


@router.patch("/{vehicle_id}", response_model=schemas.VehicleOut)
def update_vehicle(
    vehicle_id: int,
    payload: schemas.VehicleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    updates = payload.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        _ensure_organization_exists(db, updates["organization_id"])
    plate_number = updates.get("plate_number")
    if plate_number is not None:
        plate_number = plate_number.strip()
        if not plate_number:
            raise HTTPException(status_code=400, detail="Plate number cannot be empty")
        duplicate = db.query(models.Vehicle).filter(
            models.Vehicle.plate_number == plate_number,
            models.Vehicle.id != vehicle.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Plate number already registered")
        updates["plate_number"] = plate_number

    if "model" in updates:
        updates["model"] = updates["model"].strip()
        if not updates["model"]:
            raise HTTPException(status_code=400, detail="Model cannot be empty")

    for field, value in updates.items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return _enrich_vehicle(db, vehicle)
