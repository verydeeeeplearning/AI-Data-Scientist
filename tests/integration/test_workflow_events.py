"""Integration tests — verify hook events flow correctly through the chain.

Tests that hooks emit the right events with correct payloads,
and that the emit wiring (HookContext.emit → callback) works end-to-end.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.builtin_hooks import (
    ExecPlanSaveHook,
    ProcessMetricsHook,
    SessionInitHook,
)
from ds_agent.agent.core import DSAgent
from ds_agent.agent.ds_workflow_hooks import (
    BaselineGuardHook,
    LeakageDetectionHook,
    ModelSanityCheckHook,
    OverfittingDetectorHook,
    ProfileResultsHook,
    StageQualityHook,
    WorkflowTrackerHook,
)
from ds_agent.agent.hooks import HookContext, HookRegistry
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_and_events() -> tuple[HookRegistry, list[tuple[str, dict]]]:
    """Create a registry with all DS hooks and an event collector."""
    events: list[tuple[str, dict]] = []
    registry = HookRegistry()
    registry.register(WorkflowTrackerHook())
    registry.register(LeakageDetectionHook())
    registry.register(BaselineGuardHook())
    registry.register(OverfittingDetectorHook())
    registry.register(StageQualityHook())
    registry.register(ModelSanityCheckHook())
    registry.register(ProfileResultsHook())
    registry.register(SessionInitHook())
    registry.register(ProcessMetricsHook())
    return registry, events


def _ctx(events: list) -> HookContext:
    return HookContext(
        emit=lambda e, p: events.append((e, p)),
        session_id="test-session",
        iteration=1,
    )


# ---------------------------------------------------------------------------
# Event chain integration tests
# ---------------------------------------------------------------------------


class TestEventChain:
    """Verify events flow through the full hook registry."""

    @pytest.mark.asyncio
    async def test_session_init_emits_plan_created(self):
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        await registry.run_session_init(ctx)

        plan_events = [event for event in events if event[0] == "plan.created"]
        assert len(plan_events) == 1
        assert plan_events[0][1]["planTree"]["id"] == "ds_workflow_plan"

    @pytest.mark.asyncio
    async def test_workflow_step_events_on_profiler(self):
        """data_profiler → step(running) + step(done) + profile + quality."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        await registry.run_pre_hooks("data_profiler", {}, ctx)
        step_events = [e for e in events if e[0] == "workflow.step"]
        assert len(step_events) == 1
        assert step_events[0][1]["status"] == "running"

        await registry.run_post_hooks(
            "data_profiler",
            {},
            "200 rows, 15 columns, missing 5.2%, Grade: B",
            False,
            ctx,
        )

        step_events = [e for e in events if e[0] == "workflow.step"]
        assert len(step_events) == 2
        assert step_events[1][1]["status"] == "done"

        # profile.results should also be emitted
        profile_events = [e for e in events if e[0] == "profile.results"]
        assert len(profile_events) == 1
        assert profile_events[0][1]["rows"] == 200
        assert profile_events[0][1]["columns"] == 15
        assert profile_events[0][1]["grade"] == "B"

    @pytest.mark.asyncio
    async def test_leakage_warning_event(self):
        """feature_engineer with leakage pattern → harness.warning event."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        leaky_code = "scaler.fit_transform(X_test)"
        await registry.run_post_hooks("feature_engineer", {"code": leaky_code}, "ok", False, ctx)

        warning_events = [e for e in events if e[0] == "harness.warning"]
        assert len(warning_events) >= 1
        assert warning_events[0][1]["type"] == "leakage"
        assert warning_events[0][1]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_baseline_warning_before_train(self):
        """train_model without baseline → harness.warning (baseline_missing)."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        await registry.run_pre_hooks("train_model", {"code": "model.fit(X, y)"}, ctx)

        warning_events = [e for e in events if e[0] == "harness.warning"]
        baseline_warnings = [w for w in warning_events if w[1]["type"] == "baseline_missing"]
        assert len(baseline_warnings) == 1

    @pytest.mark.asyncio
    async def test_overfitting_warning_event(self):
        """train_model with large gap → harness.warning (overfitting)."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        result = "train_accuracy: 0.99, test_accuracy: 0.60"
        await registry.run_post_hooks("train_model", {}, result, False, ctx)

        warning_events = [e for e in events if e[0] == "harness.warning"]
        overfit_warnings = [w for w in warning_events if w[1]["type"] == "overfitting"]
        assert len(overfit_warnings) == 1

    @pytest.mark.asyncio
    async def test_quality_update_on_eda(self):
        """run_eda → quality.update event with score and checks."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        eda_result = (
            "Performed pearsonr correlation, saved heatmap plot via savefig, "
            "found outlier with IQR method"
        )
        await registry.run_post_hooks("run_eda", {"code": eda_result}, eda_result, False, ctx)

        quality_events = [e for e in events if e[0] == "quality.update"]
        assert len(quality_events) >= 1
        assert quality_events[0][1]["stage"] == "eda"
        assert quality_events[0][1]["score"] > 0

    @pytest.mark.asyncio
    async def test_sanity_check_on_train_model(self):
        """train_model → quality.update with sanity check results."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        result = "Model trained successfully. Accuracy: 0.85"
        await registry.run_post_hooks("train_model", {}, result, False, ctx)

        quality_events = [e for e in events if e[0] == "quality.update"]
        # Both StageQualityHook and ModelSanityCheckHook emit quality.update
        sanity_checks = [
            e
            for e in quality_events
            if any(c["name"] == "prediction_distribution" for c in e[1].get("checks", []))
        ]
        assert len(sanity_checks) == 1

    @pytest.mark.asyncio
    async def test_session_init_returns_rules(self):
        """SessionInitHook injects safety + methodology rules."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        injections = await registry.run_session_init(ctx)
        assert len(injections) >= 1
        combined = "\n".join(injections)
        assert "Safety" in combined
        assert "baseline" in combined.lower()

    @pytest.mark.asyncio
    async def test_full_workflow_event_sequence(self):
        """Simulate a mini DS workflow: load → profile → eda → model → eval."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        # 1. Load data
        await registry.run_pre_hooks("data_loader", {}, ctx)
        await registry.run_post_hooks("data_loader", {}, "Loaded 1000 rows", False, ctx)

        # 2. Profile
        await registry.run_pre_hooks("data_profiler", {}, ctx)
        await registry.run_post_hooks(
            "data_profiler", {}, "1000 rows, 20 columns, missing 2%, Grade: A", False, ctx
        )

        # 3. EDA
        await registry.run_pre_hooks("run_eda", {}, ctx)
        await registry.run_post_hooks(
            "run_eda", {"code": "sns.heatmap(corr())"}, "savefig correlation", False, ctx
        )

        # 4. Model
        await registry.run_pre_hooks("train_model", {"code": "DummyClassifier baseline"}, ctx)
        await registry.run_post_hooks(
            "train_model",
            {"code": "DummyClassifier baseline"},
            "baseline accuracy: 0.65",
            False,
            ctx,
        )

        # 5. Evaluate
        await registry.run_pre_hooks("evaluate_model", {}, ctx)
        await registry.run_post_hooks(
            "evaluate_model",
            {},
            "test_accuracy: 0.85, f1: 0.82, x_test evaluated",
            False,
            ctx,
        )

        # Verify we got workflow.step events for all stages
        step_events = [e for e in events if e[0] == "workflow.step"]
        stages_seen = {e[1]["stage"] for e in step_events}
        assert "data_loading" in stages_seen
        assert "profiling" in stages_seen
        assert "eda" in stages_seen
        assert "modeling" in stages_seen
        assert "evaluation" in stages_seen

        plan_updates = [event for event in events if event[0] == "plan.updated"]
        assert len(plan_updates) >= 10

        # Verify quality events were emitted
        quality_events = [e for e in events if e[0] == "quality.update"]
        assert len(quality_events) >= 3  # profiling, eda, modeling, evaluation

        # Verify profile.results was emitted
        profile_events = [e for e in events if e[0] == "profile.results"]
        assert len(profile_events) == 1


class TestProcessMetricsIntegration:
    @pytest.mark.asyncio
    async def test_metrics_accumulate_across_tools(self):
        """ProcessMetricsHook counts tool calls and retries across a workflow."""
        registry, events = _make_registry_and_events()
        ctx = _ctx(events)

        await registry.run_session_init(ctx)

        # Tool 1: succeed
        await registry.run_pre_hooks("data_loader", {}, ctx)
        await registry.run_post_hooks("data_loader", {}, "ok", False, ctx)

        # Tool 2: fail
        await registry.run_pre_hooks("run_eda", {}, ctx)
        await registry.run_post_hooks("run_eda", {}, "error", True, ctx)

        # Tool 2: retry
        await registry.run_pre_hooks("run_eda", {}, ctx)
        await registry.run_post_hooks("run_eda", {}, "ok", False, ctx)

        # Find the ProcessMetricsHook
        metrics_hook = next(h for h in registry.hooks if isinstance(h, ProcessMetricsHook))
        m = metrics_hook.metrics
        assert m["tool_call_count"] == 3
        assert m["retry_count"] == 1
        assert m["error_count"] == 1
        assert m["tool_counts"]["data_loader"] == 1
        assert m["tool_counts"]["run_eda"] == 2


class TestExecPlanSaveIntegration:
    @pytest.mark.asyncio
    async def test_saves_plan_on_first_iteration(self, tmp_path):
        """ExecPlanSaveHook saves plan to disk when first tool returns plan-like content."""
        hook = ExecPlanSaveHook(base_dir=tmp_path / "plans")
        ctx = HookContext(
            emit=lambda e, p: None,
            session_id="test-123",
            iteration=1,
        )

        result = "Step 1. Load data\nStep 2. Profile quality\nPlan: approach with baseline"
        await hook.post_tool_use("data_loader", {}, result, False, ctx)

        plan_file = tmp_path / "plans" / "test-123.md"
        assert plan_file.exists()
        content = plan_file.read_text(encoding="utf-8")
        assert "Step 1" in content
        assert "test-123" in content

    @pytest.mark.asyncio
    async def test_skips_error_results(self, tmp_path):
        hook = ExecPlanSaveHook(base_dir=tmp_path / "plans")
        ctx = HookContext(emit=lambda e, p: None, session_id="test-err", iteration=1)

        await hook.post_tool_use("data_loader", {}, "error", True, ctx)
        assert not (tmp_path / "plans" / "test-err.md").exists()

    @pytest.mark.asyncio
    async def test_only_saves_once(self, tmp_path):
        hook = ExecPlanSaveHook(base_dir=tmp_path / "plans")
        ctx = HookContext(emit=lambda e, p: None, session_id="test-once", iteration=1)

        result = "Step 1. Load\nStep 2. Plan approach"
        await hook.post_tool_use("data_loader", {}, result, False, ctx)
        # Second call — should not overwrite
        await hook.post_tool_use("run_eda", {}, "Step 1 something else plan", False, ctx)
        assert hook._saved is True


# ---------------------------------------------------------------------------
# Reasoning ↔ plan-node linkage (DSAgent ↔ WorkflowTrackerHook)
# ---------------------------------------------------------------------------


def _make_provider_for_thinking(thinking_text: str) -> MagicMock:
    """Build a stub LLM provider that returns a single thinking-only step."""

    provider = MagicMock()
    provider.chat = AsyncMock(
        return_value=LLMResponse(
            content="ok",
            thinking=thinking_text,
            usage=Usage(),
        )
    )
    provider.count_tokens = AsyncMock(return_value=10)
    provider.get_model_info = MagicMock(
        return_value=ModelInfo(
            model_id="test-model",
            provider="test",
            display_name="Test",
            max_context_tokens=128_000,
            max_output_tokens=4_096,
        )
    )
    return provider


class _StubToolRegistry:
    """Minimal ToolRegistry stand-in — no tools, no dispatch needed."""

    def get_definitions(self) -> list[dict]:
        return []

    async def dispatch(self, name: str, arguments: dict) -> str:  # pragma: no cover
        raise AssertionError(f"unexpected tool dispatch: {name}")


class TestReasoningPlanNodeLinkage:
    """Reasoning-emitted events must carry planNodeId for the active stage."""

    @pytest.mark.asyncio
    async def test_reasoning_emitted_links_to_current_plan_node(self):
        """When the agent emits thinking while a stage is running, the
        ``reasoning.emitted`` payload must include the active stage's
        ``planNodeId`` AND the WorkflowTrackerHook must record the reasoning
        id in that node's ``reasoningRefs`` (visible via a follow-up
        ``plan.updated`` patch).
        """

        emitted: list[tuple[str, dict]] = []

        callbacks = MagicMock()
        callbacks.emit_event = lambda event, payload: emitted.append((event, payload))
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()

        tracker = WorkflowTrackerHook()
        registry = HookRegistry()
        registry.register(tracker)

        # Stub provider whose ``chat`` ALSO flips the profiling stage to
        # ``running`` immediately before returning. This mimics the
        # realistic interleaving where the LLM step happens while a stage
        # tool is executing — the WorkflowTrackerHook's
        # ``on_session_init`` runs first and resets state, so we cannot
        # pre-seed earlier than the LLM call itself.
        async def _chat(**_kwargs):
            tracker._stages["profiling"] = "running"
            return LLMResponse(
                content="ok",
                thinking="Considering profile coverage.",
                usage=Usage(),
            )

        provider = _make_provider_for_thinking("Considering profile coverage.")
        provider.chat = _chat  # type: ignore[assignment]

        agent = DSAgent(
            provider=provider,
            tool_registry=_StubToolRegistry(),
            callbacks=callbacks,
            hook_registry=registry,
        )
        agent.set_runtime_context(run_id="run-link-1", surface="test")

        await agent.run("Profile the dataset.")
        # Sanity: the stage really was running at the moment of emission.
        assert tracker.current_active_stage_id() == "profiling"

        reasoning_events = [evt for evt in emitted if evt[0] == "reasoning.emitted"]
        assert len(reasoning_events) == 1
        payload = reasoning_events[0][1]
        assert payload["planNodeId"] == "profiling"
        # id is mandatory for downstream plan-node ↔ trace linking.
        assert isinstance(payload.get("id"), str)
        assert payload["id"]

        # The WorkflowTrackerHook should have recorded the reasoning id on
        # the active stage and emitted a corresponding plan.updated patch.
        assert payload["id"] in tracker._stage_reasoning_refs["profiling"]
        link_patches = [
            evt
            for evt in emitted
            if evt[0] == "plan.updated"
            and evt[1].get("nodeId") == "profiling"
            and "reasoningRefs" in evt[1].get("updates", {})
        ]
        assert len(link_patches) >= 1
        assert payload["id"] in link_patches[-1][1]["updates"]["reasoningRefs"]
