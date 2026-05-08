import os
from datetime import timedelta

import cloudinary
import cloudinary.uploader
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decode_email_token,
    get_current_confirmed_user,
    get_current_user,
    verify_password,
)
from crud import (
    create_contact,
    create_user,
    delete_contact,
    get_contact,
    get_contacts,
    get_upcoming_birthdays,
    get_user_by_email,
    update_contact,
)
from database import Base, engine, get_db
from email_service import send_verification_email
from models import User
from rate_limiter import limit_me_route
from schemas import ContactCreate, ContactResponse, ContactUpdate, Token, UserCreate, UserResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Contacts API",
    description="REST API for storing and managing contacts",
    version="2.0.0",
)

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


@app.get("/")
def root():
    return {"message": "Contacts API is running"}


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    user = create_user(db, user_data.username, user_data.email, user_data.password)
    await send_verification_email(user.email, user.username)
    return user


@app.post("/auth/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    email = decode_email_token(token)
    user = get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.confirmed:
        return {"message": "Email is already verified"}

    user.confirmed = True
    db.commit()
    return {"message": "Email verified successfully"}


@app.post("/auth/request-email")
async def request_email_verification(current_user: User = Depends(get_current_user)):
    if current_user.confirmed:
        return {"message": "Email is already verified"}
    await send_verification_email(current_user.email, current_user.username)
    return {"message": "Verification email sent"}


@app.get("/users/me", response_model=UserResponse)
def read_users_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = Depends(limit_me_route),
):
    return current_user


@app.patch("/users/avatar", response_model=UserResponse)
def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db),
):
    if not os.getenv("CLOUDINARY_NAME"):
        raise HTTPException(status_code=500, detail="Cloudinary is not configured")

    result = cloudinary.uploader.upload(
        file.file,
        folder="goit-pythonweb-hw-10/avatars",
        public_id=f"user_{current_user.id}",
        overwrite=True,
        resource_type="image",
    )
    current_user.avatar = result.get("secure_url")
    db.commit()
    db.refresh(current_user)
    return current_user


@app.post("/contacts/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_new_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    return create_contact(db, contact, current_user.id)


@app.get("/contacts/", response_model=list[ContactResponse])
def read_contacts(
    first_name: str | None = Query(None, description="Search by first name"),
    last_name: str | None = Query(None, description="Search by last name"),
    email: str | None = Query(None, description="Search by email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    return get_contacts(db, current_user.id, first_name=first_name, last_name=last_name, email=email)


@app.get("/contacts/upcoming/birthdays", response_model=list[ContactResponse])
def upcoming_birthdays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    return get_upcoming_birthdays(db, current_user.id)


@app.get("/contacts/{contact_id}", response_model=ContactResponse)
def read_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    contact = get_contact(db, contact_id, current_user.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@app.put("/contacts/{contact_id}", response_model=ContactResponse)
def update_existing_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    contact = update_contact(db, contact_id, contact_data, current_user.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@app.delete("/contacts/{contact_id}", response_model=ContactResponse)
def delete_existing_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    contact = delete_contact(db, contact_id, current_user.id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact
