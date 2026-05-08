import pytest
import auth


def test_get_current_user_from_cache(monkeypatch):
    cached_user = {
        "id": 1,
        "email": "test@example.com",
        "username": "testuser",
        "avatar": None,
        "role": "user",
        "confirmed": True,
    }

    token = auth.create_access_token({"sub": cached_user["email"]})

    def fake_get_cached_user(email):
        assert email == cached_user["email"]
        return cached_user

    def fake_set_cached_user(user):
        raise AssertionError("set_cached_user should not be called on cache hit")

    monkeypatch.setattr(auth, "get_cached_user", fake_get_cached_user)
    monkeypatch.setattr(auth, "set_cached_user", fake_set_cached_user)

    class FakeDB:
        def query(self, *args, **kwargs):
            raise AssertionError("Database should not be called on cache hit")

    user = auth.get_current_user(token=token, db=FakeDB())

    assert user.email == cached_user["email"]
    assert user.username == cached_user["username"]
    assert user.role == cached_user["role"]
    assert user.confirmed is True
