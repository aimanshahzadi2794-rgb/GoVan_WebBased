from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .auth import decode_access_token
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

PLATFORM_ADMIN_ROLES = {models.UserRole.admin, models.UserRole.super_admin}
ORGANIZATION_MANAGER_ROLES = {
    models.UserRole.organization_admin,
    models.UserRole.fleet_manager,
}


def is_platform_admin(user: models.User) -> bool:
    return user.role in PLATFORM_ADMIN_ROLES


def ensure_organization_access(user: models.User, organization_id: int | None):
    """Reject cross-tenant resource access independently of frontend filtering."""
    if is_platform_admin(user):
        return
    if user.organization_id is None or organization_id != user.organization_id:
        # Return 404 so callers cannot use IDs to enumerate another tenant's data.
        raise HTTPException(status_code=404, detail="Resource not found")


def scope_organization_query(query, entity, user: models.User):
    """Apply a tenant predicate to a query for rows with a direct org FK."""
    if is_platform_admin(user):
        return query
    column = entity.id if entity is models.Organization else entity.organization_id
    if user.role in ORGANIZATION_MANAGER_ROLES and user.organization_id is None:
        return query.filter(column == -1)
    if user.organization_id is None:
        return query.filter(column.is_(None))
    return query.filter(column == user.organization_id)


def log_activity(
    db: Session,
    actor: models.User,
    action: str,
    entity_type: str,
    entity_id: int | None,
    *,
    organization_id: int | None = None,
    details: dict | None = None,
):
    db.add(models.ActivityLog(
        actor_id=actor.id,
        organization_id=organization_id if organization_id is not None else actor.organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    ))


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise credentials_error
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise credentials_error
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_error
    if user.organization_id is not None and user.role not in PLATFORM_ADMIN_ROLES:
        organization = db.get(models.Organization, user.organization_id)
        if organization is None or not organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This organization is suspended",
            )
    return user


def require_role(*allowed_roles: str):
    """Dependency factory: raise 403 unless current user's role is in allowed_roles.

    This is the multi-tenant / role isolation control called out in the SRS
    (NFR-ISO-01 in spirit) -- centralized here instead of re-checked ad hoc
    in every route.
    """
    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' is not permitted to perform this action",
            )
        return user
    return checker


def require_organization_manager():
    return require_role("admin", "super_admin", "organization_admin", "fleet_manager")


def require_platform_admin():
    return require_role("admin", "super_admin")
