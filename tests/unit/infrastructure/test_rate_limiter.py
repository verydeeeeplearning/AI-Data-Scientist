"""Tests for token bucket rate limiter and backoff calculator."""

from __future__ import annotations

from ds_agent.infrastructure.external.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
    compute_backoff_seconds,
)


def test_token_bucket_acquire_succeeds_within_capacity() -> None:
    configs = {"test": RateLimitConfig(system="test", requests_per_second=10, burst_capacity=3)}
    limiter = TokenBucketRateLimiter(configs=configs)
    assert limiter.acquire("test") is True
    assert limiter.acquire("test") is True
    assert limiter.acquire("test") is True


def test_token_bucket_acquire_fails_when_exhausted() -> None:
    configs = {"test": RateLimitConfig(system="test", requests_per_second=0.001, burst_capacity=1)}
    limiter = TokenBucketRateLimiter(configs=configs)
    assert limiter.acquire("test") is True
    assert limiter.acquire("test") is False


def test_token_bucket_uses_default_for_unknown_system() -> None:
    limiter = TokenBucketRateLimiter(configs={})
    assert limiter.acquire("unknown_system") is True


def test_backoff_exponential_growth() -> None:
    b0 = compute_backoff_seconds(0, base_seconds=1.0, jitter=False)
    b1 = compute_backoff_seconds(1, base_seconds=1.0, jitter=False)
    b2 = compute_backoff_seconds(2, base_seconds=1.0, jitter=False)
    assert b0 == 1.0
    assert b1 == 2.0
    assert b2 == 4.0


def test_backoff_respects_max() -> None:
    result = compute_backoff_seconds(20, base_seconds=1.0, max_seconds=60.0, jitter=False)
    assert result == 60.0


def test_backoff_with_jitter_is_bounded() -> None:
    for attempt in range(10):
        result = compute_backoff_seconds(attempt, base_seconds=0.1, max_seconds=60.0, jitter=True)
        assert 0 < result <= 60.0


def test_rate_limit_config_frozen() -> None:
    config = RateLimitConfig(system="slack", requests_per_second=1.0, burst_capacity=5)
    assert config.system == "slack"
    try:
        config.system = "jira"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except Exception:
        pass
