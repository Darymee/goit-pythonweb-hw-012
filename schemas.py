from datetime import date
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class ContactBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=5, max_length=20)
    birthday: date
    additional_data: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, min_length=5, max_length=20)
    birthday: date | None = None
    additional_data: str | None = None


class ContactResponse(ContactBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
