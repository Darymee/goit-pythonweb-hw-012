"""Redis cache helpers used by authentication dependencies."""

import json
import os
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover - only used when dependency is unavailable
    redis = None

USER_CACHE_TTL = int(os.getenv("USER_CACHE_TTL", "900"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def _client():
    """Create a Redis client or return ``None`` when Redis is unavailable."""
    if redis is None:
        return None
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


redis_client = _client()


def user_cache_key(email: str) -> str:
    """Build a Redis cache key for a user email."""
    return f"user:{email}"


def get_cached_user(email: str) -> dict[str, Any] | None:
    """Return cached public user fields for an email, if present."""
    if redis_client is None:
        return None
    cached = redis_client.get(user_cache_key(email))
    if not cached:
        return None
    return json.loads(cached)


def set_cached_user(user: Any) -> None:
    """Store safe user fields in Redis for authentication reuse."""
    if redis_client is None:
        return
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar": user.avatar,
        "confirmed": user.confirmed,
        "role": user.role,
    }
    redis_client.setex(user_cache_key(user.email), USER_CACHE_TTL, json.dumps(payload))


def delete_cached_user(email: str) -> None:
    """Remove a user from the Redis cache."""
    if redis_client is not None:
        redis_client.delete(user_cache_key(email))
