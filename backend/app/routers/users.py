from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_password
from ..database import get_db
from ..deps import (
    ensure_organization_access,
    is_platform_admin,
    log_activity,
    require_organization_manager,
    scope_organization_query,
)

router = APIRouter(prefix="/users", tags=["users"])


def _ensure_organization_exists(db: Session, organization_id: int | None):
    if organization_id is not None and db.get(models.Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")


@router.get("/", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    if admin.role in {models.UserRole.organization_admin, models.UserRole.fleet_manager} and admin.organization_id is None:
        return []
    query = scope_organization_query(db.query(models.User), models.User, admin)
    return query.order_by(models.User.created_at.desc(), models.User.id.desc()).all()


@router.post("/", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.AdminUserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    organization_id = payload.organization_id
    if not is_platform_admin(admin):
        if admin.organization_id is None:
            raise HTTPException(status_code=403, detail="An organization must be assigned to this account")
        if payload.role not in {
            models.UserRole.driver,
            models.UserRole.passenger,
            models.UserRole.guardian,
        }:
            raise HTTPException(status_code=403, detail="Only platform administrators can create manager accounts")
        if organization_id is not None and organization_id != admin.organization_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        organization_id = admin.organization_id
    elif payload.role in {
        models.UserRole.super_admin,
        models.UserRole.organization_admin,
        models.UserRole.fleet_manager,
    } and organization_id is None:
        if payload.role == models.UserRole.super_admin:
            raise HTTPException(status_code=400, detail="Super administrators are platform-wide and must not have an organization")
        raise HTTPException(status_code=400, detail="Manager accounts must be assigned to an organization")
    if payload.role in {models.UserRole.admin, models.UserRole.super_admin} and organization_id is not None:
        raise HTTPException(status_code=400, detail="Platform administrator accounts must not have an organization")
    _ensure_organization_exists(db, organization_id)
    if organization_id is not None:
        organization = db.get(models.Organization, organization_id)
        if not organization.is_active:
            raise HTTPException(status_code=400, detail="Cannot assign a user to a suspended organization")
    if db.query(models.User.id).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        organization_id=organization_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(
        db, admin, "user.created", "user", user.id,
        organization_id=user.organization_id,
        details={"role": user.role.value, "email": user.email},
    )
    db.commit()
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_organization_access(admin, user.organization_id)

    updates = payload.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        _ensure_organization_exists(db, updates["organization_id"])
        ensure_organization_access(admin, updates["organization_id"])
    if not is_platform_admin(admin) and updates.get("role") in {
        models.UserRole.admin,
        models.UserRole.super_admin,
        models.UserRole.organization_admin,
        models.UserRole.fleet_manager,
    }:
        raise HTTPException(status_code=403, detail="Only platform administrators can assign manager roles")
    if user.id == admin.id and (
        updates.get("role") not in (None, user.role)
        or updates.get("is_active") is False
    ):
        raise HTTPException(status_code=400, detail="You cannot deactivate or change the role of your own account")
    effective_role = updates.get("role", user.role)
    effective_organization_id = updates.get("organization_id", user.organization_id)
    if effective_role in {models.UserRole.admin, models.UserRole.super_admin} and effective_organization_id is not None:
        raise HTTPException(status_code=400, detail="Platform administrator accounts must not have an organization")
    if effective_role in {models.UserRole.organization_admin, models.UserRole.fleet_manager} and effective_organization_id is None:
        raise HTTPException(status_code=400, detail="Manager accounts must be assigned to an organization")

    for field, value in updates.items():
        if value is not None or field in {
            "license_number", "phone", "license_expiry", "organization_id"
        }:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    log_activity(
        db, admin, "user.updated", "user", user.id,
        organization_id=user.organization_id,
        details={"changed_fields": sorted(updates)},
    )
    db.commit()
    return user


@router.get("/{passenger_id}/guardians", response_model=List[schemas.GuardianLinkOut])
def list_guardians_for_passenger(
    passenger_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    passenger = db.get(models.User, passenger_id)
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    if passenger.role != models.UserRole.passenger:
        raise HTTPException(status_code=400, detail="Guardian links can only be listed for passengers")
    ensure_organization_access(admin, passenger.organization_id)
    return (
        db.query(models.GuardianLink)
        .filter(models.GuardianLink.passenger_id == passenger_id)
        .order_by(models.GuardianLink.id)
        .all()
    )


@router.post(
    "/{passenger_id}/guardians",
    response_model=schemas.GuardianLinkOut,
    status_code=201,
)
def link_guardian(
    passenger_id: int,
    payload: schemas.GuardianLinkCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    passenger = db.get(models.User, passenger_id)
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    guardian = db.get(models.User, payload.guardian_id)
    if not guardian:
        raise HTTPException(status_code=404, detail="Guardian not found")
    if passenger.role != models.UserRole.passenger:
        raise HTTPException(status_code=400, detail="The linked account must be a passenger")
    if guardian.role != models.UserRole.guardian:
        raise HTTPException(status_code=400, detail="The linked account must have the guardian role")
    ensure_organization_access(admin, passenger.organization_id)
    if guardian.organization_id != passenger.organization_id:
        raise HTTPException(status_code=400, detail="Passenger and guardian must belong to the same organization")
    if guardian.id == passenger.id:
        raise HTTPException(status_code=400, detail="A user cannot be their own guardian")
    relationship_label = payload.relationship.strip()
    if not relationship_label:
        raise HTTPException(status_code=400, detail="Relationship cannot be empty")
    existing_link = db.query(models.GuardianLink).filter(
        models.GuardianLink.guardian_id == guardian.id,
        models.GuardianLink.passenger_id == passenger.id,
    ).first()
    if existing_link:
        raise HTTPException(status_code=409, detail="Guardian is already linked to this passenger")

    link = models.GuardianLink(
        guardian_id=guardian.id,
        passenger_id=passenger.id,
        relationship_label=relationship_label,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{passenger_id}/guardians/{guardian_id}", status_code=204)
def unlink_guardian(
    passenger_id: int,
    guardian_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_organization_manager()),
):
    link = db.query(models.GuardianLink).filter(
        models.GuardianLink.passenger_id == passenger_id,
        models.GuardianLink.guardian_id == guardian_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Guardian link not found")
    passenger = db.get(models.User, passenger_id)
    ensure_organization_access(admin, passenger.organization_id if passenger else None)
    db.delete(link)
    db.commit()
