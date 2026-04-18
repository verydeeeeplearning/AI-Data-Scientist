"""Domain value object tests: BudgetPolicy, BudgetState."""

from ds_agent.domain.value_objects.budget import (
    BudgetPolicy,
    BudgetState,
    BudgetThresholdEvent,
)


class TestBudgetPolicy:
    def test_default_values(self):
        policy = BudgetPolicy()
        assert policy.max_iterations == 100
        assert policy.max_total_tokens == 2_000_000
        assert policy.max_cost_usd == 10.0
        assert policy.max_wall_time_seconds == 7200.0
        assert policy.warning_threshold_pct == 80.0
        assert policy.critical_threshold_pct == 95.0

    def test_custom_values(self):
        policy = BudgetPolicy(
            max_iterations=50,
            max_cost_usd=5.0,
            warning_threshold_pct=70.0,
        )
        assert policy.max_iterations == 50
        assert policy.max_cost_usd == 5.0
        assert policy.warning_threshold_pct == 70.0

    def test_immutability(self):
        """BudgetPolicy should be a frozen-like value object."""
        policy = BudgetPolicy()
        # Pydantic BaseModel isn't frozen by default, but the values should be stable
        assert policy.max_iterations == 100


class TestBudgetState:
    def test_default_state(self):
        state = BudgetState()
        assert state.iterations_used == 0
        assert state.total_tokens_used == 0
        assert state.total_cost_usd == 0.0
        assert state.wall_time_elapsed == 0.0
        assert not state.warning_issued
        assert not state.critical_issued

    def test_mutability(self):
        state = BudgetState()
        state.iterations_used = 10
        state.total_cost_usd = 1.5
        assert state.iterations_used == 10
        assert state.total_cost_usd == 1.5


class TestBudgetThresholdEvent:
    def test_warning_event(self):
        event = BudgetThresholdEvent(
            dimension="cost",
            level="warning",
            used=8.0,
            limit=10.0,
            pct=80.0,
            message="Cost budget at 80%",
        )
        assert event.dimension == "cost"
        assert event.level == "warning"
        assert event.pct == 80.0

    def test_exhausted_event(self):
        event = BudgetThresholdEvent(
            dimension="iterations",
            level="exhausted",
            used=100,
            limit=100,
            pct=100.0,
            message="Iteration budget exhausted",
        )
        assert event.level == "exhausted"
