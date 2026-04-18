"""E2E simulation test — full DS workflow with mock LLM provider.

Scenario: "titanic.csv 분석해서 생존 예측 모델 만들어줘"

The mock provider simulates an LLM that follows the DS workflow:
1. data_loader → load data
2. data_profiler → profile quality
3. run_eda → exploratory analysis
4. execute_code → feature engineering
5. execute_code → model training
6. execute_code → evaluation
7. Final text response with summary
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.core import DSAgent
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.domain.entities.messages import (
    LLMResponse,
    Role,
    ToolCall,
    Usage,
)
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.value_objects.budget import BudgetPolicy


def _make_mock_provider():
    """Create a mock LLM that simulates a DS workflow.

    Returns tool calls in sequence, then a final summary.
    """
    responses = [
        # Step 1: Load data
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="execute_code",
                    arguments={"code": "print('Data loaded: 891 rows, 12 columns')"},
                )
            ],
            usage=Usage(input_tokens=500, output_tokens=100),
            model="mock-ds-llm",
        ),
        # Step 2: Profile data
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc2",
                    name="execute_code",
                    arguments={
                        "code": (
                            "import json\n"
                            "profile = {\n"
                            "    'shape': [891, 12],\n"
                            "    'quality_grade': 'B',\n"
                            "    'missing': {'Age': '19.9%', 'Cabin': '77.1%'},\n"
                            "    'target': {'Survived': {'0': 549, '1': 342}}\n"
                            "}\n"
                            "print(json.dumps(profile))"
                        )
                    },
                )
            ],
            usage=Usage(input_tokens=800, output_tokens=200),
            model="mock-ds-llm",
        ),
        # Step 3: EDA
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc3",
                    name="execute_code",
                    arguments={
                        "code": (
                            "import json\n"
                            "findings = {\n"
                            "    'top_features': ['Sex', 'Pclass', 'Fare', 'Age'],\n"
                            "    'class_balance': '61.6% vs 38.4%',\n"
                            "    'key_insight': 'Sex is the strongest predictor'\n"
                            "}\n"
                            "print(json.dumps(findings))"
                        )
                    },
                )
            ],
            usage=Usage(input_tokens=1000, output_tokens=300),
            model="mock-ds-llm",
        ),
        # Step 4: Feature engineering
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc4",
                    name="execute_code",
                    arguments={
                        "code": (
                            "import json\n"
                            "result = {\n"
                            "    'features_created': 15,\n"
                            "    'train_size': 623,\n"
                            "    'test_size': 268,\n"
                            "    'encoding': 'label + onehot',\n"
                            "    'imputation': 'median for Age'\n"
                            "}\n"
                            "print(json.dumps(result))"
                        )
                    },
                )
            ],
            usage=Usage(input_tokens=1200, output_tokens=400),
            model="mock-ds-llm",
        ),
        # Step 5: Model training
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc5",
                    name="execute_code",
                    arguments={
                        "code": (
                            "import json\n"
                            "results = {\n"
                            "    'models': [\n"
                            "        {'name': 'LogisticRegression', 'f1': 0.76, 'auc': 0.84},\n"
                            "        {'name': 'LightGBM', 'f1': 0.81, 'auc': 0.87},\n"
                            "        {'name': 'XGBoost', 'f1': 0.79, 'auc': 0.86}\n"
                            "    ],\n"
                            "    'best_model': 'LightGBM'\n"
                            "}\n"
                            "print(json.dumps(results))"
                        )
                    },
                )
            ],
            usage=Usage(input_tokens=1500, output_tokens=500),
            model="mock-ds-llm",
        ),
        # Step 6: Evaluation
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="tc6",
                    name="execute_code",
                    arguments={
                        "code": (
                            "import json\n"
                            "evaluation = {\n"
                            "    'test_f1': 0.79,\n"
                            "    'test_auc': 0.85,\n"
                            "    'test_accuracy': 0.82,\n"
                            "    'feature_importance': ['Sex', 'Fare', 'Age', 'Pclass'],\n"
                            "    'confusion_matrix': [[90, 15], [23, 50]]\n"
                            "}\n"
                            "print(json.dumps(evaluation))"
                        )
                    },
                )
            ],
            usage=Usage(input_tokens=1800, output_tokens=400),
            model="mock-ds-llm",
        ),
        # Step 7: Final summary (no tool calls)
        LLMResponse(
            content=(
                "## Titanic 생존 예측 분석 완료\n\n"
                "### 데이터 요약\n"
                "- 891행 x 12열, 품질등급 B\n"
                "- 주요 결측: Age (19.9%), Cabin (77.1%)\n\n"
                "### 모델 성능\n\n"
                "| Model | F1 | AUC |\n"
                "|-------|-----|-----|\n"
                "| Baseline (LR) | 0.76 | 0.84 |\n"
                "| **LightGBM** ★ | **0.81** | **0.87** |\n"
                "| XGBoost | 0.79 | 0.86 |\n\n"
                "### 핵심 발견\n"
                "- Sex가 가장 강력한 예측 변수\n"
                "- LightGBM이 baseline 대비 +6.6% F1 향상\n"
                "- 테스트 세트 F1=0.79, AUC=0.85\n"
            ),
            usage=Usage(input_tokens=2000, output_tokens=300),
            model="mock-ds-llm",
        ),
    ]

    provider = MagicMock()
    provider.chat = AsyncMock(side_effect=responses)
    provider.count_tokens = AsyncMock(return_value=500)
    provider.get_model_info = MagicMock(
        return_value=ModelInfo(
            model_id="mock-ds-llm",
            provider="mock",
            display_name="Mock DS LLM",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )
    )
    return provider


class _IsolatedToolRegistry:
    """A separate tool registry for E2E tests, isolated from global state."""

    def __init__(self):
        self._tools = {}

    def register(self, name, handler):
        self._tools[name] = handler

    def get_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": n,
                    "description": n,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
            for n in self._tools
        ]

    async def dispatch(self, name, arguments):
        import json as _json

        handler = self._tools.get(name)
        if handler is None:
            return _json.dumps({"error": f"Tool not found: {name}"})
        try:
            import asyncio

            if asyncio.iscoroutinefunction(handler):
                return str(await handler(**arguments))
            return str(handler(**arguments))
        except Exception as e:
            return _json.dumps({"error": str(e)})


def _make_isolated_registry():
    from ds_agent.tools.sandbox import ProcessSandbox

    async def _execute_code(code: str, timeout: int = 120) -> str:
        sandbox = ProcessSandbox(timeout=timeout)
        result = await sandbox.execute(code)
        return result.stdout if result.success else f"Error:\n{result.stderr}"

    registry = _IsolatedToolRegistry()
    registry.register("execute_code", _execute_code)
    return registry


class TestDSWorkflowE2E:
    """End-to-end test simulating a complete DS workflow."""

    @pytest.mark.asyncio
    async def test_full_ds_workflow(self):
        """Simulate: data load → profile → eda → features → model → evaluate → report."""
        provider = _make_mock_provider()

        agent = DSAgent(
            provider=provider,
            tool_registry=_make_isolated_registry(),
            budget_policy=BudgetPolicy(max_iterations=20, max_cost_usd=5.0),
            prompt_builder=PromptBuilder(),
        )

        result = await agent.run("titanic.csv 분석해서 생존 예측 모델 만들어줘")

        # Verify final response contains expected content
        assert "Titanic" in result or "titanic" in result.lower()
        assert "LightGBM" in result
        assert "0.81" in result or "0.87" in result
        assert "F1" in result or "f1" in result.lower()

        # Verify provider was called correct number of times (6 tool + 1 final)
        assert provider.chat.call_count == 7

    @pytest.mark.asyncio
    async def test_workflow_tracks_budget(self):
        """Verify budget tracking across the full workflow."""
        provider = _make_mock_provider()

        agent = DSAgent(
            provider=provider,
            tool_registry=_make_isolated_registry(),
            budget_policy=BudgetPolicy(max_iterations=20),
            prompt_builder=PromptBuilder(),
        )

        await agent.run("분석해줘")

        # Budget should reflect all 7 LLM calls
        summary = agent._budget.get_summary()
        assert summary["iterations_used"] == 7
        assert summary["total_cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_workflow_tools_executed(self):
        """Verify each tool call was dispatched."""
        provider = _make_mock_provider()
        tool_calls_log: list[str] = []

        registry = _make_isolated_registry()
        original_dispatch = registry.dispatch

        async def tracking_dispatch(name, args):
            tool_calls_log.append(name)
            return await original_dispatch(name, args)

        registry.dispatch = tracking_dispatch  # type: ignore[assignment]

        agent = DSAgent(
            provider=provider,
            tool_registry=registry,
            budget_policy=BudgetPolicy(max_iterations=20),
            prompt_builder=PromptBuilder(),
        )
        await agent.run("분석해줘")

        # 6 tool calls (all execute_code in this simulation)
        assert len(tool_calls_log) == 6
        assert all(name == "execute_code" for name in tool_calls_log)

    @pytest.mark.asyncio
    async def test_workflow_callbacks_fire(self):
        """Verify callbacks are triggered during workflow."""
        provider = _make_mock_provider()

        callbacks = MagicMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider,
            tool_registry=_make_isolated_registry(),
            budget_policy=BudgetPolicy(max_iterations=20),
            callbacks=callbacks,
            prompt_builder=PromptBuilder(),
        )

        await agent.run("분석해줘")

        # 6 tool starts + 6 tool ends
        assert callbacks.on_tool_start.call_count == 6
        assert callbacks.on_tool_end.call_count == 6
        # At least 7 steps
        assert callbacks.on_step.call_count >= 7

    @pytest.mark.asyncio
    async def test_tool_results_contain_data(self):
        """Verify tool execution produces actual output."""
        provider = _make_mock_provider()

        agent = DSAgent(
            provider=provider,
            tool_registry=_make_isolated_registry(),
            budget_policy=BudgetPolicy(max_iterations=20),
            prompt_builder=PromptBuilder(),
        )

        await agent.run("분석해줘")

        # The provider saw tool results in messages
        # Check that tool results were passed back to the LLM
        for call in provider.chat.call_args_list[1:]:
            messages = call.kwargs.get("messages") or call.args[0]
            tool_msgs = [m for m in messages if m.role == Role.TOOL]
            for tm in tool_msgs:
                # Tool results should contain actual data (from sandbox execution)
                assert tm.content is not None
                assert len(tm.content) > 0

    @pytest.mark.asyncio
    async def test_budget_exhaustion_stops_workflow(self):
        """Agent stops gracefully when budget runs out mid-workflow."""
        provider = _make_mock_provider()

        agent = DSAgent(
            provider=provider,
            tool_registry=_make_isolated_registry(),
            budget_policy=BudgetPolicy(max_iterations=3),  # Only allow 3 steps
            prompt_builder=PromptBuilder(),
        )

        result = await agent.run("분석해줘")

        # Should stop early with budget message
        assert "budget" in result.lower() or "exhausted" in result.lower()
        # Should not have completed all 7 calls
        assert provider.chat.call_count <= 3
