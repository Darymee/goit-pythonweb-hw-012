"""Database repository functions for users and contacts."""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth import get_password_hash
from cache import delete_cached_user
from models import Contact, User
from schemas import ContactCreate, ContactUpdate


def get_user_by_email(db: Session, email: str):
    """
    Return a user by email.

    :param db: Database session.
    :param email: User email address.
    :return: User object or None if not found.
    """
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    role: str = "user",
):
    """
    Create a new user with a hashed password.

    :param db: Database session.
    :param username: User name.
    :param email: User email address.
    :param password: Plain-text password.
    :param role: User role.
    :return: Created user object.
    """
    user = User(
        username=username,
        email=email,
        password=get_password_hash(password),
        role=role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def update_user_refresh_token(db: Session, user: User, refresh_token: str | None):
    """Store or clear a user refresh token and invalidate cached user data."""
    user.refresh_token = refresh_token
    db.commit()
    db.refresh(user)
    delete_cached_user(user.email)
    return user


def update_user_password(db: Session, user: User, password: str):
    """
    Update a user's password and clear cached authentication data.

    :param db: Database session.
    :param user: User object.
    :param password: New plain-text password.
    :return: Updated user object.
    """
    user.password = get_password_hash(password)
    user.refresh_token = None

    db.commit()
    db.refresh(user)

    delete_cached_user(user.email)

    return user


def get_contacts(
    db: Session,
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
):
    """
    Return contacts owned by a specific user.

    Supports optional filtering by first name, last name, or email.

    :param db: Database session.
    :param user_id: Owner user ID.
    :param first_name: Optional first name filter.
    :param last_name: Optional last name filter.
    :param email: Optional email filter.
    :return: List of contacts.
    """
    query = db.query(Contact).filter(Contact.user_id == user_id)

    if first_name:
        query = query.filter(Contact.first_name.ilike(f"%{first_name}%"))

    if last_name:
        query = query.filter(Contact.last_name.ilike(f"%{last_name}%"))

    if email:
        query = query.filter(Contact.email.ilike(f"%{email}%"))

    return query.all()


def get_contact(db: Session, contact_id: int, user_id: int):
    """
    Return a single contact by ID.

    :param db: Database session.
    :param contact_id: Contact identifier.
    :param user_id: Owner user ID.
    :return: Contact object or None.
    """
    return (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.user_id == user_id)
        .first()
    )


def create_contact(
    db: Session,
    contact: ContactCreate,
    user_id: int,
):
    """
    Create a new contact for a user.

    Prevents duplicate email addresses for the same user.

    :param db: Database session.
    :param contact: Contact creation payload.
    :param user_id: Owner user ID.
    :raises HTTPException: If email already exists.
    :return: Created contact object.
    """
    existing = (
        db.query(Contact)
        .filter(
            Contact.email == contact.email,
            Contact.user_id == user_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    db_contact = Contact(**contact.model_dump(), user_id=user_id)

    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)

    return db_contact


def update_contact(
    db: Session,
    contact_id: int,
    contact_data: ContactUpdate,
    user_id: int,
):
    """
    Update an existing contact.

    :param db: Database session.
    :param contact_id: Contact identifier.
    :param contact_data: Updated contact data.
    :param user_id: Owner user ID.
    :raises HTTPException: If email already exists.
    :return: Updated contact object or None.
    """
    db_contact = get_contact(db, contact_id, user_id)

    if not db_contact:
        return None

    update_data = contact_data.model_dump(exclude_unset=True)

    if "email" in update_data:
        existing = (
            db.query(Contact)
            .filter(
                Contact.email == update_data["email"],
                Contact.id != contact_id,
                Contact.user_id == user_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")

    for key, value in update_data.items():
        setattr(db_contact, key, value)

    db.commit()
    db.refresh(db_contact)

    return db_contact


def delete_contact(
    db: Session,
    contact_id: int,
    user_id: int,
):
    """
    Delete a contact by ID.

    :param db: Database session.
    :param contact_id: Contact identifier.
    :param user_id: Owner user ID.
    :return: Deleted contact object or None.
    """
    db_contact = get_contact(db, contact_id, user_id)

    if not db_contact:
        return None

    db.delete(db_contact)
    db.commit()

    return db_contact


def safe_birthday_for_year(birthday: date, year: int) -> date:
    """
    Return a birthday date adjusted for a specific year.

    Leap-day birthdays are converted to February 28 in non-leap years.

    :param birthday: Original birthday date.
    :param year: Target year.
    :return: Safe birthday date.
    """
    try:
        return birthday.replace(year=year)

    except ValueError:
        return date(year, 2, 28)


def get_upcoming_birthdays(db: Session, user_id: int):
    """
    Return contacts with birthdays within the next seven days.

    :param db: Database session.
    :param user_id: Owner user ID.
    :return: List of contacts with upcoming birthdays.
    """
    contacts = db.query(Contact).filter(Contact.user_id == user_id).all()

    today = date.today()
    next_week = today + timedelta(days=7)

    result = []

    for contact in contacts:
        birthday_this_year = safe_birthday_for_year(
            contact.birthday,
            today.year,
        )

        if birthday_this_year < today:
            birthday_this_year = safe_birthday_for_year(
                contact.birthday,
                today.year + 1,
            )

        if today <= birthday_this_year <= next_week:
            result.append(contact)

    return result
