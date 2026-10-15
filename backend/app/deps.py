from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .auth import decode_access_token
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
    if user_id is None:
        raise credentials_error
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_error
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
