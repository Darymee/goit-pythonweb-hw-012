from auth import create_email_token, create_password_reset_token
from crud import create_user


def register_and_login(
    client, db_session, confirmed=True, role="user", email="user@example.com"
):
    user = create_user(db_session, "user", email, "secret123", role=role)
    user.confirmed = confirmed
    db_session.commit()
    response = client.post(
        "/auth/login", data={"username": email, "password": "secret123"}
    )
    assert response.status_code == 200
    body = response.json()
    token = body["access_token"]
    assert body["refresh_token"]
    return user, {"Authorization": f"Bearer {token}"}


def test_register_login_and_me(client):
    response = client.post(
        "/auth/register",
        json={"username": "ann", "email": "ann@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"

    bad = client.post(
        "/auth/login", data={"username": "ann@example.com", "password": "bad"}
    )
    assert bad.status_code == 401

    ok = client.post(
        "/auth/login", data={"username": "ann@example.com", "password": "secret123"}
    )
    body = ok.json()
    token = body["access_token"]
    assert body["refresh_token"]
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ann@example.com"


def test_verify_email_and_request_email(client, db_session):
    user = create_user(db_session, "ann", "ann@example.com", "secret123")
    token = create_email_token(user.email)
    response = client.get(f"/auth/verify/{token}")
    assert response.status_code == 200
    assert response.json()["message"] == "Email verified successfully"

    login = client.post(
        "/auth/login", data={"username": user.email, "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/auth/request-email", headers=headers)
    assert response.json()["message"] == "Email is already verified"


def test_password_reset(client, db_session):
    user = create_user(db_session, "ann", "ann@example.com", "secret123")
    response = client.post("/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 200

    token = create_password_reset_token(user.email)
    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "changed123"}
    )
    assert response.status_code == 200

    login = client.post(
        "/auth/login", data={"username": user.email, "password": "changed123"}
    )
    assert login.status_code == 200


def test_contacts_require_confirmation_and_crud(client, db_session):
    _, headers = register_and_login(client, db_session, confirmed=False)
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone_number": "123456789",
        "birthday": "2000-01-01",
        "additional_data": "note",
    }
    assert client.post("/contacts/", json=payload, headers=headers).status_code == 403

    _, headers = register_and_login(
        client, db_session, confirmed=True, email="ok@example.com"
    )
    created = client.post("/contacts/", json=payload, headers=headers)
    assert created.status_code == 201
    contact_id = created.json()["id"]

    assert client.get("/contacts/", headers=headers).status_code == 200
    assert (
        client.get(f"/contacts/{contact_id}", headers=headers).json()["email"]
        == "john@example.com"
    )
    assert (
        client.put(
            f"/contacts/{contact_id}", json={"first_name": "Jack"}, headers=headers
        ).json()["first_name"]
        == "Jack"
    )
    assert (
        client.get("/contacts/upcoming/birthdays", headers=headers).status_code == 200
    )
    assert client.delete(f"/contacts/{contact_id}", headers=headers).status_code == 200
    assert client.get(f"/contacts/{contact_id}", headers=headers).status_code == 404


def test_admin_only_avatar(client, db_session):
    _, user_headers = register_and_login(
        client, db_session, role="user", email="plain@example.com"
    )
    files = {"file": ("avatar.png", b"image", "image/png")}
    assert (
        client.patch("/users/avatar", files=files, headers=user_headers).status_code
        == 403
    )

    _, admin_headers = register_and_login(
        client, db_session, role="admin", email="admin@example.com"
    )
    response = client.patch("/users/avatar", files=files, headers=admin_headers)
    assert response.status_code != 403


def test_reset_password_invalid_token(client):
    response = client.post(
        "/auth/reset-password",
        json={"token": "invalid-token", "new_password": "newpassword123"},
    )

    assert response.status_code == 400


def test_reset_password_token_for_missing_user(client):
    from auth import create_password_reset_token

    token = create_password_reset_token("missing@example.com")

    response = client.post(
        "/auth/reset-password",
        json={
            "token": token,
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == 404


def test_forgot_password_user_not_found(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200


def test_refresh_and_logout(client, db_session):
    user = create_user(db_session, "ann", "refresh@example.com", "secret123")
    user.confirmed = True
    db_session.commit()

    login = client.post(
        "/auth/login", data={"username": user.email, "password": "secret123"}
    )
    assert login.status_code == 200
    tokens = login.json()

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    stale = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert stale.status_code == 401

    headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    after_logout = client.post(
        "/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]}
    )
    assert after_logout.status_code == 401


def test_access_endpoint_rejects_refresh_token(client, db_session):
    user = create_user(db_session, "ann", "scope@example.com", "secret123")
    user.confirmed = True
    db_session.commit()

    login = client.post(
        "/auth/login", data={"username": user.email, "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['refresh_token']}"}

    response = client.get("/users/me", headers=headers)
    assert response.status_code == 401
