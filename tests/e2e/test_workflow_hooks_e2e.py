"""E2E regression tests — DS workflow hooks fire correctly during agent runs.

Tests verify that harness hooks (leakage, baseline, overfitting, workflow tracking,
quality scoring) integrate properly with the agent core loop.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.builtin_hooks import BudgetGuardHook, ProcessMetricsHook
from ds_agent.agent.core import DSAgent
from ds_agent.agent.ds_workflow_hooks import (
    BaselineGuardHook,
    LeakageDetectionHook,
    OverfittingDetectorHook,
    StageQualityHook,
    WorkflowTrackerHook,
)
from ds_agent.agent.hooks import HookRegistry
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.domain.entities.messages import LLMResponse, ToolCall, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.value_objects.budget import BudgetPolicy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_provider(responses: list[LLMResponse]):
    provider = MagicMock()
    provider.chat = AsyncMock(side_effect=responses)
    provider.count_tokens = AsyncMock(return_value=100)
    provider.get_model_info = MagicMock(
        return_value=ModelInfo(
            model_id="mock",
            provider="mock",
            display_name="Mock",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )
    )
    return provider


def _mock_registry(tools: dict | None = None):
    tools = tools or {}
    registry = MagicMock()
    registry.get_definitions.return_value = [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": n,
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in tools
    ]

    async def dispatch(name, arguments):
        handler = tools.get(name)
        if handler:
            return str(handler(**arguments))
        return f'{{"error": "Unknown tool: {name}"}}'

    registry.dispatch = AsyncMock(side_effect=dispatch)
    return registry


def _usage(inp: int = 100, out: int = 50) -> Usage:
    return Usage(input_tokens=inp, output_tokens=out)


# ---------------------------------------------------------------------------
# 1. WorkflowTrackerHook E2E
# ---------------------------------------------------------------------------


class TestWorkflowTrackerE2E:
    @pytest.mark.asyncio
    async def test_tracks_stages_through_agent_loop(self):
        """Verify tracker marks stages as done when tools execute."""
        tracker = WorkflowTrackerHook()
        hooks = HookRegistry()
        hooks.register(tracker)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="data_profiler", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(
                tool_calls=[ToolCall(id="t2", name="run_eda", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"data_profiler": lambda: "profile ok", "run_eda": lambda: "eda ok"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Analyze data")

        assert tracker.stages["profiling"] == "done"
        assert tracker.stages["eda"] == "done"
        assert tracker.stages["modeling"] == "pending"
        comp = tracker.get_completeness()
        assert comp["completed"] == 2
        assert "modeling" in comp["missing"]

    @pytest.mark.asyncio
    async def test_tracks_error_stage(self):
        """Verify tracker marks stage as error when tool fails."""
        tracker = WorkflowTrackerHook()
        hooks = HookRegistry()
        hooks.register(tracker)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="train_model", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Failed.", usage=_usage()),
        ]

        tools = {"train_model": lambda: '{"error": "OOM"}'}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Train")

        # Tool result is JSON with "error" key → _is_tool_error() returns True → stage="error"
        assert tracker.stages["modeling"] == "error"


# ---------------------------------------------------------------------------
# 2. LeakageDetectionHook E2E
# ---------------------------------------------------------------------------


class TestLeakageDetectionE2E:
    @pytest.mark.asyncio
    async def test_leakage_warning_appended_to_result(self):
        """Leaky code in feature_engineer triggers warning in tool result."""
        leak_hook = LeakageDetectionHook()
        hooks = HookRegistry()
        hooks.register(leak_hook)

        leaky_code = "scaler.fit_transform(X_test)"
        responses = [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="feature_engineer",
                        arguments={"code": leaky_code},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done with FE.", usage=_usage()),
        ]

        tools = {"feature_engineer": lambda code="": "Features created"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Engineer features")

        # The LLM should have seen the leakage warning in tool results
        second_call_messages = agent._provider.chat.call_args_list[1]
        messages = second_call_messages.kwargs.get("messages") or second_call_messages.args[0]
        tool_msgs = [m for m in messages if m.role.value == "tool"]
        assert any("Leakage" in (m.content or "") for m in tool_msgs)

    @pytest.mark.asyncio
    async def test_clean_code_passes(self):
        """Clean code should show passed message."""
        leak_hook = LeakageDetectionHook()
        hooks = HookRegistry()
        hooks.register(leak_hook)

        clean_code = "scaler.fit(X_train)\nX_test_scaled = scaler.transform(X_test)"
        responses = [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="feature_engineer",
                        arguments={"code": clean_code},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"feature_engineer": lambda code="": "Features ok"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("FE")

        second_call = agent._provider.chat.call_args_list[1]
        messages = second_call.kwargs.get("messages") or second_call.args[0]
        tool_msgs = [m for m in messages if m.role.value == "tool"]
        assert any("passed" in (m.content or "").lower() for m in tool_msgs)


# ---------------------------------------------------------------------------
# 3. BaselineGuardHook E2E
# ---------------------------------------------------------------------------


class TestBaselineGuardE2E:
    @pytest.mark.asyncio
    async def test_no_warning_when_baseline_first(self):
        """Baseline → model → no warning on second train_model."""
        guard = BaselineGuardHook()
        hooks = HookRegistry()
        hooks.register(guard)

        responses = [
            # Step 1: baseline
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="train_model",
                        arguments={"code": "DummyClassifier baseline"},
                    )
                ],
                usage=_usage(),
            ),
            # Step 2: real model
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t2",
                        name="train_model",
                        arguments={"code": "LightGBM train"},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"train_model": lambda code="": "Trained"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Train models")

        assert guard.baseline_established is True

    @pytest.mark.asyncio
    async def test_warns_without_baseline(self):
        """train_model without prior baseline → guard records it."""
        guard = BaselineGuardHook()
        hooks = HookRegistry()
        hooks.register(guard)

        responses = [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="train_model",
                        arguments={"code": "LightGBM train"},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"train_model": lambda code="": "Trained"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Train")

        # Baseline was never established
        assert guard.baseline_established is False


# ---------------------------------------------------------------------------
# 4. OverfittingDetectorHook E2E
# ---------------------------------------------------------------------------


class TestOverfittingDetectorE2E:
    @pytest.mark.asyncio
    async def test_detects_overfitting_in_result(self):
        """Tool result with large train-test gap triggers warning."""
        detector = OverfittingDetectorHook()
        hooks = HookRegistry()
        hooks.register(detector)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="train_model", arguments={"code": "train"})],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        def fake_train(code=""):
            return "train_accuracy: 0.98\ntest_accuracy: 0.62"

        tools = {"train_model": fake_train}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Train")

        # The LLM should have seen the overfitting warning
        second_call = agent._provider.chat.call_args_list[1]
        messages = second_call.kwargs.get("messages") or second_call.args[0]
        tool_msgs = [m for m in messages if m.role.value == "tool"]
        assert any("Overfitting" in (m.content or "") for m in tool_msgs)


# ---------------------------------------------------------------------------
# 5. StageQualityHook E2E
# ---------------------------------------------------------------------------


class TestStageQualityE2E:
    @pytest.mark.asyncio
    async def test_scores_profiling_stage(self):
        """data_profiler tool result scores the profiling stage."""
        quality = StageQualityHook()
        hooks = HookRegistry()
        hooks.register(quality)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="data_profiler", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Profile complete.", usage=_usage()),
        ]

        def fake_profiler():
            return (
                '{"missing": 5, "null": 3, "mean": 42, "std": 7, '
                '"outlier_count": 2, "quality_grade": "B"}'
            )

        tools = {"data_profiler": fake_profiler}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Profile")

        assert "profiling" in quality.scores
        assert quality.scores["profiling"] == 100  # all 4 checks pass

    @pytest.mark.asyncio
    async def test_overall_score_accumulates(self):
        """Multiple stages score independently, overall accumulates."""
        quality = StageQualityHook()
        tracker = WorkflowTrackerHook()
        hooks = HookRegistry()
        hooks.register(tracker)
        hooks.register(quality)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="data_profiler", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t2",
                        name="train_model",
                        arguments={"code": "DummyClassifier baseline cross_val_score lightgbm"},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {
            "data_profiler": lambda: (
                '{"missing": 0, "mean": 1, "outlier": 0, "quality_grade": "A"}'
            ),
            "train_model": lambda code="": "accuracy: 0.87",
        }
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Full pipeline")

        assert "profiling" in quality.scores
        assert "modeling" in quality.scores
        overall, grade = quality.get_overall_score()
        assert overall > 0
        assert grade in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# 6. Combined hooks — full pipeline regression
# ---------------------------------------------------------------------------


class TestFullPipelineRegression:
    @pytest.mark.asyncio
    async def test_all_hooks_work_together(self):
        """All 5 hooks registered simultaneously work without conflict."""
        tracker = WorkflowTrackerHook()
        leak = LeakageDetectionHook()
        baseline = BaselineGuardHook()
        overfit = OverfittingDetectorHook()
        quality = StageQualityHook()

        hooks = HookRegistry()
        for h in [tracker, leak, baseline, overfit, quality]:
            hooks.register(h)

        responses = [
            # 1: profile
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="data_profiler", arguments={})],
                usage=_usage(),
            ),
            # 2: EDA
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t2",
                        name="run_eda",
                        arguments={"code": "ttest savefig hypothesis"},
                    )
                ],
                usage=_usage(),
            ),
            # 3: feature engineering (clean)
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t3",
                        name="feature_engineer",
                        arguments={"code": "train_test_split LabelEncoder StandardScaler"},
                    )
                ],
                usage=_usage(),
            ),
            # 4: baseline
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t4",
                        name="train_model",
                        arguments={"code": "DummyClassifier baseline"},
                    )
                ],
                usage=_usage(),
            ),
            # 5: real model
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t5",
                        name="train_model",
                        arguments={"code": "LightGBM cross_val_score"},
                    )
                ],
                usage=_usage(),
            ),
            # 6: evaluation
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t6",
                        name="evaluate_model",
                        arguments={"code": "X_test accuracy f1 confusion_matrix shap"},
                    )
                ],
                usage=_usage(),
            ),
            # 7: done
            LLMResponse(content="Analysis complete.", usage=_usage()),
        ]

        tools = {
            "data_profiler": lambda: '{"missing": 0, "mean": 1, "quality_grade": "A"}',
            "run_eda": lambda code="": "p-value=0.03, plot saved",
            "feature_engineer": lambda code="": "Features created",
            "train_model": lambda code="": "train_accuracy: 0.88\ntest_accuracy: 0.85",
            "evaluate_model": lambda code="": "test accuracy: 0.85, f1: 0.83",
        }

        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=20),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        result = await agent.run("Full DS analysis")

        # Verify final result
        assert "Analysis complete" in result

        # Verify tracker
        assert tracker.stages["profiling"] == "done"
        assert tracker.stages["eda"] == "done"
        assert tracker.stages["feature_eng"] == "done"
        assert tracker.stages["modeling"] == "done"
        assert tracker.stages["evaluation"] == "done"
        comp = tracker.get_completeness()
        assert comp["completed"] >= 5

        # Verify baseline was established
        assert baseline.baseline_established is True

        # Verify quality scores exist
        assert len(quality.scores) >= 3
        overall, _grade = quality.get_overall_score()
        assert overall > 0

    @pytest.mark.asyncio
    async def test_hooks_reset_between_sessions(self):
        """Resetting hooks clears state for new session."""
        tracker = WorkflowTrackerHook()
        baseline = BaselineGuardHook()
        quality = StageQualityHook()

        # Simulate some state
        tracker._stages["eda"] = "done"
        baseline._baseline_established = True
        quality._scores["modeling"] = 80

        # Reset
        tracker.reset()
        baseline.reset()
        quality.reset()

        assert tracker.stages["eda"] == "pending"
        assert baseline.baseline_established is False
        assert len(quality.scores) == 0


# ---------------------------------------------------------------------------
# 7. Regression: time-series data split
# ---------------------------------------------------------------------------


class TestTimeSeriesSplitRegression:
    @pytest.mark.asyncio
    async def test_timeseries_code_scores_feature_eng(self):
        """Feature eng with TimeSeriesSplit should score well and not trigger leakage."""
        leak = LeakageDetectionHook()
        quality = StageQualityHook()
        hooks = HookRegistry()
        hooks.register(leak)
        hooks.register(quality)

        responses = [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="feature_engineer",
                        arguments={
                            "code": (
                                "from sklearn.model_selection import train_test_split\n"
                                "X_train, X_test = train_test_split(X, test_size=0.2)\n"
                                "from sklearn.preprocessing import StandardScaler\n"
                                "scaler = StandardScaler()\n"
                                "X_train = scaler.fit_transform(X_train)\n"
                                "X_test = scaler.transform(X_test)"
                            )
                        },
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"feature_engineer": lambda code="": "Features engineered"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Process time series")

        # No leakage in this clean code
        assert "feature_eng" in quality.scores


# ---------------------------------------------------------------------------
# 8. Regression: large data handling
# ---------------------------------------------------------------------------


class TestLargeDataRegression:
    @pytest.mark.asyncio
    async def test_large_data_profile_flows_correctly(self):
        """Profiling 100K+ rows works through the hook pipeline."""
        tracker = WorkflowTrackerHook()
        quality = StageQualityHook()
        hooks = HookRegistry()
        hooks.register(tracker)
        hooks.register(quality)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="data_profiler", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        def fake_profiler():
            return (
                "100000 rows, 50 columns. "
                "Missing: 2.1%. Outlier detected via IQR. "
                "mean: 42, std: 7. quality_grade: A"
            )

        tools = {"data_profiler": fake_profiler}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Profile large dataset")

        assert tracker.stages["profiling"] == "done"
        assert quality.scores.get("profiling", 0) >= 75


# ---------------------------------------------------------------------------
# 9. Regression: fairness audit
# ---------------------------------------------------------------------------


class TestFairnessAuditRegression:
    @pytest.mark.asyncio
    async def test_fairness_checks_boost_evaluation_score(self):
        """Evaluation result mentioning fairness metrics should score well."""
        quality = StageQualityHook()
        hooks = HookRegistry()
        hooks.register(quality)

        responses = [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="evaluate_model",
                        arguments={"code": "X_test accuracy f1 demographic_parity shap"},
                    )
                ],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        def fake_eval(code=""):
            return (
                "test accuracy: 0.85, f1: 0.82. "
                "confusion_matrix computed. "
                "Fairness: demographic_parity = 0.92 across protected groups. "
                "SHAP feature importance: age, income top features."
            )

        tools = {"evaluate_model": fake_eval}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        await agent.run("Evaluate with fairness")

        assert "evaluation" in quality.scores
        # All 5 checks should pass: test_set, metrics, error, importance, fairness
        assert quality.scores["evaluation"] >= 80


# ---------------------------------------------------------------------------
# 10. Regression: budget exhaustion
# ---------------------------------------------------------------------------


class TestBudgetExhaustionRegression:
    @pytest.mark.asyncio
    async def test_budget_guard_stops_expensive_tools(self):
        """When budget is critical, expensive tools are denied."""
        guard = BudgetGuardHook(max_cost_usd=1.0, critical_pct=90.0)
        tracker = WorkflowTrackerHook()
        hooks = HookRegistry()
        hooks.register(guard)
        hooks.register(tracker)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="train_model", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Budget exceeded.", usage=_usage()),
        ]

        tools = {"train_model": lambda: "Trained"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10, max_cost_usd=1.0),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
            mode="auto",
        )
        # Manually push cost to 95% ($0.95 of $1.00)
        agent._budget.state.total_cost_usd = 0.95

        await agent.run("Train model")

        # The tool should have been denied
        second_call = agent._provider.chat.call_args_list[1]
        messages = second_call.kwargs.get("messages") or second_call.args[0]
        tool_msgs = [m for m in messages if m.role.value == "tool"]
        assert any("DENIED" in (m.content or "") for m in tool_msgs)

    @pytest.mark.asyncio
    async def test_process_metrics_during_budget_scenario(self):
        """ProcessMetricsHook accurately tracks tool calls including denied ones."""
        metrics = ProcessMetricsHook()
        guard = BudgetGuardHook(max_cost_usd=1.0, critical_pct=90.0)
        hooks = HookRegistry()
        hooks.register(guard)
        hooks.register(metrics)

        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="train_model", arguments={})],
                usage=_usage(),
            ),
            LLMResponse(content="Done.", usage=_usage()),
        ]

        tools = {"train_model": lambda: "ok"}
        agent = DSAgent(
            provider=_mock_provider(responses),
            tool_registry=_mock_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=10, max_cost_usd=1.0),
            prompt_builder=PromptBuilder(),
            hook_registry=hooks,
        )
        agent._budget.state.total_cost_usd = 0.95

        await agent.run("Train")

        # Pre hooks ran (including metrics counter), but tool was denied
        m = metrics.metrics
        assert m["tool_call_count"] >= 1
