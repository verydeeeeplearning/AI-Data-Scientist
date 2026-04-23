"""Permission framework for tool-level access control."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.interfaces.certification import CertificationStore
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.action_classifier import ActionCandidate, ActionClassifier
from ds_agent.runtime.action_matrix import ActionMatrix
from ds_agent.runtime.autonomy_policy import AutonomyPolicy


class PermissionMode(StrEnum):
    """Workspace permission level."""

    READ_ONLY = "read_only"
    WORKSPACE = "workspace"
    FULL_ACCESS = "full_access"


class ToolSafetyLevel(StrEnum):
    """Tool danger classification."""

    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


TOOL_SAFETY_MAP: dict[str, ToolSafetyLevel] = {
    "data_loader": ToolSafetyLevel.SAFE,
    "data_profiler": ToolSafetyLevel.SAFE,
    "run_eda": ToolSafetyLevel.SAFE,
    "evaluate_model": ToolSafetyLevel.SAFE,
    "generate_report": ToolSafetyLevel.SAFE,
    "read_file": ToolSafetyLevel.SAFE,
    "list_files": ToolSafetyLevel.SAFE,
    "web_search": ToolSafetyLevel.SAFE,
    "drift_monitor": ToolSafetyLevel.SAFE,
    "ab_test": ToolSafetyLevel.SAFE,
    "skill_list": ToolSafetyLevel.SAFE,
    "skill_view": ToolSafetyLevel.SAFE,
    "skill_search": ToolSafetyLevel.SAFE,
    "memory_search": ToolSafetyLevel.SAFE,
    "memory_store": ToolSafetyLevel.SAFE,
    "ask_user": ToolSafetyLevel.SAFE,
    "policy_check": ToolSafetyLevel.SAFE,
    "lineage_capture": ToolSafetyLevel.SAFE,
    "notebook_generate": ToolSafetyLevel.SAFE,
    "slide_generate": ToolSafetyLevel.SAFE,
    "dashboard_spec": ToolSafetyLevel.SAFE,
    "execute_code": ToolSafetyLevel.CAUTION,
    "train_model": ToolSafetyLevel.CAUTION,
    "feature_engineer": ToolSafetyLevel.CAUTION,
    "distributed_exec": ToolSafetyLevel.CAUTION,
    "write_file": ToolSafetyLevel.CAUTION,
    "generate_deployment": ToolSafetyLevel.CAUTION,
    "send_to_slack": ToolSafetyLevel.CAUTION,
    "publish_confluence_page": ToolSafetyLevel.CAUTION,
    "publish_notion_page": ToolSafetyLevel.CAUTION,
    "create_jira_ticket": ToolSafetyLevel.CAUTION,
    "open_git_pr": ToolSafetyLevel.CAUTION,
    "create_git_pr": ToolSafetyLevel.CAUTION,
    "send_email": ToolSafetyLevel.CAUTION,
    "create_calendar_event": ToolSafetyLevel.CAUTION,
    "list_my_portfolio": ToolSafetyLevel.SAFE,
    "pause_task": ToolSafetyLevel.CAUTION,
    "resume_task": ToolSafetyLevel.CAUTION,
    "set_sla": ToolSafetyLevel.CAUTION,
    "request_monitoring": ToolSafetyLevel.CAUTION,
    "list_learning_inbox": ToolSafetyLevel.SAFE,
    "review_learning_item": ToolSafetyLevel.CAUTION,
    "get_learning_item": ToolSafetyLevel.SAFE,
    "list_promotions": ToolSafetyLevel.SAFE,
    "list_deprecations": ToolSafetyLevel.SAFE,
    "rollback_promotion": ToolSafetyLevel.CAUTION,
}


def get_tool_safety(tool_name: str) -> ToolSafetyLevel:
    """Look up safety level, defaulting to CAUTION for unknown tools."""
    return TOOL_SAFETY_MAP.get(tool_name, ToolSafetyLevel.CAUTION)


@dataclass(frozen=True)
class PermissionPolicy:
    """Determines whether a tool call is allowed."""

    mode: PermissionMode = PermissionMode.FULL_ACCESS
    agent_mode: str = "auto"
    denied_tools: frozenset[str] = frozenset()
    authority_mode: AuthorityMode | str | None = None
    audience_persona: AudiencePersona | str | None = None
    mission: str | None = None
    mission_pack: MissionPack | None = None
    latest_review_verdict: ReviewVerdict | None = None
    certification_store: CertificationStore | None = None
    action_matrix: ActionMatrix | None = None

    def check(
        self,
        tool_name: str,
        arguments: Mapping[str, object] | None = None,
    ) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        if tool_name in self.denied_tools:
            return False, f"Tool '{tool_name}' is explicitly denied"

        safety = get_tool_safety(tool_name)

        if self.mode == PermissionMode.READ_ONLY and safety != ToolSafetyLevel.SAFE:
            return False, f"Read-only mode: '{tool_name}' ({safety.value}) not allowed"

        classified = ActionClassifier().classify(
            ActionCandidate(tool_name=tool_name, arguments=dict(arguments or {}))
        )
        decision = AutonomyPolicy(
            matrix=self.action_matrix,
            certification_store=self.certification_store,
        ).evaluate(
            action_is_safe=safety == ToolSafetyLevel.SAFE,
            action_class=classified,
            action_arguments=dict(arguments or {}),
            authority=self.authority_mode,
            audience=self.audience_persona,
            mission=self.mission,
            mission_pack=self.mission_pack,
            latest_review_verdict=self.latest_review_verdict,
            legacy_mode=self.agent_mode,
        )
        if decision.blocked:
            if decision.reason == "freeze_mode_blocks_writes":
                return False, f"Freeze mode: '{tool_name}' blocks write side effects"
            return (
                False,
                (
                    f"{decision.context.authority.value.title()} mode: "
                    f"'{tool_name}' blocked by autonomy policy"
                ),
            )
        if decision.requires_approval:
            label = _legacy_mode_label(self.agent_mode, decision.context.authority.value)
            if decision.reason == "missing_certification":
                return (
                    False,
                    (
                        f"{label} mode: '{tool_name}' requires approval "
                        "(missing mission certification)"
                    ),
                )
            if decision.reason == "mission_boundary_out_of_scope":
                return (
                    False,
                    (f"{label} mode: '{tool_name}' requires approval (outside mission boundary)"),
                )
            if decision.reason == "incident_still_requires_approval_for_irreversible":
                return (
                    False,
                    (
                        f"{label} mode: '{tool_name}' requires approval "
                        "(incident irreversible-action guard)"
                    ),
                )
            if decision.reason == "mission_auto_escalation_triggered":
                signals = ", ".join(decision.escalation_signals) or "matched signal"
                return (
                    False,
                    (
                        f"{label} mode: '{tool_name}' requires approval "
                        f"(mission auto-escalation: {signals})"
                    ),
                )
            return False, f"{label} mode: '{tool_name}' requires approval"

        return True, ""


def _legacy_mode_label(value: str, fallback: str) -> str:
    normalized = str(value).strip().lower().replace("_", "-")
    if normalized == "auto":
        return fallback.replace("_", " ").title()
    if normalized == "step-by-step":
        return "Step-by-step"
    if normalized == "supervised":
        return "Supervised"
    if normalized:
        return normalized.replace("-", " ").title()
    return fallback.replace("_", " ").title()
