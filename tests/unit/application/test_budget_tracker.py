"""IterationBudget tracker tests."""

from ds_agent.agent.budget_tracker import IterationBudget
from ds_agent.domain.entities.messages import Usage
from ds_agent.domain.value_objects.budget import BudgetPolicy


class TestIterationBudget:
    def test_initial_state(self):
        budget = IterationBudget()
        assert budget.remaining_iterations > 0
        assert budget.remaining_cost > 0
        assert not budget.is_exhausted

    def test_consume_iteration(self):
        budget = IterationBudget(policy=BudgetPolicy(max_iterations=10))
        usage = Usage(input_tokens=1000, output_tokens=500)
        budget.consume(usage, model="claude-sonnet-4")

        assert budget.state.iterations_used == 1
        assert budget.state.total_tokens_used == 1500
        assert budget.state.total_cost_usd > 0

    def test_exhausted_by_iterations(self):
        budget = IterationBudget(policy=BudgetPolicy(max_iterations=2))
        usage = Usage(input_tokens=100, output_tokens=50)

        budget.consume(usage, model="test")
        assert not budget.is_exhausted
        budget.consume(usage, model="test")
        assert budget.is_exhausted

    def test_exhausted_by_cost(self):
        budget = IterationBudget(policy=BudgetPolicy(max_cost_usd=0.001))
        # Large usage to exceed tiny budget
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        budget.consume(usage, model="claude-sonnet-4")

        assert budget.is_exhausted

    def test_remaining_iterations(self):
        budget = IterationBudget(policy=BudgetPolicy(max_iterations=10))
        usage = Usage(input_tokens=100, output_tokens=50)

        budget.consume(usage, model="test")
        assert budget.remaining_iterations == 9

    def test_remaining_cost(self):
        policy = BudgetPolicy(max_cost_usd=10.0)
        budget = IterationBudget(policy=policy)

        assert budget.remaining_cost == 10.0
        usage = Usage(input_tokens=100, output_tokens=50)
        budget.consume(usage, model="test")
        assert budget.remaining_cost < 10.0

    def test_warning_threshold(self):
        events = []
        budget = IterationBudget(policy=BudgetPolicy(max_iterations=10, warning_threshold_pct=50.0))

        for _ in range(6):
            usage = Usage(input_tokens=100, output_tokens=50)
            evts = budget.consume(usage, model="test")
            events.extend(evts)

        warning_events = [e for e in events if e.level == "warning"]
        assert len(warning_events) >= 1

    def test_critical_threshold(self):
        events = []
        budget = IterationBudget(
            policy=BudgetPolicy(max_iterations=10, critical_threshold_pct=90.0)
        )

        for _ in range(10):
            usage = Usage(input_tokens=100, output_tokens=50)
            evts = budget.consume(usage, model="test")
            events.extend(evts)

        critical_events = [e for e in events if e.level == "critical"]
        assert len(critical_events) >= 1

    def test_get_summary(self):
        budget = IterationBudget(policy=BudgetPolicy(max_iterations=100))
        usage = Usage(input_tokens=1000, output_tokens=500)
        budget.consume(usage, model="claude-sonnet-4")
        budget.consume(usage, model="gpt-4.1")

        summary = budget.get_summary()
        assert summary["iterations_used"] == 2
        assert summary["total_cost_usd"] > 0
        assert "cost_by_model" in summary
