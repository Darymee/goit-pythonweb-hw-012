from datetime import date
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class ContactBase(BaseModel):
    """Shared contact fields used by create, update and response schemas."""

    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=5, max_length=20)
    birthday: date
    additional_data: str | None = None


class ContactCreate(ContactBase):
    """Payload for contact creation."""

    pass


class ContactUpdate(BaseModel):
    """Partial payload for contact updates."""

    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, min_length=5, max_length=20)
    birthday: date | None = None
    additional_data: str | None = None


class ContactResponse(ContactBase):
    """Contact response returned by API routes."""

    id: int

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Payload for user registration."""

    username: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class UserResponse(BaseModel):
    """Public user data returned by API routes."""

    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    confirmed: bool
    role: str = "user"

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """OAuth2 bearer token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload for refreshing access token."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Payload for requesting a password reset email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Payload for confirming password reset with a token."""

    token: str
    new_password: str = Field(..., min_length=6, max_length=72)
