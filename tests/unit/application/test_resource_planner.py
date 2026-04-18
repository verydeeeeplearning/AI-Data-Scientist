"""Resource-aware planning tests for PLAN 17 Phase 6."""

from __future__ import annotations

from ds_agent.application.services.resource_planner import ResourcePlanner
from ds_agent.domain.value_objects.resource_profile import ExecutionStrategy, ResourceProfile


class TestResourcePlanner:
    def test_uses_direct_strategy_for_small_data(self):
        planner = ResourcePlanner()

        plan = planner.plan(
            ResourceProfile(
                data_size_bytes=500_000,
                row_count=20_000,
                column_count=12,
                available_memory_bytes=8_000_000_000,
                available_cpus=8,
            )
        )

        assert plan.strategy == ExecutionStrategy.DIRECT

    def test_uses_sample_first_when_memory_pressure_is_high(self):
        planner = ResourcePlanner()

        plan = planner.plan(
            ResourceProfile(
                data_size_bytes=5_000_000_000,
                row_count=10_000_000,
                column_count=50,
                available_memory_bytes=4_000_000_000,
                available_cpus=8,
            )
        )

        assert plan.strategy == ExecutionStrategy.SAMPLE_FIRST
        assert plan.sample_fraction <= 0.1

    def test_uses_distributed_for_very_large_data(self):
        planner = ResourcePlanner()

        plan = planner.plan(
            ResourceProfile(
                data_size_bytes=50_000_000_000,
                row_count=100_000_000,
                column_count=120,
                available_memory_bytes=16_000_000_000,
                available_cpus=16,
            )
        )

        assert plan.strategy == ExecutionStrategy.DISTRIBUTED
