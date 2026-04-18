"""Per-system token bucket rate limiter for integration dispatch."""

from __future__ import annotations

import random
import time

from pydantic import BaseModel, ConfigDict, Field


class RateLimitConfig(BaseModel):
    """Rate limit settings for one integration system."""

    model_config = ConfigDict(frozen=True)

    system: str = Field(min_length=1)
    requests_per_second: float = Field(default=1.0, gt=0)
    burst_capacity: int = Field(default=5, ge=1)


_DEFAULT_CONFIGS: dict[str, RateLimitConfig] = {
    "slack": RateLimitConfig(system="slack", requests_per_second=1.0, burst_capacity=5),
    "jira": RateLimitConfig(system="jira", requests_per_second=5.0, burst_capacity=10),
    "confluence": RateLimitConfig(
        system="confluence", requests_per_second=5.0, burst_capacity=10,
    ),
    "notion": RateLimitConfig(system="notion", requests_per_second=3.0, burst_capacity=8),
    "git": RateLimitConfig(system="git", requests_per_second=5.0, burst_capacity=10),
}


class _Bucket:
    """In-memory token bucket for a single system."""

    def __init__(self, config: RateLimitConfig) -> None:
        self.tokens = float(config.burst_capacity)
        self.capacity = config.burst_capacity
        self.refill_rate = config.requests_per_second
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def acquire(self) -> bool:
        """Try to consume one token. Returns True if acquired."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class TokenBucketRateLimiter:
    """Per-system in-memory rate limiter for integration connectors."""

    def __init__(
        self,
        configs: dict[str, RateLimitConfig] | None = None,
    ) -> None:
        self._configs = configs or _DEFAULT_CONFIGS
        self._buckets: dict[str, _Bucket] = {}

    def acquire(self, system: str) -> bool:
        """Try to acquire a dispatch token for the given system."""
        if system not in self._buckets:
            config = self._configs.get(
                system,
                RateLimitConfig(system=system),
            )
            self._buckets[system] = _Bucket(config)
        return self._buckets[system].acquire()


def compute_backoff_seconds(
    attempt: int,
    *,
    base_seconds: float = 0.1,
    max_seconds: float = 60.0,
    jitter: bool = True,
) -> float:
    """Exponential backoff: min(max, base * 2^attempt) + optional jitter."""
    delay: float = min(max_seconds, base_seconds * (2 ** attempt))
    if jitter:
        delay *= 0.5 + random.random() * 0.5
    return delay
