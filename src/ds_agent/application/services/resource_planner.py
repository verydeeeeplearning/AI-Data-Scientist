"""Resource-aware planning for PLAN 17 Phase 6."""

from __future__ import annotations

from ds_agent.domain.value_objects.resource_profile import (
    ExecutionStrategy,
    ResourcePlan,
    ResourceProfile,
)


class ResourcePlanner:
    """Pick an execution strategy based on dataset scale and memory pressure."""

    def plan(self, profile: ResourceProfile) -> ResourcePlan:
        warnings: list[str] = []

        if profile.data_size_bytes > 10_000_000_000 or profile.row_count > 50_000_000:
            return ResourcePlan(
                strategy=ExecutionStrategy.DISTRIBUTED,
                rationale="Dataset is large enough to warrant distributed execution.",
                warnings=warnings,
            )

        memory_pressure = profile.estimated_memory_bytes > int(profile.available_memory_bytes * 0.8)
        if memory_pressure:
            warnings.append("Estimated in-memory footprint exceeds available memory headroom.")
            return ResourcePlan(
                strategy=ExecutionStrategy.SAMPLE_FIRST,
                rationale="Prototype on a representative sample before scaling up.",
                sample_fraction=self._sample_fraction(profile.row_count),
                warnings=warnings,
            )

        if profile.data_size_bytes > 1_000_000_000 or profile.row_count > 5_000_000:
            return ResourcePlan(
                strategy=ExecutionStrategy.CHUNKED,
                rationale="Process in chunks to control memory use.",
                chunk_size_rows=max(
                    50_000,
                    min(500_000, profile.row_count // max(profile.available_cpus, 1)),
                ),
                warnings=warnings,
            )

        if profile.data_size_bytes > 100_000_000 or profile.row_count > 500_000:
            return ResourcePlan(
                strategy=ExecutionStrategy.SAMPLE_FIRST,
                rationale="Use a sample-first workflow before full-data validation.",
                sample_fraction=self._sample_fraction(profile.row_count),
                warnings=warnings,
            )

        return ResourcePlan(
            strategy=ExecutionStrategy.DIRECT,
            rationale="Dataset is small enough for direct pandas processing.",
            warnings=warnings,
        )

    @staticmethod
    def _sample_fraction(row_count: int) -> float:
        if row_count >= 10_000_000:
            return 0.01
        if row_count >= 1_000_000:
            return 0.05
        return 0.10
