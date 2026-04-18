"""Infrastructure adapters that enforce sandbox policy at runtime."""

from ds_agent.infrastructure.sandbox.preamble import (
    VIOLATION_PREFIX,
    VIOLATION_SUFFIX,
    build_preamble,
    parse_violations,
)

__all__ = [
    "VIOLATION_PREFIX",
    "VIOLATION_SUFFIX",
    "build_preamble",
    "parse_violations",
]
