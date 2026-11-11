"""Rate limiter supporting Redis with automatic in-memory sliding window fallback."""

import time
from collections import defaultdict
from app.core.config import settings

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class RateLimiter:
    """Sliding-window rate limiter per application."""

    def __init__(self):
        self._redis_client = None
        self._memory_store: dict[str, list[float]] = defaultdict(list)

    async def _get_redis(self):
        if settings.REDIS_ENABLED and settings.REDIS_URL and aioredis:
            if self._redis_client is None:
                try:
                    self._redis_client = aioredis.from_url(
                        settings.REDIS_URL,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                except Exception:
                    self._redis_client = None
            return self._redis_client
        return None

    async def check_rate_limit(
        self,
        identifier: str,
        limit_per_minute: int,
    ) -> tuple[bool, int]:
        """Checks if the request is within rate limit.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        if limit_per_minute <= 0:
            return True, 0

        now = time.time()
        window_size = 60.0  # 1 minute sliding window

        redis = await self._get_redis()
        if redis:
            try:
                key = f"ratelimit:{identifier}"
                pipeline = redis.pipeline()
                pipeline.zremrangebyscore(key, 0, now - window_size)
                pipeline.zcard(key)
                pipeline.zadd(key, {str(now): now})
                pipeline.expire(key, int(window_size) + 5)
                _, count, _, _ = await pipeline.execute()

                if count >= limit_per_minute:
                    # Fetch oldest timestamp in current window to calculate retry-after
                    oldest = await redis.zrange(key, 0, 0, withscores=True)
                    retry_after = int(window_size - (now - oldest[0][1])) if oldest else 60
                    return False, max(1, retry_after)
                return True, 0
            except Exception:
                # Fallback to in-memory on Redis error
                pass

        # In-memory sliding window implementation
        timestamps = self._memory_store[identifier]
        threshold = now - window_size
        # Purge timestamps outside the window
        self._memory_store[identifier] = [ts for ts in timestamps if ts > threshold]

        if len(self._memory_store[identifier]) >= limit_per_minute:
            oldest = self._memory_store[identifier][0]
            retry_after = int(window_size - (now - oldest))
            return False, max(1, retry_after)

        self._memory_store[identifier].append(now)
        return True, 0

    def reset_in_memory(self, identifier: str | None = None) -> None:
        """Helper for testing to reset memory counters."""
        if identifier:
            self._memory_store.pop(identifier, None)
        else:
            self._memory_store.clear()


rate_limiter = RateLimiter()
