"""Authentication, authorization and token helper functions."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from cache import get_cached_user, set_cached_user
from database import get_db
from models import User

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-env")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
EMAIL_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_TOKEN_EXPIRE_HOURS", "24"))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a plain-text password."""
    return pwd_context.hash(password[:72])


def create_token(data: dict, expires_delta: timedelta, scope: str) -> str:
    """Create a signed JWT token with scope and expiration time."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "scope": scope, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived JWT access token."""
    expire_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(data, expire_delta, "access_token")


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a long-lived JWT refresh token."""
    expire_delta = expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(data, expire_delta, "refresh_token")


def create_email_token(email: str) -> str:
    """Create a JWT token for email verification."""
    return create_token(
        {"sub": email},
        timedelta(hours=EMAIL_TOKEN_EXPIRE_HOURS),
        "email_verification",
    )


def create_password_reset_token(email: str) -> str:
    """Create a JWT token for password reset flow."""
    return create_token(
        {"sub": email},
        timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        "password_reset",
    )


def decode_scoped_token(token: str, expected_scope: str) -> str:
    """Decode a JWT token and validate its scope, returning the subject email."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    if payload.get("scope") != expected_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token scope",
        )

    email = payload.get("sub")
    if not isinstance(email, str) or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )
    return email


def decode_email_token(token: str) -> str:
    """Decode an email verification token."""
    return decode_scoped_token(token, "email_verification")


def decode_password_reset_token(token: str) -> str:
    """Decode a password reset token."""
    return decode_scoped_token(token, "password_reset")


def decode_refresh_token(refresh_token: str) -> str:
    """Decode a refresh token and return its subject email."""
    try:
        return decode_scoped_token(refresh_token, "refresh_token")
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def _user_from_cache(data: dict) -> User:
    """Build a lightweight User object from cached safe fields."""
    user = User()
    user.id = data["id"]
    user.username = data["username"]
    user.email = data["email"]
    user.avatar = data.get("avatar")
    user.confirmed = data.get("confirmed", False)
    user.role = data.get("role", "user")
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Return the authenticated user, using Redis cache before database lookup."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != "access_token":
            raise credentials_exception
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    cached = get_cached_user(email)
    if cached:
        return _user_from_cache(cached)

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    set_cached_user(user)
    return user


def get_current_confirmed_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the current user only if the email address is confirmed."""
    if not current_user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not verified",
        )
    return current_user


def get_current_admin_user(current_user: User = Depends(get_current_confirmed_user)) -> User:
    """Return the current user only if the user has the admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
