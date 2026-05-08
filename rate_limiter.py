import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

WINDOW_SECONDS = 60
MAX_REQUESTS = 5
_requests: dict[str, deque[float]] = defaultdict(deque)


def limit_me_route(request: Request) -> None:
    """
    Limit the number of requests to the `/me` endpoint.

    This function implements a simple in-memory rate limiter based on
    the client's authorization header or IP address. If the number of
    requests exceeds the allowed limit within the configured time window,
    an HTTP 429 exception is raised.

    Args:
        request (Request): Incoming FastAPI request object.

    Raises:
        HTTPException: If the request limit is exceeded.
    """

    authorization = request.headers.get("authorization", "")
    key = authorization or request.client.host if request.client else "anonymous"
    now = time.time()
    bucket = _requests[key]

    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests to /me. Try again later.",
        )

    bucket.append(now)
