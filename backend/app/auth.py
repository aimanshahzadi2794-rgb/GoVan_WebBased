"""
Basic authentication: password hashing + JWT issue/verify.

This is intentionally "basic auth" as requested for the MVP: email +
password, bcrypt hashing, a signed JWT with a short-ish expiry. No
refresh tokens, no OAuth providers, no MFA -- those are documented as
later hardening, not MVP scope (see NFR-SEC in the SRS for the full
target).
"""
import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

_configured_secret = os.getenv("GOVAN_SECRET_KEY")
if not _configured_secret and os.getenv("GOVAN_ENV", "development").lower() == "production":
    raise RuntimeError("GOVAN_SECRET_KEY must be configured when GOVAN_ENV=production")
if not _configured_secret:
    warnings.warn(
        "GOVAN_SECRET_KEY is unset; using an ephemeral development key. Sessions will reset on restart.",
        RuntimeWarning,
        stacklevel=2,
    )
SECRET_KEY = _configured_secret or secrets.token_urlsafe(48)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hour session, MVP-simple

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
