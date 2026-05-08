from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from crud import (
    create_contact,
    create_user,
    delete_contact,
    get_contact,
    get_contacts,
    get_upcoming_birthdays,
    safe_birthday_for_year,
    update_contact,
    update_user_password,
)
from schemas import ContactCreate, ContactUpdate
from auth import verify_password


def contact_payload(email="john@example.com", birthday=None):
    return ContactCreate(
        first_name="John",
        last_name="Doe",
        email=email,
        phone_number="123456789",
        birthday=birthday or date.today(),
        additional_data="friend",
    )


def test_create_user_and_password_update(db_session):
    user = create_user(db_session, "john", "john@example.com", "secret123")
    assert user.id
    assert verify_password("secret123", user.password)

    update_user_password(db_session, user, "newsecret")
    assert verify_password("newsecret", user.password)


def test_contact_crud_and_duplicate_email(db_session):
    user = create_user(db_session, "john", "john@example.com", "secret123")
    contact = create_contact(db_session, contact_payload("a@example.com"), user.id)
    assert get_contact(db_session, contact.id, user.id).email == "a@example.com"
    assert len(get_contacts(db_session, user.id, first_name="jo")) == 1

    with pytest.raises(HTTPException):
        create_contact(db_session, contact_payload("a@example.com"), user.id)

    updated = update_contact(db_session, contact.id, ContactUpdate(first_name="Jane"), user.id)
    assert updated.first_name == "Jane"

    deleted = delete_contact(db_session, contact.id, user.id)
    assert deleted.email == "a@example.com"
    assert get_contact(db_session, contact.id, user.id) is None


def test_update_contact_missing_and_duplicate(db_session):
    user = create_user(db_session, "john", "john@example.com", "secret123")
    first = create_contact(db_session, contact_payload("a@example.com"), user.id)
    create_contact(db_session, contact_payload("b@example.com"), user.id)

    assert update_contact(db_session, 999, ContactUpdate(first_name="Jane"), user.id) is None
    with pytest.raises(HTTPException):
        update_contact(db_session, first.id, ContactUpdate(email="b@example.com"), user.id)


def test_upcoming_birthdays_and_leap_day(db_session):
    user = create_user(db_session, "john", "john@example.com", "secret123")
    create_contact(db_session, contact_payload("soon@example.com", date.today() + timedelta(days=3)), user.id)
    create_contact(db_session, contact_payload("later@example.com", date.today() + timedelta(days=20)), user.id)

    birthdays = get_upcoming_birthdays(db_session, user.id)
    assert [c.email for c in birthdays] == ["soon@example.com"]
    assert safe_birthday_for_year(date(2020, 2, 29), 2023) == date(2023, 2, 28)
