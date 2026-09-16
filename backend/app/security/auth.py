"""
Admin authentication abstraction + rate limiting.

Auth: a single shared ADMIN_TOKEN checked via the X-Admin-Token header is
intentionally simple -- it is an abstraction point, not a real identity
system (see security/jwt_auth.py for the role-based JWT layer added
alongside it). Enforcement is off by default (REQUIRE_ADMIN_TOKEN=false)
so Judge Mode / local demo needs no setup; the frontend sends the header
regardless so flipping the flag to "true" works immediately without a
frontend change.

Rate limiting: Redis INCR+EXPIRE per client IP when config.REDIS_URL is
set (works correctly across multiple backend replicas, since the counter
lives in shared Redis rather than one process's memory) -- falls back to
an in-memory sliding window when Redis isn't configured or isn't
reachable, so rate limiting never becomes a hard dependency on an
optional piece of infrastructure.
"""
import time
from collections import defaultdict, deque
from fastapi import Header, HTTPException, Request
from .. import config

_redis_client = None
_redis_unavailable = False


def _get_redis():
    global _redis_client, _redis_unavailable
    if not config.REDIS_URL or _redis_unavailable:
        return None
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(config.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
    return _redis_client


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    if not config.REQUIRE_ADMIN_TOKEN:
        return True
    if x_admin_token != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
    return True


_request_log: dict[str, deque] = defaultdict(deque)
_WINDOW_SECONDS = 60


def _check_rate_limit_redis(client: str):
    """Returns True if allowed, False if exceeded, None if Redis isn't
    configured/reachable (caller falls back to the in-memory limiter)."""
    global _redis_unavailable
    r = _get_redis()
    if r is None:
        return None
    try:
        key = f"indra:ratelimit:{client}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, _WINDOW_SECONDS)
        return count <= config.RATE_LIMIT_PER_MINUTE
    except Exception:
        _redis_unavailable = True  # stop retrying Redis for the rest of this process's life
        return None


def check_rate_limit(request: Request):
    client = request.client.host if request.client else "unknown"

    redis_result = _check_rate_limit_redis(client)
    if redis_result is not None:
        if not redis_result:
            raise HTTPException(status_code=429, detail="Rate limit exceeded, slow down")
        return True

    now = time.monotonic()
    log = _request_log[client]
    while log and now - log[0] > _WINDOW_SECONDS:
        log.popleft()
    if len(log) >= config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, slow down")
    log.append(now)
    return True
