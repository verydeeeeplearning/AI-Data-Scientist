"""Hook system tests — PreToolUse/PostToolUse, built-in hooks, permission policy."""

from unittest.mock import MagicMock

import pytest

from ds_agent.agent.builtin_hooks import (
    AuditLogHook,
    BudgetGuardHook,
    ExperimentTrackerHook,
    PermissionHook,
    SessionInitHook,
)
from ds_agent.agent.hooks import (
    FinalResponseResult,
    HookAction,
    HookContext,
    HookRegistry,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.agent.permissions import (
    PermissionMode,
    PermissionPolicy,
    ToolSafetyLevel,
    get_tool_safety,
)
from ds_agent.domain.entities.mission_pack import MissionPack

# ---------------------------------------------------------------------------
# HookRegistry
# ---------------------------------------------------------------------------


class TestHookRegistry:
    @pytest.mark.asyncio
    async def test_empty_registry_allows(self):
        registry = HookRegistry()
        ctx = HookContext()
        result = await registry.run_pre_hooks("data_loader", {}, ctx)
        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_deny_hook_stops_execution(self):
        class DenyAll(ToolHook):
            name = "deny_all"
            priority = 10

            async def pre_tool_use(self, tool_name, arguments, context):
                return PreToolUseResult(action=HookAction.DENY, deny_reason="blocked")

        registry = HookRegistry()
        registry.register(DenyAll())
        result = await registry.run_pre_hooks("any_tool", {}, HookContext())
        assert result.action == HookAction.DENY
        assert result.deny_reason == "blocked"

    @pytest.mark.asyncio
    async def test_modify_hook_changes_arguments(self):
        class AddDefault(ToolHook):
            name = "add_default"
            priority = 10

            async def pre_tool_use(self, tool_name, arguments, context):
                new_args = {**arguments, "timeout": 60}
                return PreToolUseResult(action=HookAction.MODIFY, modified_arguments=new_args)

        registry = HookRegistry()
        registry.register(AddDefault())
        result = await registry.run_pre_hooks("execute_code", {"code": "x"}, HookContext())
        assert result.action == HookAction.ALLOW
        assert result.modified_arguments["timeout"] == 60
        assert result.modified_arguments["code"] == "x"

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Lower priority number runs first."""
        order = []

        class HookA(ToolHook):
            name = "a"
            priority = 20

            async def pre_tool_use(self, tool_name, arguments, context):
                order.append("a")
                return PreToolUseResult()

        class HookB(ToolHook):
            name = "b"
            priority = 5

            async def pre_tool_use(self, tool_name, arguments, context):
                order.append("b")
                return PreToolUseResult()

        registry = HookRegistry()
        registry.register(HookA())
        registry.register(HookB())
        await registry.run_pre_hooks("tool", {}, HookContext())
        assert order == ["b", "a"]

    @pytest.mark.asyncio
    async def test_post_hooks_chain_modifications(self):
        class AppendA(ToolHook):
            name = "append_a"
            priority = 10

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                return PostToolUseResult(modified_result=result + "_A")

        class AppendB(ToolHook):
            name = "append_b"
            priority = 20

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                return PostToolUseResult(modified_result=result + "_B")

        registry = HookRegistry()
        registry.register(AppendA())
        registry.register(AppendB())
        result = await registry.run_post_hooks("tool", {}, "base", False, HookContext())
        assert result.modified_result == "base_A_B"

    @pytest.mark.asyncio
    async def test_post_hook_trigger_learning(self):
        class LearnHook(ToolHook):
            name = "learner"

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                return PostToolUseResult(trigger_learning=True)

        registry = HookRegistry()
        registry.register(LearnHook())
        result = await registry.run_post_hooks("train_model", {}, "ok", False, HookContext())
        assert result.trigger_learning is True

    @pytest.mark.asyncio
    async def test_final_response_hooks_chain_modifications(self):
        class StripMachineBlock(ToolHook):
            name = "strip_machine_block"
            priority = 10

            async def on_final_response(self, response, context):
                return FinalResponseResult(modified_response=response.replace("<!--x-->", ""))

        class NormalizeWhitespace(ToolHook):
            name = "normalize_whitespace"
            priority = 20

            async def on_final_response(self, response, context):
                return FinalResponseResult(modified_response=response.strip())

        registry = HookRegistry()
        registry.register(StripMachineBlock())
        registry.register(NormalizeWhitespace())
        result = await registry.run_final_response_hooks("answer<!--x-->   ", HookContext())
        assert result.modified_response == "answer"

    @pytest.mark.asyncio
    async def test_final_response_hooks_propagate_followup_flags(self):
        class FollowupHook(ToolHook):
            name = "followup"
            priority = 10

            async def on_final_response(self, response, context):
                return FinalResponseResult(
                    modified_response=response + "\n\nVerifier follow-up required.",
                    requires_followup=True,
                    followup_reason="Resolve the verifier finding before review.",
                )

        registry = HookRegistry()
        registry.register(FollowupHook())

        result = await registry.run_final_response_hooks("answer", HookContext())

        assert result.modified_response == "answer\n\nVerifier follow-up required."
        assert result.requires_followup is True
        assert result.followup_reason == "Resolve the verifier finding before review."


# ---------------------------------------------------------------------------
# PermissionPolicy
# ---------------------------------------------------------------------------


class TestPermissionPolicy:
    @staticmethod
    def _mission_pack(**overrides) -> MissionPack:
        payload = {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "boundary": {
                "allowed_data_domains": ["growth", "sales"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["jira_create", "artifact_draft"],
            },
            "required_checks": ["schema_drift"],
            "required_artifacts": ["exec_brief"],
            "success_criteria": ["issue_classified"],
            "action_policy_overrides": {"jira_create": {"delegate": "auto"}},
            "certification": {
                "current_level": "delegate",
                "next_target": "autopilot",
                "autopilot_requirements": {
                    "shadow_runs_passed": 10,
                    "critical_violations": 0,
                    "verifier_avg_score": 0.85,
                    "rollback_rehearsal": "passed",
                    "owner_approvals": 2,
                },
            },
        }
        payload.update(overrides)
        return MissionPack.model_validate(payload)

    def test_full_access_allows_known_delegate_local_write(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, _ = policy.check("write_file", {"file_path": "notes.md", "content": "ok"})
        assert allowed is True

    def test_read_only_blocks_caution_tools(self):
        policy = PermissionPolicy(mode=PermissionMode.READ_ONLY, agent_mode="auto")
        allowed, reason = policy.check("execute_code")
        assert allowed is False
        assert "Read-only" in reason

    def test_read_only_allows_safe_tools(self):
        policy = PermissionPolicy(mode=PermissionMode.READ_ONLY, agent_mode="auto")
        allowed, _ = policy.check("data_loader")
        assert allowed is True

    def test_supervised_blocks_caution(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="supervised")
        allowed, reason = policy.check("train_model")
        assert allowed is False
        assert "Supervised" in reason

    def test_supervised_allows_safe(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="supervised")
        allowed, _ = policy.check("data_profiler")
        assert allowed is True

    def test_step_by_step_blocks_non_safe(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="step-by-step")
        allowed, _ = policy.check("execute_code")
        assert allowed is False

    def test_step_by_step_blocks_safe_tools_too(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="step-by-step")
        allowed, reason = policy.check("data_loader")
        assert allowed is False
        assert "Step-by-step" in reason

    def test_denied_tools_always_blocked(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            denied_tools=frozenset({"data_loader"}),
        )
        allowed, reason = policy.check("data_loader")
        assert allowed is False
        assert "explicitly denied" in reason

    def test_auto_mode_uses_action_matrix_for_jira_creation(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check("create_jira_ticket")
        assert allowed is False
        assert "Delegate mode" in reason
        assert "requires approval" in reason

    def test_auto_mode_uses_arguments_for_pii_sql_classification(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check("sql_query", {"data_sensitivity": "pii"})
        assert allowed is False
        assert "Delegate mode" in reason
        assert "requires approval" in reason

    def test_auto_mode_uses_unknown_matrix_for_generic_execute_code(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check("execute_code", {"code": "print('hello')"})
        assert allowed is False
        assert "Delegate mode" in reason
        assert "requires approval" in reason

    def test_auto_mode_uses_action_matrix_for_git_pr_creation(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check(
            "create_git_pr",
            {"title": "PR", "body": "body", "head": "feature-branch"},
        )
        assert allowed is False
        assert "Delegate mode" in reason
        assert "requires approval" in reason

    def test_auto_mode_allows_ask_user_as_read_only_coordination(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check("ask_user", {"question": "Proceed?"})
        assert allowed is True
        assert reason == ""

    def test_auto_mode_policy_check_record_approval_requires_approval(self):
        policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")
        allowed, reason = policy.check(
            "policy_check",
            {"action": "generate_deployment", "record_approval": True},
        )
        assert allowed is False
        assert "Delegate mode" in reason
        assert "requires approval" in reason

    def test_mission_override_can_allow_delegate_jira(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            mission="weekly-kpi-triage",
            mission_pack=self._mission_pack(),
        )
        allowed, reason = policy.check("create_jira_ticket", {"data_domain": "growth"})
        assert allowed is True
        assert reason == ""

    def test_out_of_boundary_action_mentions_mission_boundary(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            mission="weekly-kpi-triage",
            mission_pack=self._mission_pack(),
        )
        allowed, reason = policy.check(
            "generate_deployment",
            {"environment": "production", "data_domain": "growth"},
        )
        assert allowed is False
        assert "outside mission boundary" in reason

    def test_autopilot_requires_mission_certification(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            authority_mode="autopilot",
            mission="weekly-kpi-triage",
            mission_pack=self._mission_pack(),
        )

        allowed, reason = policy.check("generate_report", {"data_domain": "growth"})

        assert allowed is False
        assert "missing mission certification" in reason

    def test_freeze_overlay_blocks_mission_override_write_actions(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            authority_mode="freeze",
            mission="weekly-kpi-triage",
            mission_pack=self._mission_pack(),
        )

        allowed, reason = policy.check("create_jira_ticket", {"data_domain": "growth"})

        assert allowed is False
        assert "Freeze mode" in reason

    def test_incident_overlay_requires_approval_for_irreversible_actions(self):
        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            authority_mode="incident",
        )

        allowed, reason = policy.check("generate_deployment", {"environment": "production"})

        assert allowed is False
        assert "incident irreversible-action guard" in reason

    def test_mission_auto_escalation_mentions_matching_signal(self):
        from datetime import UTC, datetime

        from ds_agent.domain.entities.review_verdict import ReviewVerdict

        policy = PermissionPolicy(
            mode=PermissionMode.FULL_ACCESS,
            agent_mode="auto",
            mission="weekly-kpi-triage",
            mission_pack=self._mission_pack(
                auto_escalate_when=["confidence_low"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["artifact_draft"],
                },
            ),
            latest_review_verdict=ReviewVerdict.model_validate(
                {
                    "verdict_id": "RV-20260421002",
                    "task_id": "TC-2026-001",
                    "result": "warn",
                    "summary": "Confidence dropped below threshold.",
                    "created_at": datetime(2026, 4, 21, tzinfo=UTC),
                    "confidence": {
                        "score": 0.2,
                        "grade": "low",
                        "rationale": "Confidence dropped below threshold.",
                    },
                }
            ),
        )

        allowed, reason = policy.check(
            "write_file",
            {"file_path": "notes.md", "content": "ok", "data_domain": "growth"},
        )

        assert allowed is False
        assert "mission auto-escalation" in reason
        assert "confidence_low" in reason

    def test_get_tool_safety_known(self):
        assert get_tool_safety("data_loader") == ToolSafetyLevel.SAFE
        assert get_tool_safety("execute_code") == ToolSafetyLevel.CAUTION

    def test_get_tool_safety_unknown_defaults_caution(self):
        assert get_tool_safety("completely_unknown") == ToolSafetyLevel.CAUTION


# ---------------------------------------------------------------------------
# Built-in Hooks
# ---------------------------------------------------------------------------


class TestPermissionHook:
    @pytest.mark.asyncio
    async def test_auto_mode_allows_classified_local_write(self):
        hook = PermissionHook(PermissionPolicy(mode=PermissionMode.FULL_ACCESS))
        ctx = HookContext(mode="auto")
        result = await hook.pre_tool_use(
            "write_file",
            {"file_path": "notes.md", "content": "ok"},
            ctx,
        )
        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_auto_mode_requires_approval_for_generic_execute_code(self):
        hook = PermissionHook(PermissionPolicy(mode=PermissionMode.FULL_ACCESS))
        ctx = HookContext(mode="auto")
        result = await hook.pre_tool_use("execute_code", {"code": "print('hello')"}, ctx)
        assert result.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_supervised_mode_denies_caution(self):
        hook = PermissionHook(PermissionPolicy(mode=PermissionMode.FULL_ACCESS))
        ctx = HookContext(mode="supervised")
        result = await hook.pre_tool_use("train_model", {}, ctx)
        assert result.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_read_only_denies_writes(self):
        hook = PermissionHook(PermissionPolicy(mode=PermissionMode.READ_ONLY))
        ctx = HookContext(mode="auto")
        result = await hook.pre_tool_use("write_file", {}, ctx)
        assert result.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_policy_store_override_can_allow_delegate_jira(self, tmp_path):
        from ds_agent.runtime.policy_store import JsonPolicyStore

        store = JsonPolicyStore(base_dir=tmp_path)
        store.set_action_matrix_overrides({"jira_create": {"delegate": "auto"}})

        hook = PermissionHook(
            PermissionPolicy(mode=PermissionMode.FULL_ACCESS),
            policy_store=store,
        )
        ctx = HookContext(mode="auto")

        result = await hook.pre_tool_use("create_jira_ticket", {}, ctx)

        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_incident_overlay_in_context_overrides_contract_authority(self):
        class _TaskContractStore:
            @staticmethod
            def get_active_bundle(_session_id):
                from datetime import UTC, datetime

                from ds_agent.domain.entities.task_contract import TaskContract
                from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle

                return TaskContractBundle(
                    contract=TaskContract(
                        task_id="TC-2026-001",
                        session_id="session-1",
                        type="ops_triage",
                        business_goal="Triage KPI anomalies",
                        authority="delegate",
                        mission="weekly-kpi-triage",
                        required_deliverables=[
                            {"type": "exec_brief", "audience": "executive", "format": "md"}
                        ],
                        created_at=datetime(2026, 4, 15, tzinfo=UTC),
                        updated_at=datetime(2026, 4, 15, tzinfo=UTC),
                    )
                )

        hook = PermissionHook(
            PermissionPolicy(mode=PermissionMode.FULL_ACCESS),
            task_contract_store=_TaskContractStore(),
            mission_loader=MagicMock(),
        )
        hook._mission_loader.try_load.return_value = TestPermissionPolicy._mission_pack()
        ctx = HookContext(mode="auto", authority_mode="incident", session_id="session-1")

        result = await hook.pre_tool_use(
            "generate_deployment",
            {"environment": "production", "data_domain": "growth"},
            ctx,
        )

        assert result.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_latest_contract_verdict_flows_into_mission_auto_escalation(self):
        class _TaskContractStore:
            @staticmethod
            def get_active_bundle(_session_id):
                from datetime import UTC, datetime

                from ds_agent.domain.entities.review_verdict import ReviewVerdict
                from ds_agent.domain.entities.task_contract import TaskContract
                from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle

                return TaskContractBundle(
                    contract=TaskContract(
                        task_id="TC-2026-001",
                        session_id="session-1",
                        type="ops_triage",
                        business_goal="Triage KPI anomalies",
                        authority="delegate",
                        mission="weekly-kpi-triage",
                        required_deliverables=[
                            {"type": "exec_brief", "audience": "executive", "format": "md"}
                        ],
                        created_at=datetime(2026, 4, 15, tzinfo=UTC),
                        updated_at=datetime(2026, 4, 15, tzinfo=UTC),
                    ),
                    review_verdicts=[
                        ReviewVerdict.model_validate(
                            {
                                "verdict_id": "RV-20260421003",
                                "task_id": "TC-2026-001",
                                "result": "warn",
                                "summary": "Confidence dropped below threshold.",
                                "created_at": datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
                                "confidence": {
                                    "score": 0.2,
                                    "grade": "low",
                                    "rationale": "Confidence dropped below threshold.",
                                },
                            }
                        )
                    ],
                )

        hook = PermissionHook(
            PermissionPolicy(mode=PermissionMode.FULL_ACCESS),
            task_contract_store=_TaskContractStore(),
            mission_loader=MagicMock(),
        )
        hook._mission_loader.try_load.return_value = TestPermissionPolicy._mission_pack(
            auto_escalate_when=["confidence_low"],
            action_policy_overrides={},
            boundary={
                "allowed_data_domains": ["growth"],
                "required_semantic_metrics": [],
                "allowed_action_classes": ["artifact_draft"],
            },
        )
        ctx = HookContext(mode="auto", session_id="session-1")

        result = await hook.pre_tool_use(
            "write_file",
            {"file_path": "notes.md", "content": "ok", "data_domain": "growth"},
            ctx,
        )

        assert result.action == HookAction.DENY
        assert result.deny_reason is not None
        assert "mission auto-escalation" in result.deny_reason
        assert "confidence_low" in result.deny_reason


class TestBudgetGuardHook:
    @pytest.mark.asyncio
    async def test_allows_when_budget_ok(self):
        hook = BudgetGuardHook(max_cost_usd=10.0)
        ctx = HookContext(total_cost_usd=5.0)
        result = await hook.pre_tool_use("train_model", {}, ctx)
        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_denies_expensive_tool_at_critical(self):
        hook = BudgetGuardHook(max_cost_usd=10.0, critical_pct=95.0)
        ctx = HookContext(total_cost_usd=9.6)
        result = await hook.pre_tool_use("train_model", {}, ctx)
        assert result.action == HookAction.DENY
        assert "Budget critical" in result.deny_reason

    @pytest.mark.asyncio
    async def test_allows_cheap_tool_at_critical(self):
        hook = BudgetGuardHook(max_cost_usd=10.0)
        ctx = HookContext(total_cost_usd=9.6)
        result = await hook.pre_tool_use("data_loader", {}, ctx)
        assert result.action == HookAction.ALLOW


class TestExperimentTrackerHook:
    @pytest.mark.asyncio
    async def test_triggers_on_train_model_success(self):
        hook = ExperimentTrackerHook()
        ctx = HookContext()
        result = await hook.post_tool_use("train_model", {}, "metrics...", False, ctx)
        assert result.trigger_learning is True

    @pytest.mark.asyncio
    async def test_no_trigger_on_error(self):
        hook = ExperimentTrackerHook()
        ctx = HookContext()
        result = await hook.post_tool_use("train_model", {}, "error", True, ctx)
        assert result.trigger_learning is False

    @pytest.mark.asyncio
    async def test_no_trigger_on_untracked_tool(self):
        hook = ExperimentTrackerHook()
        ctx = HookContext()
        result = await hook.post_tool_use("data_loader", {}, "ok", False, ctx)
        assert result.trigger_learning is False


class TestSessionInitHook:
    @pytest.mark.asyncio
    async def test_returns_rules_text(self):
        hook = SessionInitHook()
        ctx = HookContext()
        text = await hook.on_session_init(ctx)
        assert text is not None
        assert "baseline" in text.lower()
        assert "leakage" in text.lower()
        assert "Safety" in text

    @pytest.mark.asyncio
    async def test_registry_run_session_init(self):
        registry = HookRegistry()
        registry.register(SessionInitHook())
        ctx = HookContext()
        injections = await registry.run_session_init(ctx)
        assert len(injections) == 1
        assert "DS Methodology" in injections[0]

    @pytest.mark.asyncio
    async def test_hook_base_returns_none(self):
        """Base ToolHook.on_session_init returns None by default."""
        hook = ToolHook()
        result = await hook.on_session_init(HookContext())
        assert result is None

    @pytest.mark.asyncio
    async def test_registry_filters_none(self):
        """Hooks returning None are excluded from injections list."""
        registry = HookRegistry()
        registry.register(ToolHook())  # returns None
        registry.register(SessionInitHook())  # returns text
        injections = await registry.run_session_init(HookContext())
        assert len(injections) == 1


class TestAuditLogHook:
    @pytest.mark.asyncio
    async def test_pre_and_post_return_allow(self, tmp_path):
        hook = AuditLogHook(log_path=tmp_path / "audit.jsonl")
        ctx = HookContext()
        pre = await hook.pre_tool_use("data_loader", {"file": "a.csv"}, ctx)
        assert pre.action == HookAction.ALLOW

        post = await hook.post_tool_use("data_loader", {}, "ok", False, ctx)
        assert post.modified_result is None

        # Check log file was written
        log_file = tmp_path / "audit.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2  # pre + post
