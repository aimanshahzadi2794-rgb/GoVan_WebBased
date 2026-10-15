from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_role

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/", response_model=List[schemas.OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    return db.query(models.Organization).order_by(models.Organization.name).all()


@router.post("/", response_model=schemas.OrganizationOut, status_code=201)
def create_organization(
    payload: schemas.OrganizationCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organization name cannot be empty")
    organization = models.Organization(
        name=name,
        type=payload.type,
        contact_email=payload.contact_email,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@router.patch("/{organization_id}", response_model=schemas.OrganizationOut)
def update_organization(
    organization_id: int,
    payload: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    organization = db.get(models.Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if not updates["name"]:
            raise HTTPException(status_code=400, detail="Organization name cannot be empty")
    for field, value in updates.items():
        setattr(organization, field, value)
    db.commit()
    db.refresh(organization)
    return organization


@router.delete("/{organization_id}", status_code=204)
def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    organization = db.get(models.Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    db.query(models.User).filter(
        models.User.organization_id == organization.id
    ).update({models.User.organization_id: None}, synchronize_session=False)
    db.query(models.Vehicle).filter(
        models.Vehicle.organization_id == organization.id
    ).update({models.Vehicle.organization_id: None}, synchronize_session=False)
    db.query(models.Route).filter(
        models.Route.organization_id == organization.id
    ).update({models.Route.organization_id: None}, synchronize_session=False)
    db.delete(organization)
    db.commit()
    return Response(status_code=204)
