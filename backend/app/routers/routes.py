from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import (
    ensure_organization_access,
    is_platform_admin,
    log_activity,
    require_organization_manager,
    scope_organization_query,
    get_current_user,
)
from ..routing import route_metrics


router = APIRouter(prefix="/routes", tags=["routes"])


def _ensure_organization_exists(db: Session, organization_id: int | None):
    if organization_id is not None and db.get(models.Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")


def _enrich(route: models.Route, confirmed_bookings: int = 0) -> models.Route:
    """
    Calculate and attach route distance and estimated duration.
    Use road-network metrics from a configured OSRM-compatible service,
    falling back to Haversine distance with an explicit source label.
    """
    distance, duration, geometry, source, routing_duration, traffic_scenario = route_metrics(route.stops)
    route.distance_km = distance
    route.estimated_duration_min = duration
    route.geometry = geometry
    route.routing_source = source
    route.routing_duration_min = routing_duration
    route.traffic_scenario = traffic_scenario
    route.vehicle_capacity = route.vehicle.capacity if route.vehicle else None
    route.confirmed_bookings = confirmed_bookings
    route.seats_left = (
        max(route.vehicle.capacity - confirmed_bookings, 0)
        if route.vehicle
        else None
    )

    return route


@router.get("/", response_model=List[schemas.RouteOut])
def list_routes(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    routes = scope_organization_query(db.query(models.Route), models.Route, user).all()
    confirmed_counts = dict(
        db.query(models.Booking.route_id, func.count(models.Booking.id))
        .filter(models.Booking.status == "confirmed")
        .group_by(models.Booking.route_id)
        .all()
    )
    return [
        _enrich(route, confirmed_counts.get(route.id, 0))
        for route in routes
    ]


@router.post("/", response_model=schemas.RouteOut, status_code=201)
def create_route(
    payload: schemas.RouteCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    organization_id = payload.organization_id
    if not is_platform_admin(admin):
        if admin.organization_id is None:
            raise HTTPException(status_code=403, detail="An organization must be assigned to this account")
        if organization_id is None:
            organization_id = admin.organization_id
    _ensure_organization_exists(db, organization_id)
    ensure_organization_access(admin, organization_id)
    if payload.vehicle_id is not None:
        vehicle = db.get(models.Vehicle, payload.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if vehicle.organization_id != organization_id:
            raise HTTPException(status_code=400, detail="Route and vehicle must belong to the same organization")
    route = models.Route(
        name=payload.name,
        pickup_time=payload.pickup_time,
        drop_time=payload.drop_time,
        vehicle_id=payload.vehicle_id,
        days_of_week=payload.days_of_week,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        organization_id=organization_id,
    )
    db.add(route)
    db.flush()  # assigns route.id without committing yet

    for stop_data in payload.stops:
        db.add(models.Stop(route_id=route.id, **stop_data.model_dump()))

    db.commit()
    db.refresh(route)
    log_activity(
        db, admin, "route.created", "route", route.id,
        organization_id=route.organization_id, details={"name": route.name},
    )
    db.commit()

    return _enrich(route)


def _ensure_route_editable(db: Session, route: models.Route):
    active_trip = db.query(models.Trip.id).filter(
        models.Trip.route_id == route.id,
        models.Trip.status == "active",
    ).first()
    if active_trip:
        raise HTTPException(status_code=409, detail="Cannot edit or delete a route with an in-progress trip")


@router.patch("/{route_id}", response_model=schemas.RouteOut)
def update_route(
    route_id: int,
    payload: schemas.RouteUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    route = db.get(models.Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    ensure_organization_access(admin, route.organization_id)
    _ensure_route_editable(db, route)

    updates = payload.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        _ensure_organization_exists(db, updates["organization_id"])
        ensure_organization_access(admin, updates["organization_id"])
    valid_from = updates.get("valid_from", route.valid_from)
    valid_to = updates.get("valid_to", route.valid_to)
    if valid_from and valid_to and valid_from > valid_to:
        raise HTTPException(status_code=400, detail="valid_from must be on or before valid_to")

    stop_payloads = updates.pop("stops", None)
    effective_organization_id = updates.get("organization_id", route.organization_id)
    effective_vehicle_id = updates.get("vehicle_id", route.vehicle_id)
    if effective_vehicle_id is not None:
        vehicle = db.get(models.Vehicle, effective_vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if vehicle.organization_id != effective_organization_id:
            raise HTTPException(status_code=400, detail="Route and vehicle must belong to the same organization")
    for field, value in updates.items():
        setattr(route, field, value)

    if stop_payloads is not None:
        route.stops.clear()
        route.stops.extend(
            models.Stop(**stop_data) for stop_data in stop_payloads
        )

    db.commit()
    db.refresh(route)
    log_activity(
        db, admin, "route.updated", "route", route.id,
        organization_id=route.organization_id,
        details={"changed_fields": sorted(updates)},
    )
    db.commit()
    return _enrich(route)


@router.delete("/{route_id}", status_code=204)
def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    route = db.get(models.Route, route_id)

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Route not found",
        )
    ensure_organization_access(admin, route.organization_id)

    _ensure_route_editable(db, route)
    log_activity(
        db, admin, "route.deleted", "route", route.id,
        organization_id=route.organization_id, details={"name": route.name},
    )
    db.delete(route)
    db.commit()

    return None
