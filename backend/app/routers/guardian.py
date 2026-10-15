from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_role

router = APIRouter(prefix="/guardian", tags=["guardian"])


@router.get("/passengers", response_model=List[schemas.GuardianPassengerOut])
def list_guardian_passengers(
    db: Session = Depends(get_db),
    guardian: models.User = Depends(require_role("guardian")),
):
    links = (
        db.query(models.GuardianLink, models.User)
        .join(models.User, models.User.id == models.GuardianLink.passenger_id)
        .filter(models.GuardianLink.guardian_id == guardian.id)
        .order_by(models.User.name, models.User.id)
        .all()
    )
    return [
        {
            "id": passenger.id,
            "name": passenger.name,
            "email": passenger.email,
            "relationship": link.relationship_label,
        }
        for link, passenger in links
    ]
