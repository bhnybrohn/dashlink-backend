"""Rate limiter — Redis-backed sliding window counter."""

from fastapi import Request
from redis.asyncio import Redis

from app.core.exceptions import RateLimitError


class RateLimiter:
    """Sliding window rate limiter backed by Redis.

    Usage as a FastAPI dependency:
        rate_limit = RateLimiter(max_requests=5, window_seconds=900)  # 5 per 15 min
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def check(self, redis: Redis, key: str) -> None:  # type: ignore[type-arg]
        """Check rate limit. Raises RateLimitError if exceeded."""
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window_seconds)
        results = await pipe.execute()

        current_count = results[0]
        if current_count > self.max_requests:
            raise RateLimitError()

    def get_key(self, request: Request, prefix: str = "rl") -> str:
        """Generate a rate limit key from request IP."""
        client_ip = request.client.host if request.client else "unknown"
        return f"{prefix}:{client_ip}:{request.url.path}"


# Pre-configured rate limiters
auth_rate_limiter = RateLimiter(max_requests=5, window_seconds=120)       # 5 per 15 min
checkout_rate_limiter = RateLimiter(max_requests=5, window_seconds=120)   # 5 per 10 min
global_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)    # 100 per min
