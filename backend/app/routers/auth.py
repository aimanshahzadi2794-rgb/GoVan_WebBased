import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text

from .. import models, schemas
from ..database import get_db
from ..auth import hash_password, verify_password, create_access_token
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
PASSWORD_RESET_EXPIRE_MINUTES = 30


def _password_reset_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_reset_url(token: str) -> str:
    configured_url = os.getenv("GOVAN_PASSWORD_RESET_URL", "http://localhost:5174/")
    parts = urlsplit(configured_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["reset_token"] = token
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)):
    needs_first_admin = not db.query(models.User.id).filter(
        models.User.role == models.UserRole.admin
    ).first()
    return {"needs_first_admin": needs_first_admin}


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if payload.role == "admin" and db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))

    if payload.organization_id is not None and db.get(
        models.Organization, payload.organization_id
    ) is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if payload.role == "admin" and db.query(models.User.id).filter(
        models.User.role == models.UserRole.admin
    ).first():
        raise HTTPException(status_code=403, detail="The first administrator has already been created")
    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=models.UserRole(payload.role),
        organization_id=payload.organization_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses "username" as the field name; we treat it as email.
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return schemas.Token(access_token=token, user=user)


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == payload.email,
        models.User.is_active.is_(True),
    ).first()
    if user:
        now = datetime.now(timezone.utc)
        reset_token = secrets.token_urlsafe(32)
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.used_at.is_(None),
        ).update(
            {models.PasswordResetToken.used_at: now},
            synchronize_session=False,
        )
        db.add(models.PasswordResetToken(
            user_id=user.id,
            token_hash=_password_reset_hash(reset_token),
            expires_at=now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        ))
        db.commit()
        logger.info("Password reset link generated: %s", _password_reset_url(reset_token))

    return {"message": "If an active account exists for that email, a password reset link has been generated."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    reset_record = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == _password_reset_hash(payload.token),
        models.PasswordResetToken.used_at.is_(None),
        models.PasswordResetToken.expires_at > now,
    ).first()
    if not reset_record or not reset_record.user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    reset_record.user.hashed_password = hash_password(payload.password)
    reset_record.used_at = now
    db.commit()
    return {"message": "Password has been reset successfully."}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
