from datetime import date, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Contact, User
from schemas import ContactCreate, ContactUpdate
from auth import get_password_hash


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, username: str, email: str, password: str):
    user = User(username=username, email=email, password=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_contacts(db: Session, user_id: int, first_name: str | None = None, last_name: str | None = None, email: str | None = None):
    query = db.query(Contact).filter(Contact.user_id == user_id)

    if first_name:
        query = query.filter(Contact.first_name.ilike(f"%{first_name}%"))
    if last_name:
        query = query.filter(Contact.last_name.ilike(f"%{last_name}%"))
    if email:
        query = query.filter(Contact.email.ilike(f"%{email}%"))

    return query.all()


def get_contact(db: Session, contact_id: int, user_id: int):
    return db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == user_id).first()


def create_contact(db: Session, contact: ContactCreate, user_id: int):
    existing = db.query(Contact).filter(Contact.email == contact.email, Contact.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    db_contact = Contact(**contact.model_dump(), user_id=user_id)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


def update_contact(db: Session, contact_id: int, contact_data: ContactUpdate, user_id: int):
    db_contact = get_contact(db, contact_id, user_id)
    if not db_contact:
        return None

    update_data = contact_data.model_dump(exclude_unset=True)

    if "email" in update_data:
        existing = (
            db.query(Contact)
            .filter(Contact.email == update_data["email"], Contact.id != contact_id, Contact.user_id == user_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")

    for key, value in update_data.items():
        setattr(db_contact, key, value)

    db.commit()
    db.refresh(db_contact)
    return db_contact


def delete_contact(db: Session, contact_id: int, user_id: int):
    db_contact = get_contact(db, contact_id, user_id)
    if not db_contact:
        return None

    db.delete(db_contact)
    db.commit()
    return db_contact


def safe_birthday_for_year(birthday: date, year: int) -> date:
    try:
        return birthday.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def get_upcoming_birthdays(db: Session, user_id: int):
    contacts = db.query(Contact).filter(Contact.user_id == user_id).all()
    today = date.today()
    next_week = today + timedelta(days=7)
    result = []

    for contact in contacts:
        birthday_this_year = safe_birthday_for_year(contact.birthday, today.year)
        if birthday_this_year < today:
            birthday_this_year = safe_birthday_for_year(contact.birthday, today.year + 1)
        if today <= birthday_this_year <= next_week:
            result.append(contact)

    return result
