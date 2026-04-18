"""Domain value objects for resource-aware execution planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class ExecutionStrategy(StrEnum):
    """Execution strategies for different data scales."""

    DIRECT = "direct"
    SAMPLE_FIRST = "sample_first"
    CHUNKED = "chunked"
    DISTRIBUTED = "distributed"


@dataclass(frozen=True)
class ResourceProfile:
    """Profile of available resources and dataset size."""

    data_size_bytes: int
    row_count: int
    column_count: int
    available_memory_bytes: int
    available_cpus: int

    @property
    def estimated_memory_bytes(self) -> int:
        """Tabular processing typically expands data in memory."""
        return int(self.data_size_bytes * 3)


@dataclass(frozen=True)
class ResourcePlan:
    """Execution plan derived from a resource profile."""

    strategy: ExecutionStrategy
    rationale: str
    sample_fraction: float | None = None
    chunk_size_rows: int | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["strategy"] = self.strategy.value
        return payload
