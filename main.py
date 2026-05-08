import os
from datetime import timedelta

import cloudinary
import cloudinary.uploader
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_email_token,
    get_current_admin_user,
    get_current_confirmed_user,
    get_current_user,
    decode_password_reset_token,
    decode_refresh_token,
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
    update_user_password,
    update_user_refresh_token,
)
from database import Base, engine, get_db
from email_service import send_password_reset_email, send_verification_email
from models import User
from rate_limiter import limit_me_route
from schemas import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
)

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
    """
    Return a health-check message confirming that the API is running.

    :return: API status message.
    """
    return {"message": "Contacts API is running"}


@app.post(
    "/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Creates a user with a hashed password, stores it in the database,
    and sends an email verification message.

    :param user_data: User registration data.
    :param db: Database session dependency.
    :raises HTTPException: If the email already exists.
    :return: Created user object.
    """
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = create_user(db, user_data.username, user_data.email, user_data.password)
    await send_verification_email(user.email, user.username)
    return user


@app.post("/auth/login", response_model=Token)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate a user and return a JWT access token.

    :param form_data: OAuth2 login form with email and password.
    :param db: Database session dependency.
    :raises HTTPException: If credentials are invalid.
    :return: JWT access token.
    """
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
    refresh_token = create_refresh_token(data={"sub": user.email})
    update_user_refresh_token(db, user, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/auth/refresh", response_model=Token)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Issue a new access/refresh token pair from a valid refresh token."""
    email = decode_refresh_token(payload.refresh_token)
    user = get_user_by_email(db, email)

    if user is None or user.refresh_token != payload.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    update_user_refresh_token(db, user, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/auth/logout")
def logout_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current user's stored refresh token."""
    user = get_user_by_email(db, current_user.email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    update_user_refresh_token(db, user, None)
    return {"message": "Logged out successfully"}


@app.post("/auth/forgot-password")
async def forgot_password(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """
    Send password reset instructions to a user's email.

    Always returns a neutral response to prevent email enumeration.

    :param payload: Password reset request payload.
    :param db: Database session dependency.
    :return: Generic success message.
    """
    user = get_user_by_email(db, payload.email)

    if user:
        await send_password_reset_email(user.email, user.username)

    return {
        "message": "If this email exists, password reset instructions have been sent"
    }


@app.post("/auth/reset-password")
def reset_password(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """
    Reset a user's password using a valid reset token.

    :param payload: Password reset confirmation payload.
    :param db: Database session dependency.
    :raises HTTPException: If the user does not exist.
    :return: Password reset success message.
    """
    email = decode_password_reset_token(payload.token)
    user = get_user_by_email(db, email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_user_password(db, user, payload.new_password)

    return {"message": "Password changed successfully"}


@app.get("/auth/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verify a user's email address using a confirmation token.

    :param token: Email verification JWT token.
    :param db: Database session dependency.
    :raises HTTPException: If the user is not found.
    :return: Verification status message.
    """
    email = decode_email_token(token)
    user = get_user_by_email(db, email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.confirmed:
        return {"message": "Email is already verified"}

    user.confirmed = True
    db.commit()

    from cache import delete_cached_user

    delete_cached_user(user.email)

    return {"message": "Email verified successfully"}


@app.post("/auth/request-email")
async def request_email_verification(
    current_user: User = Depends(get_current_user),
):
    """
    Send a new email verification message to the current user.

    :param current_user: Authenticated user.
    :return: Verification email status message.
    """
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
    """
    Return information about the authenticated user.

    :param request: Incoming HTTP request.
    :param current_user: Authenticated user.
    :param _: Rate limiter dependency.
    :return: Current user object.
    """
    return current_user


@app.patch("/users/avatar", response_model=UserResponse)
def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Upload and update the current admin user's avatar.

    Avatar images are uploaded to Cloudinary.

    :param file: Uploaded image file.
    :param current_user: Authenticated admin user.
    :param db: Database session dependency.
    :raises HTTPException: If Cloudinary is not configured or user is not found.
    :return: Updated user object.
    """
    if not os.getenv("CLOUDINARY_NAME"):
        raise HTTPException(
            status_code=500,
            detail="Cloudinary is not configured",
        )

    result = cloudinary.uploader.upload(
        file.file,
        folder="goit-pythonweb-hw-10/avatars",
        public_id=f"user_{current_user.id}",
        overwrite=True,
        resource_type="image",
    )

    db_user = get_user_by_email(db, current_user.email)

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.avatar = result.get("secure_url")

    db.commit()
    db.refresh(db_user)

    from cache import delete_cached_user

    delete_cached_user(db_user.email)

    return db_user


@app.post(
    "/contacts/",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    """
    Create a new contact for the authenticated user.

    :param contact: Contact creation payload.
    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :return: Created contact object.
    """
    return create_contact(db, contact, current_user.id)


@app.get("/contacts/", response_model=list[ContactResponse])
def read_contacts(
    first_name: str | None = Query(None, description="Search by first name"),
    last_name: str | None = Query(None, description="Search by last name"),
    email: str | None = Query(None, description="Search by email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    """
    Return all contacts for the authenticated user.

    Supports filtering by first name, last name, and email.

    :param first_name: Optional first name filter.
    :param last_name: Optional last name filter.
    :param email: Optional email filter.
    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :return: List of contacts.
    """
    return get_contacts(
        db,
        current_user.id,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


@app.get("/contacts/upcoming/birthdays", response_model=list[ContactResponse])
def upcoming_birthdays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    """
    Return contacts with birthdays within the next seven days.

    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :return: List of contacts with upcoming birthdays.
    """
    return get_upcoming_birthdays(db, current_user.id)


@app.get("/contacts/{contact_id}", response_model=ContactResponse)
def read_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    """
    Return a single contact by ID.

    :param contact_id: Contact identifier.
    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :raises HTTPException: If the contact does not exist.
    :return: Contact object.
    """
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
    """
    Update an existing contact.

    :param contact_id: Contact identifier.
    :param contact_data: Updated contact data.
    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :raises HTTPException: If the contact does not exist.
    :return: Updated contact object.
    """
    contact = update_contact(
        db,
        contact_id,
        contact_data,
        current_user.id,
    )

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@app.delete("/contacts/{contact_id}", response_model=ContactResponse)
def delete_existing_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_confirmed_user),
):
    """
    Delete a contact by ID.

    :param contact_id: Contact identifier.
    :param db: Database session dependency.
    :param current_user: Authenticated confirmed user.
    :raises HTTPException: If the contact does not exist.
    :return: Deleted contact object.
    """
    contact = delete_contact(db, contact_id, current_user.id)

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact
