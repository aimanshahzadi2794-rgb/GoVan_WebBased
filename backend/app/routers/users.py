from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_password
from ..database import get_db
from ..deps import require_role

router = APIRouter(prefix="/users", tags=["users"])


def _ensure_organization_exists(db: Session, organization_id: int | None):
    if organization_id is not None and db.get(models.Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")


@router.get("/", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    return db.query(models.User).order_by(models.User.created_at.desc(), models.User.id.desc()).all()


@router.post("/", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.AdminUserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    _ensure_organization_exists(db, payload.organization_id)
    if db.query(models.User.id).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        organization_id=payload.organization_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        _ensure_organization_exists(db, updates["organization_id"])
    if user.id == admin.id and (
        updates.get("role") not in (None, models.UserRole.admin)
        or updates.get("is_active") is False
    ):
        raise HTTPException(status_code=400, detail="You cannot deactivate or demote your own account")

    for field, value in updates.items():
        if value is not None or field in {
            "license_number", "phone", "license_expiry", "organization_id"
        }:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{passenger_id}/guardians", response_model=List[schemas.GuardianLinkOut])
def list_guardians_for_passenger(
    passenger_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    passenger = db.get(models.User, passenger_id)
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    if passenger.role != models.UserRole.passenger:
        raise HTTPException(status_code=400, detail="Guardian links can only be listed for passengers")
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
    admin: models.User = Depends(require_role("admin")),
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
    admin: models.User = Depends(require_role("admin")),
):
    link = db.query(models.GuardianLink).filter(
        models.GuardianLink.passenger_id == passenger_id,
        models.GuardianLink.guardian_id == guardian_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Guardian link not found")
    db.delete(link)
    db.commit()
