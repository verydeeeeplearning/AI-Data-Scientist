"""Composable system prompt builder (Claude Code pattern).

Assembles the system prompt from prioritized sections. When the token
budget is tight, lower-priority sections are dropped automatically.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Protocol

from ds_agent.agent.prompt_sections import (
    CORE_IDENTITY,
    OUTPUT_FORMAT,
    QUALITY_PRINCIPLES,
    SAFETY,
    build_audience_section,
    build_authority_section,
    build_missing_mission_section,
    build_mission_section,
    task_contract_section,
)
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode

if TYPE_CHECKING:
    from ds_agent.domain.entities.mission_pack import MissionPack
    from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
    from ds_agent.domain.interfaces.session_state import GoalStore, WorkingMemoryStore
    from ds_agent.domain.interfaces.task_contract import TaskContractStore


@dataclass(frozen=True)
class PromptSection:
    """One composable section of the system prompt."""

    name: str
    content: str
    priority: int  # lower = more important, dropped last
    token_estimate: int = 0  # 0 → auto-estimate
    required: bool = False  # required sections are never dropped

    def estimated_tokens(self) -> int:
        if self.token_estimate > 0:
            return self.token_estimate
        return max(1, len(self.content) // 4)


# ---------------------------------------------------------------------------
# Legacy constant kept for backward-compat in tests that import it directly.
# ---------------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = CORE_IDENTITY + "\n\n" + QUALITY_PRINCIPLES

_STAGE_RULES: dict[AnalysisStage, tuple[str, ...]] = {
    AnalysisStage.SCOPING: (
        (
            "Clarify the business decision, success metric, and Definition of Done "
            "before deeper analysis."
        ),
        (
            "Identify the baseline the work must beat instead of assuming modeling "
            "is already justified."
        ),
        "Record key constraints early: data access, privacy, deadline, and delivery format.",
    ),
    AnalysisStage.DATA_LOADING: (
        "Verify data source scope, freshness, and basic lineage before trusting the inputs.",
        "Surface privacy, access, or schema ambiguity as a blocker instead of guessing through it.",
        (
            "Do not proceed as if the dataset is analysis-ready until loading "
            "assumptions are explicit."
        ),
    ),
    AnalysisStage.PROFILING: (
        (
            "Quantify shape, missingness, schema defects, and obvious outliers "
            "before hypothesis-building."
        ),
        "Promote the highest-risk data quality issues into explicit blockers or follow-up checks.",
        (
            "Record the strongest candidate explanations worth testing in EDA "
            "rather than free-form exploration."
        ),
    ),
    AnalysisStage.EDA: (
        "Prefer hypothesis-driven exploration over broad fishing expeditions.",
        "Document which relationships, anomalies, or segments changed the working hypothesis.",
        "Keep leakage risk and business plausibility in view while interpreting patterns.",
    ),
    AnalysisStage.FEATURE_ENG: (
        (
            "Fit transforms on train-only data and treat target or future "
            "information as leakage by default."
        ),
        "Document why each transformation should improve signal, not just model convenience.",
        (
            "Preserve a path back to simple features so feature additions can be "
            "justified against a baseline."
        ),
    ),
    AnalysisStage.MODELING: (
        "Establish and record a simple baseline before trusting more complex models.",
        "Choose a validation strategy that matches the data shape and leakage risks.",
        "Compare a small set of credible candidates and track both quality and operational cost.",
    ),
    AnalysisStage.EVALUATION: (
        "Use untouched holdout evidence for final claims instead of reusing tuning feedback.",
        "Translate model metrics into business risk, error modes, and decision readiness.",
        "Include uncertainty or confidence framing when the evidence is narrow or unstable.",
    ),
    AnalysisStage.REPORTING: (
        (
            "Lead with the decision, impact, and risk instead of replaying the "
            "full analysis chronology."
        ),
        "Make recommendations actionable by naming the next step, owner, or unresolved blocker.",
        "State assumptions, limitations, and follow-up questions explicitly.",
    ),
}

_STAGE_TO_SKILLS: dict[AnalysisStage, tuple[str, ...]] = {
    AnalysisStage.SCOPING: ("scoping",),
    AnalysisStage.DATA_LOADING: (),
    AnalysisStage.PROFILING: ("data-profiling",),
    AnalysisStage.EDA: ("eda",),
    AnalysisStage.FEATURE_ENG: ("feature-engineering",),
    AnalysisStage.MODELING: ("modeling",),
    AnalysisStage.EVALUATION: ("evaluation",),
    AnalysisStage.REPORTING: ("reporting",),
}


class MissionPackLoaderLike(Protocol):
    """Minimal protocol for loading one active mission pack."""

    def load(self, name: str) -> MissionPack: ...

    def try_load(self, name: str) -> MissionPack | None: ...


class PromptBuilder:
    """Assembles the system prompt dynamically from prioritized sections.

    Sections are sorted by priority (lower = more important).  When the
    combined token estimate exceeds *max_system_tokens*, the builder drops
    the least-important (highest-priority number) optional sections first.
    """

    def __init__(
        self,
        system_prompt_override: str | None = None,
        skill_names: list[str] | None = None,
        skill_hub: object | None = None,
        memory_hints: str | None = None,
        project_context: str | None = None,
        use_case_hint: str | None = None,
        use_case_context: str | None = None,
        tool_registry: object | None = None,
        model_name: str | None = None,
        workspace_dir: str | None = None,
        session_id: str | None = None,
        goal_store: GoalStore | None = None,
        working_memory_store: WorkingMemoryStore | None = None,
        task_contract_store: TaskContractStore | None = None,
        max_system_tokens: int = 8000,
        language: str | None = None,
        legacy_agent_mode: str | None = None,
        authority_mode: AuthorityMode | str | None = None,
        audience_persona: AudiencePersona | str | None = None,
        mission_loader: MissionPackLoaderLike | None = None,
    ) -> None:
        self._override = system_prompt_override
        self._skill_names: list[str] = skill_names or []
        self._skill_hub = skill_hub
        self._memory_hints = memory_hints or ""
        self._project_context = project_context or ""
        self._use_case_hint = use_case_hint
        self._use_case_context = use_case_context or ""
        self._tool_registry = tool_registry
        self._model_name = model_name
        self._workspace_dir = workspace_dir
        self._session_id = session_id
        self._goal_store = goal_store
        self._working_memory_store = working_memory_store
        self._task_contract_store = task_contract_store
        self._max_tokens = max_system_tokens
        self._language = language
        self._legacy_agent_mode = legacy_agent_mode
        self._authority_mode = authority_mode
        self._audience_persona = audience_persona
        self._mission_loader = mission_loader

    # -- public API ----------------------------------------------------------

    def build(
        self,
        user_message: str,
        history: list[ChatMessage] | None = None,
    ) -> list[ChatMessage]:
        """Build full message list: system + history + user message."""
        messages: list[ChatMessage] = [self.build_system_message()]
        if history:
            messages.extend(history)
        messages.append(ChatMessage(role=Role.USER, content=user_message))
        return messages

    def build_system_message(self) -> ChatMessage:
        """Build the current system message only.

        This allows the agent loop to refresh the system prompt when session
        state changes mid-run without rebuilding the entire conversation list.
        """
        return ChatMessage(role=Role.SYSTEM, content=self._build_system_content())

    # -- internal assembly ---------------------------------------------------

    def _build_system_content(self) -> str:
        if self._override:
            return self._override

        sections = self._collect_sections()
        return self._assemble(sections)

    def _collect_sections(self) -> list[PromptSection]:
        active_contract_bundle = self._get_active_task_contract_bundle()
        active_mission_pack = self._get_active_mission_pack(active_contract_bundle)
        working_memory = self._load_working_memory()
        current_stage = None if working_memory is None else working_memory.current_stage

        # Upfront sections: always present (core context)
        sections: list[PromptSection] = [
            PromptSection("identity", CORE_IDENTITY, priority=0, required=True),
            PromptSection(
                "authority",
                build_authority_section(
                    self._resolve_authority_mode(active_contract_bundle, active_mission_pack)
                ),
                priority=1,
                required=True,
            ),
            PromptSection(
                "audience",
                build_audience_section(
                    self._resolve_audience_persona(active_contract_bundle, active_mission_pack)
                ),
                priority=2,
                required=True,
            ),
            PromptSection("environment", self._build_environment(), priority=3, required=True),
            PromptSection("workspace", self._build_workspace_section(), priority=3, required=True),
            PromptSection("quality", QUALITY_PRINCIPLES, priority=4),
            PromptSection("safety", SAFETY, priority=5),
            PromptSection("output_format", OUTPUT_FORMAT, priority=6),
        ]

        # P1-13: user-preferred output language. Forced section so the
        # directive survives token trimming.
        language_section = self._build_language_section()
        if language_section:
            sections.append(PromptSection("language", language_section, priority=3, required=True))

        # On-demand sections: loaded only when relevant, higher priority numbers
        # so they are dropped first when token budget is tight.
        # Tool guides are on-demand — individual tool prompts are available
        # when the agent calls a tool, so the full guide is low priority.
        mission_context = self._build_mission_context(active_contract_bundle, active_mission_pack)
        if mission_context:
            sections.append(PromptSection("mission", mission_context, priority=3, required=True))

        stage_guidance = self._build_stage_guidance(current_stage)
        if stage_guidance:
            sections.append(
                PromptSection(
                    "stage_guidance",
                    stage_guidance,
                    priority=4,
                    required=True,
                )
            )

        tool_guides = self._build_tool_guides()
        if tool_guides:
            sections.append(PromptSection("tool_guides", tool_guides, priority=7))

        # Skills come from the active session set plus any mission-required additions.
        skill_content = self._build_skill_content(active_mission_pack, current_stage=current_stage)
        if skill_content:
            sections.append(PromptSection("skills", skill_content, priority=6))

        if self._memory_hints:
            sections.append(
                PromptSection("memory", f"# Memory Context\n{self._memory_hints}", priority=5)
            )

        if self._project_context:
            sections.append(
                PromptSection("project", f"# Project Context\n{self._project_context}", priority=8)
            )

        use_case_context = self._build_use_case_context()
        if use_case_context:
            sections.append(PromptSection("use_case", use_case_context, priority=5))

        continuity_context = self._build_execution_continuity_context(working_memory)
        if continuity_context:
            sections.append(
                PromptSection(
                    "execution_continuity",
                    continuity_context,
                    priority=4,
                    required=True,
                )
            )

        goal_context = self._build_goal_context()
        if goal_context:
            sections.append(PromptSection("goal", goal_context, priority=5))

        task_contract_context = self._build_task_contract_context(active_contract_bundle)
        if task_contract_context:
            sections.append(PromptSection("task_contract", task_contract_context, priority=5))

        working_memory_context = self._build_working_memory_context(working_memory)
        if working_memory_context:
            sections.append(PromptSection("working_memory", working_memory_context, priority=6))

        verifier_remediation_context = self._build_verifier_remediation_context(working_memory)
        if verifier_remediation_context:
            sections.append(
                PromptSection(
                    "verifier_remediation",
                    verifier_remediation_context,
                    priority=4,
                    required=True,
                )
            )

        # DS_METHODOLOGY removed from system prompt — its content is now
        # covered by SessionInitHook (forced injection) and skill files
        # (on-demand per stage). This saves ~200 tokens per session.

        portfolio_section = self._build_portfolio_context()
        if portfolio_section:
            sections.append(PromptSection("portfolio", portfolio_section, priority=7))

        learning_section = self._build_learning_governance_context()
        if learning_section:
            sections.append(PromptSection("learning_governance", learning_section, priority=8))

        return sections

    def _resolve_authority_mode(
        self,
        bundle: TaskContractBundle | None = None,
        mission_pack: MissionPack | None = None,
    ) -> AuthorityMode:
        if self._overlay_authority_mode is not None:
            return self._overlay_authority_mode
        if bundle is not None and bundle.contract.authority is not None:
            return bundle.contract.authority
        if self._authority_mode is not None:
            return AuthorityMode.coerce(self._authority_mode)
        if mission_pack is not None and mission_pack.authority_default is not None:
            return mission_pack.authority_default
        return AuthorityMode.from_legacy_agent_mode(self._legacy_agent_mode)

    @property
    def _overlay_authority_mode(self) -> AuthorityMode | None:
        if self._authority_mode is None:
            return None
        resolved = AuthorityMode.coerce(self._authority_mode)
        if resolved in {AuthorityMode.INCIDENT, AuthorityMode.FREEZE}:
            return resolved
        return None

    def _build_portfolio_context(self) -> str | None:
        """Build portfolio status section if the feature is enabled."""
        import os

        if os.environ.get("DS_AGENT_PORTFOLIO_ENABLED", "").lower() not in {"1", "true", "yes"}:
            return None
        try:
            from ds_agent.agent.prompt_sections import build_portfolio_section
            from ds_agent.application.portfolio.portfolio_evaluator import PortfolioEvaluator
            from ds_agent.application.portfolio.priority_calculator import PriorityCalculator
            from ds_agent.application.portfolio.slot_manager import SlotManager
            from ds_agent.application.portfolio.wait_condition_evaluator import (
                WaitConditionEvaluator,
            )
            from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore
            from ds_agent.infrastructure.work_object_container import SystemClock

            store = SqlitePortfolioStore.for_workspace(self._workspace_dir)
            clock = SystemClock()
            evaluator = PortfolioEvaluator(
                store=store,
                slot_manager=SlotManager(store),
                condition_evaluator=WaitConditionEvaluator(clock),
                priority_calculator=PriorityCalculator(clock),
            )
            return build_portfolio_section(evaluator.evaluate())
        except Exception:
            return None

    def _build_learning_governance_context(self) -> str | None:
        """Build learning governance status section if enabled."""
        import os

        if os.environ.get(
            "DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1",
            "",
        ).lower() not in {"1", "true", "yes"}:
            return None
        try:
            from ds_agent.application.learning.learning_inbox import LearningInboxUseCase
            from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
            from ds_agent.infrastructure.work_object_container import SystemClock

            store = SqliteLearningStore.for_workspace(self._workspace_dir)
            uc = LearningInboxUseCase(store=store, clock=SystemClock())
            items = uc.execute(limit=5)
            if not items:
                return None
            lines = [
                "# Learning Governance",
                f"{len(items)} items pending review:",
            ]
            for si in items[:5]:
                lines.append(
                    f"- [{si.item.item_type.value}] {si.item.title} "
                    f"(score: {si.priority_score:.2f})",
                )
            return "\n".join(lines)
        except Exception:
            return None

    def _resolve_audience_persona(
        self,
        bundle: TaskContractBundle | None = None,
        mission_pack: MissionPack | None = None,
    ) -> AudiencePersona:
        if bundle is not None and bundle.contract.audience is not None:
            return bundle.contract.audience
        if self._audience_persona is not None:
            return AudiencePersona.coerce(self._audience_persona)
        if mission_pack is not None and mission_pack.audience_default is not None:
            return mission_pack.audience_default
        return AudiencePersona.from_legacy_agent_mode(self._legacy_agent_mode)

    def _assemble(self, sections: list[PromptSection]) -> str:
        """Priority-based assembly with budget enforcement."""
        required = [s for s in sections if s.required]
        optional = sorted(
            [s for s in sections if not s.required],
            key=lambda s: s.priority,
        )

        total = sum(s.estimated_tokens() for s in required)
        included: list[PromptSection] = list(required)

        for section in optional:
            est = section.estimated_tokens()
            if total + est <= self._max_tokens:
                included.append(section)
                total += est

        included.sort(key=lambda s: s.priority)
        return "\n\n".join(s.content for s in included)

    # -- section builders ----------------------------------------------------

    _LANGUAGE_INSTRUCTIONS: ClassVar[dict[str, str]] = {
        "ko": (
            "# Response Language\n"
            "모든 사용자 응답은 한국어로 작성하세요. 변수명과 "
            "코드는 영문을 유지하고, 사용자용 설명·분석·결론·주석은 한국어로."
        ),
        "en": ("# Response Language\nRespond to the user in English."),
        "ja": (
            "# Response Language\n"
            "ユーザーへの応答はすべて日本語で書いてください。コード内の識別子は英語で可。"
        ),
    }

    def _build_language_section(self) -> str:
        if not self._language:
            return ""
        return self._LANGUAGE_INSTRUCTIONS.get(self._language, "")

    @staticmethod
    def _build_environment() -> str:
        return (
            "# Environment\n"
            f"- Platform: {sys.platform}\n"
            f"- Python: {platform.python_version()}\n"
            f"- Date: {datetime.now().strftime('%Y-%m-%d')}"
        )

    def _build_workspace_section(self) -> str:
        """Inject absolute workspace path + existing file listing.

        Without this, the agent defaults to guessing relative paths like ``.``
        or ``./data`` which resolve to the Python process CWD (outside the
        workspace boundary) and trigger an instant "Access denied" error from
        ``list_files``. The agent then has no choice but to ask the user for
        a path.
        """
        lines: list[str] = ["# Workspace"]
        if not self._workspace_dir:
            lines.append("- No workspace configured. Ask the user for file paths.")
            return "\n".join(lines)

        ws = Path(self._workspace_dir).expanduser().resolve()
        lines.append(f"- Absolute path: `{ws}`")
        lines.append("- ALL file operations must use absolute paths inside this directory.")
        lines.append(
            "- Do NOT use relative paths like `.`, `./data`, or `~/` — they "
            "resolve outside the workspace and will be rejected."
        )

        # Pre-scan the workspace so the agent knows what's already there.
        try:
            if ws.exists():
                entries = sorted(ws.iterdir(), key=lambda p: p.name)
                files = [p for p in entries if p.is_file()]
                subdirs = [p for p in entries if p.is_dir()]
                if files or subdirs:
                    lines.append("")
                    lines.append("## Existing files")
                    for f in files[:40]:
                        try:
                            size = f.stat().st_size
                            lines.append(f"- `{f.name}` ({size:,} bytes)")
                        except OSError:
                            lines.append(f"- `{f.name}`")
                    if len(files) > 40:
                        lines.append(f"- ... and {len(files) - 40} more files")
                    for d in subdirs[:10]:
                        lines.append(f"- `{d.name}/` (directory)")
                else:
                    lines.append("")
                    lines.append("## Existing files: (empty workspace)")
        except OSError:
            pass

        return "\n".join(lines)

    def _build_tool_guides(self) -> str:
        if not self._tool_registry:
            return ""

        guides: list[str] = []
        entries = _iter_tool_entries(self._tool_registry)
        for entry in entries:
            prompt = getattr(entry, "prompt", None)
            if prompt:
                guides.append(f"## {entry.name}\n{prompt}")

        if not guides:
            return ""
        return "# Tool Usage Guides\n\n" + "\n\n".join(guides)

    def _build_stage_guidance(self, current_stage: AnalysisStage | None) -> str:
        if current_stage is None:
            return ""

        rules = _STAGE_RULES.get(current_stage, ())
        prioritized_skills = _STAGE_TO_SKILLS.get(current_stage, ())
        if not rules and not prioritized_skills:
            return ""

        parts = [
            "# Stage-Aware Guidance",
            f"- Current stage: {current_stage.value}",
            "- Apply these guardrails to the next concrete action:",
        ]
        for rule in rules:
            parts.append(f"- {rule}")
        if prioritized_skills:
            preferred = ", ".join(f"`{name}`" for name in prioritized_skills)
            parts.append(f"- Prioritize these skills right now: {preferred}")
        return "\n".join(parts)

    def _build_skill_content(
        self,
        mission_pack: MissionPack | None = None,
        *,
        current_stage: AnalysisStage | None = None,
    ) -> str:
        skill_names = list(self._skill_names)
        if mission_pack is not None:
            skill_names.extend(mission_pack.skills_required)
        if current_stage is not None:
            skill_names = [*_STAGE_TO_SKILLS.get(current_stage, ()), *skill_names]
        skill_names = list(dict.fromkeys(skill_names))
        if self._skill_hub and hasattr(self._skill_hub, "get_enabled_prompt_skill_names"):
            skill_names = self._skill_hub.get_enabled_prompt_skill_names(skill_names)

        if not skill_names:
            return ""

        if self._skill_hub and hasattr(self._skill_hub, "get_skills_for_prompt"):
            content = self._skill_hub.get_skills_for_prompt(skill_names)
            if content:
                return f"# Active Skills\n{content}"

        if self._skill_hub and hasattr(self._skill_hub, "view_skill"):
            parts = ["# Active Skills"]
            for name in skill_names:
                skill = self._skill_hub.view_skill(name)
                if skill:
                    metadata_lines = []
                    tools = skill.get("tools", [])
                    permissions = skill.get("permissions", {})
                    if tools:
                        metadata_lines.append(
                            f"- Allowed tools: {', '.join(str(item) for item in tools)}"
                        )
                    network = (
                        permissions.get("network", []) if isinstance(permissions, dict) else []
                    )
                    if network:
                        metadata_lines.append(
                            f"- Network allowlist: {', '.join(str(item) for item in network)}"
                        )
                    prefix = "\n".join(metadata_lines)
                    if prefix:
                        parts.append(f"## {name}\n{prefix}\n\n{skill.get('content', '')}")
                    else:
                        parts.append(f"## {name}\n{skill.get('content', '')}")
            if len(parts) > 1:
                return "\n\n".join(parts)

        # Fallback: just list names (backward compat)
        skill_list = ", ".join(f'skill_view("{s}")' for s in skill_names)
        return f"# Available Skills\nView detailed methodology with: {skill_list}"

    def _build_goal_context(self) -> str:
        if not self._session_id or self._goal_store is None:
            return ""

        goal = self._goal_store.get_active_goal(self._session_id)
        if goal is None:
            return ""

        parts = [
            "# Active Goal",
            f"- Goal: {goal.summary}",
            f"- Status: {goal.status.value}",
        ]
        if goal.last_run_id:
            parts.append(f"- Last run: {goal.last_run_id}")
        if goal.blocked_reason:
            parts.append(f"- Blocker: {goal.blocked_reason}")
        if goal.notes:
            parts.append(f"- Recent note: {goal.notes[-1]}")
        return "\n".join(parts)

    def _load_working_memory(self):
        if not self._session_id or self._working_memory_store is None:
            return None
        return self._working_memory_store.load(self._session_id)

    def _build_execution_continuity_context(self, memory=None) -> str:
        if not self._session_id:
            return ""

        goal = None
        if self._goal_store is not None:
            goal = self._goal_store.get_active_goal(self._session_id)

        if memory is None:
            memory = self._load_working_memory()

        current_stage = None if memory is None else memory.current_stage
        blocker = None
        if goal is not None and goal.blocked_reason:
            blocker = goal.blocked_reason
        elif memory is not None and memory.pending_questions:
            blocker = memory.pending_questions[0]

        next_step = None if memory is None else memory.next_step
        recovery_note = None if memory is None else memory.recovery_note

        if not any(
            [
                current_stage is not None,
                blocker,
                next_step,
                recovery_note,
            ]
        ):
            return ""

        parts = ["# Execution Continuity"]
        if current_stage is not None:
            parts.append(f"- Current stage: {current_stage.value}")
        if blocker:
            parts.append(f"- Active blocker: {blocker}")
        if next_step:
            parts.append(f"- Next step: {next_step}")
        if recovery_note:
            parts.append(f"- Recovery state: {recovery_note}")
        return "\n".join(parts)

    def _get_active_task_contract_bundle(self) -> TaskContractBundle | None:
        if not self._session_id or self._task_contract_store is None:
            return None

        return self._task_contract_store.get_active_bundle(self._session_id)

    @staticmethod
    def _resolve_mission_name(bundle: TaskContractBundle | None) -> str | None:
        if bundle is None:
            return None
        return bundle.contract.mission

    def _get_active_mission_pack(self, bundle: TaskContractBundle | None) -> MissionPack | None:
        mission_name = self._resolve_mission_name(bundle)
        if not mission_name or self._mission_loader is None:
            return None
        return self._mission_loader.try_load(mission_name)

    def _build_task_contract_context(
        self,
        bundle: TaskContractBundle | None,
    ) -> str:
        if not self._session_id or self._task_contract_store is None:
            return task_contract_section(None)
        return task_contract_section(bundle)

    def _build_mission_context(
        self,
        bundle: TaskContractBundle | None,
        mission_pack: MissionPack | None,
    ) -> str:
        if mission_pack is not None:
            return build_mission_section(mission_pack)

        mission_name = self._resolve_mission_name(bundle)
        if mission_name:
            return build_missing_mission_section(mission_name)
        return ""

    def _build_working_memory_context(self, memory=None) -> str:
        if memory is None:
            memory = self._load_working_memory()
        if memory is None:
            return ""

        parts = ["# Working Memory"]
        if memory.current_summary:
            parts.append(f"- Summary: {memory.current_summary}")
        if memory.current_stage is not None:
            parts.append(f"- Current stage: {memory.current_stage.value}")
        if memory.next_step:
            parts.append(f"- Next step: {memory.next_step}")
        if memory.last_reflection:
            parts.append(f"- Reflection: {memory.last_reflection}")
        if memory.recovery_note:
            parts.append(f"- Recovery: {memory.recovery_note}")
        if memory.pending_questions:
            parts.append("- Pending questions:")
            for question in memory.pending_questions[:3]:
                parts.append(f"  - {question}")
        if len(parts) == 1:
            return ""
        return "\n".join(parts)

    def _build_verifier_remediation_context(self, memory=None) -> str:
        """Inject pending verifier remediation findings into the next-turn prompt.

        If the previous turn's verifier result was fail/warn and the remediation
        payload was stored in working memory, surface the issues and recommended
        actions so the agent can address them without the operator needing to
        re-state the problem.
        """
        if memory is None:
            memory = self._load_working_memory()
        if memory is None:
            return ""
        remediation = getattr(memory, "pending_verifier_remediation", None)
        if not remediation:
            return ""

        parts = [
            "## Pending Verifier Remediation",
            (
                "The previous response had verifier findings that need to be addressed "
                "before this task can progress:"
            ),
        ]
        for item in remediation[:10]:
            if not isinstance(item, dict):
                continue
            severity = item.get("severity", "")
            message = item.get("message", "")
            blocking = item.get("blocking", False)
            flag = " [BLOCKING]" if blocking else ""
            if message:
                parts.append(f"- [{severity}]{flag} {message}")

        actions = [
            a
            for a in (remediation[0].get("recommendedActions", []) if remediation else [])
            if isinstance(a, dict)
        ]
        if actions:
            parts.append("Recommended actions:")
            for action in actions[:5]:
                title = action.get("title", "")
                description = action.get("description", "")
                if title:
                    parts.append(f"- {title}: {description}" if description else f"- {title}")
        return "\n".join(parts)

    def _build_use_case_context(self) -> str:
        if not self._use_case_hint and not self._use_case_context:
            return ""

        parts = [
            "# Use-Case Context",
            (
                "- This guidance comes from onboarding. Tailor language, examples, "
                "and deliverables to it."
            ),
            (
                "- Do not treat this as a hard-coded workflow branch. Stay "
                "autonomous and adapt to the actual task."
            ),
        ]
        if self._use_case_hint:
            parts.append(
                f"- Selected use case: {self._humanize_use_case_hint(self._use_case_hint)}"
            )
        if self._use_case_context:
            parts.append(f"- Guidance: {self._use_case_context}")
        return "\n".join(parts)

    @staticmethod
    def _humanize_use_case_hint(value: str) -> str:
        return value.replace("_", " ").replace("-", " ").strip().title()


def _iter_tool_entries(registry: object) -> list:
    """Safely iterate tool entries from a ToolRegistry."""
    tools_dict = getattr(registry, "_tools", None)
    if tools_dict and isinstance(tools_dict, dict):
        return list(tools_dict.values())
    return []
