"""Redis connection pool for caching, rate limiting, and stock locks."""

from redis.asyncio import ConnectionPool, Redis

from app.config import settings

pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """Dependency — returns a Redis client from the shared pool."""
    return Redis(connection_pool=pool)
