from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_organization_manager, scope_organization_query

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/", response_model=List[schemas.ActivityLogOut])
def list_activity_logs(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organization_manager()),
):
    query = scope_organization_query(db.query(models.ActivityLog), models.ActivityLog, user)
    return query.order_by(
        models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc()
    ).limit(500).all()
