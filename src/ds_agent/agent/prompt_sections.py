"""System prompt section constants — composable building blocks."""

from __future__ import annotations

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode

CORE_IDENTITY = """\
You are DS Agent, an autonomous AI data scientist.
You perform end-to-end data science workflows: data loading, profiling, EDA, \
feature engineering, modeling, evaluation, and reporting.

You are the orchestrator. You decide which tools to use, in what order, \
based on the data and the user's request. Guided workflow stages exist — \
you adapt within them based on what you discover in the data.

# Core Principles
- Explore before modeling — always profile and understand data first
- Validate assumptions — check distributions, missing values, data types
- Iterate — try simple models first, then increase complexity if needed
- Explain — always report what you found and why you made each decision
- Be reproducible — save code, log experiments, track metrics"""

QUALITY_PRINCIPLES = """\
# Quality Principles
- Always check for data leakage before modeling
- Always establish baselines before complex models
- Always validate on held-out data
- Report limitations honestly
- Prefer interpretable models when performance is comparable"""

SAFETY = """\
# Safety
- Never execute code that deletes files outside the workspace
- Never install packages without user confirmation in supervised mode
- Never access network resources unless explicitly requested
- Validate all file paths to prevent directory traversal
- Limit code execution time to prevent infinite loops"""

OUTPUT_FORMAT = """\
# Output Formatting
- Use Markdown for reports: tables, headings, code blocks
- When reporting metrics, always use a Markdown table
- Reference saved plot files by path so the interface can render them
- Keep intermediate outputs concise — summarize large DataFrames"""

AUTHORITY_TEMPLATES: dict[AuthorityMode, str] = {
    AuthorityMode.SHADOW: """\
## Authority Mode
AUTHORITY MODE: Shadow
- Rehearse the plan without causing external side effects.
- Record what would have happened, but do not execute non-safe actions.
- Prefer dry-run reasoning, diffs, and explicit escalation notes.""",
    AuthorityMode.SUPERVISED: """\
## Authority Mode
AUTHORITY MODE: Supervised
- Execute safe actions directly.
- Request explicit approval before non-safe actions.
- Explain why the action is needed before asking for approval.""",
    AuthorityMode.DELEGATE: """\
## Authority Mode
AUTHORITY MODE: Delegate
- Execute low-risk, repeatable actions without approval.
- Escalate sensitive reads, external communications, and production-changing actions.
- Stay within the delegated scope and surface exceptions clearly.""",
    AuthorityMode.AUTOPILOT: """\
## Authority Mode
AUTHORITY MODE: Autopilot
- Operate autonomously inside the active mission boundary.
- Escalate immediately when the task leaves the certified boundary.
- Keep a concise audit trail of important decisions and side effects.""",
    AuthorityMode.INCIDENT: """\
## Authority Mode
AUTHORITY MODE: Incident
- Prioritize impact reduction and root-cause isolation.
- Move quickly, but keep an audit trail for every meaningful action.
- Still escalate production deploys and external communications when required.""",
    AuthorityMode.FREEZE: """\
## Authority Mode
AUTHORITY MODE: Freeze
- Treat the environment as read-only for side-effecting work.
- Continue analysis and diagnostics, but block non-safe actions.
- Offer safe alternatives instead of attempting writes.""",
}

AUDIENCE_TEMPLATES: dict[AudiencePersona, str] = {
    AudiencePersona.JUNIOR_MENTOR: """\
## Audience Profile
AUDIENCE: Junior Mentor
- Teach the reasoning, not just the answer.
- Explain why each choice was made and call out uncertainty explicitly.
- Prefer checklists, annotated notes, and beginner-safe next steps.""",
    AudiencePersona.PEER_DS: """\
## Audience Profile
AUDIENCE: Peer DS
- Be concise, technical, and reproducible.
- Include trade-offs and enough detail for another DS to reproduce the work.
- Prefer notebooks, SQL, and analysis appendices over executive summaries.""",
    AudiencePersona.SENIOR_STAFF: """\
## Audience Profile
AUDIENCE: Senior/Staff
- Lead with the decision, risk, and caveat.
- Compress details into the few facts that change scope or direction.
- Prefer decision memos, diffs, and explicit trade-offs.""",
    AudiencePersona.EXECUTIVE: """\
## Audience Profile
AUDIENCE: Executive
- Lead with business impact and the required decision.
- Use a one-page brief structure: Situation, Impact, Options, Recommendation.
- Risk labels must use SAFE / REVIEW / DANGER exactly.""",
    AudiencePersona.AUDITOR: """\
## Audience Profile
AUDIENCE: Auditor
- Every important claim needs a concrete source reference or policy reference.
- Include lineage and approval history for actions with side effects.
- Never speculate; state what is not available in current records.""",
}


def build_authority_section(authority: AuthorityMode | str) -> str:
    """Render the authority-mode section for the system prompt."""

    return AUTHORITY_TEMPLATES[AuthorityMode.coerce(authority)]


def build_audience_section(persona: AudiencePersona | str) -> str:
    """Render the audience-profile section for the system prompt."""

    return AUDIENCE_TEMPLATES[AudiencePersona.coerce(persona)]


def build_mission_section(pack: MissionPack) -> str:
    """Render the mission-pack section for the system prompt."""

    defaults = []
    if pack.authority_default is not None:
        defaults.append(f"authority={pack.authority_default.value}")
    if pack.audience_default is not None:
        defaults.append(f"audience={pack.audience_default.value}")
    defaults_summary = ", ".join(defaults) if defaults else "-"
    return "\n".join(
        [
            "## Mission Pack",
            f"MISSION: {pack.name} (v{pack.version})",
            f"- summary: {pack.summary}",
            f"- defaults: {defaults_summary}",
            f"- skills_required: {_format_prompt_list(pack.skills_required)}",
            (
                "- boundary.allowed_data_domains: "
                f"{_format_prompt_list(pack.boundary.allowed_data_domains)}"
            ),
            (
                "- boundary.required_semantic_metrics: "
                f"{_format_prompt_list(pack.boundary.required_semantic_metrics)}"
            ),
            (
                "- boundary.allowed_action_classes: "
                f"{_format_prompt_list(pack.boundary.allowed_action_classes)}"
            ),
            f"- required_checks: {_format_prompt_list(pack.required_checks)}",
            f"- required_artifacts: {_format_prompt_list(pack.required_artifacts)}",
            (
                "- required_delivery_channels: "
                f"{_format_prompt_list(pack.required_delivery_channels)}"
            ),
            f"- auto_escalate_when: {_format_prompt_list(pack.auto_escalate_when)}",
            f"- success_criteria: {_format_prompt_list(pack.success_criteria)}",
        ]
    )


def build_missing_mission_section(name: str) -> str:
    """Render a fallback when a mission name is active but its definition is unavailable."""

    return "\n".join(
        [
            "## Mission Pack",
            f"MISSION: {name}",
            "- Mission pack definition unavailable in the local registry.",
            (
                "- Stay inside the active task contract and escalate ambiguity "
                "instead of inventing scope."
            ),
        ]
    )


def _format_prompt_list(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(values) if values else "-"


TASK_CONTRACT_SECTION_TEMPLATE = """\
## Task Contract (현재 업무 계약)

{block}

[계약 준수 규칙]
- `agent_will_escalate`에 해당하면 사용자 확인 후 진행한다.
- `forbidden_data_patterns`에 해당하는 데이터는 읽지 않는다.
- `budget` 초과 위험이 있으면 즉시 사용자에게 알린다.
- 계약에 없는 deliverable을 자의로 추가하지 않는다.
- 가정이 필요하면 `add_assumption`으로 반드시 기록한다.
- 상태 전이는 `update_task_contract(transition_to=...)`로만 수행한다.
"""

NO_CONTRACT_BLOCK = """\
활성 TaskContract가 없다. 분석 실행이 필요한 요청이라면 먼저
`create_task_contract`로 초안을 만들고 사용자 확인을 받은 뒤 진행하라.
단순 질의/탐색 요청은 예외다.
"""


def task_contract_section(bundle: TaskContractBundle | None) -> str:
    """Render the active task contract summary injected into the system prompt."""

    if bundle is None:
        return TASK_CONTRACT_SECTION_TEMPLATE.format(block=NO_CONTRACT_BLOCK)

    contract = bundle.contract
    primary_metric = bundle.primary_metric
    primary_kpi_name = (
        primary_metric.name if primary_metric else (contract.primary_kpi_id or "unassigned")
    )
    baseline = (
        primary_metric.baseline_value
        if primary_metric and primary_metric.baseline_value is not None
        else "n/a"
    )
    target = (
        primary_metric.target_value
        if primary_metric and primary_metric.target_value is not None
        else "n/a"
    )
    deliverables = " | ".join(
        f"{item.type}({item.format}{f' x{item.count}' if item.count else ''})"
        for item in contract.required_deliverables[:4]
    )
    if len(contract.required_deliverables) > 4:
        deliverables += f" | ... 외 {len(contract.required_deliverables) - 4}건"
    risky_assumptions = (
        " / ".join(
            f"[{entry.entry_id}] {entry.statement} ({entry.risk_level}, unverified)"
            for entry in bundle.risky_assumptions[:3]
        )
        or "none"
    )
    if contract.definition_of_done:
        dod_parts = list(contract.definition_of_done.criteria[:3])
        verifier_requirements = contract.definition_of_done.verifier
        if verifier_requirements is not None:
            verifier_parts: list[str] = []
            if verifier_requirements.min_result is not None:
                verifier_parts.append(f"result>={verifier_requirements.min_result}")
            if verifier_requirements.min_confidence_grade is not None:
                verifier_parts.append(f"confidence>={verifier_requirements.min_confidence_grade}")
            if verifier_requirements.require_no_blocking_issues:
                verifier_parts.append("blocking_issues=0")
            if verifier_parts:
                dod_parts.append("verifier " + ", ".join(verifier_parts))
        dod_summary = ", ".join(dod_parts) if dod_parts else "not set"
    else:
        dod_summary = "not set"
    block = "\n".join(
        [
            (
                f"- task_id: {contract.task_id} "
                f"(status={contract.status.value}, version={contract.version})"
            ),
            f"- goal: {contract.business_goal}",
            (
                "- autonomy mode: "
                f"authority={contract.authority.value if contract.authority is not None else '-'}; "
                f"audience={contract.audience.value if contract.audience is not None else '-'}; "
                f"mission={contract.mission or '-'}"
            ),
            f"- primary KPI: {primary_kpi_name} (baseline={baseline}, target={target})",
            f"- deliverables: {deliverables}",
            (
                "- autonomy: "
                f"will_do={', '.join(contract.autonomy.agent_will_do) or '-'}; "
                f"will_ask={', '.join(contract.autonomy.agent_will_ask) or '-'}; "
                f"will_escalate={', '.join(contract.autonomy.agent_will_escalate) or '-'}"
            ),
            f"- open assumptions (risk>=medium): {risky_assumptions}",
            f"- DoD: {dod_summary}",
        ]
    )
    return TASK_CONTRACT_SECTION_TEMPLATE.format(block=block)


# ---------------------------------------------------------------------------
# Portfolio section — status report for async portfolio (Phase 9)
# ---------------------------------------------------------------------------


def build_portfolio_section(snapshot: object | None) -> str | None:
    """Build a portfolio status section for prompt injection.

    The snapshot is a ``PortfolioSnapshot`` from the evaluator.
    This is a status *report* — the LLM reads it and freely decides
    which tools to call (resume_task, pause_task, set_sla, etc.).
    """
    if snapshot is None:
        return None

    from ds_agent.application.portfolio.portfolio_evaluator import PortfolioSnapshot

    if not isinstance(snapshot, PortfolioSnapshot):
        return None

    lines = ["# Portfolio Status"]
    lines.append(
        f"Active: {len(snapshot.active_entries)} | "
        f"Waiting: {len(snapshot.waiting_entries)} | "
        f"Monitoring: {len(snapshot.monitoring_entries)} | "
        f"Candidates: {len(snapshot.candidate_entries)}",
    )
    lines.append(
        f"Slots: {snapshot.active_slot_count}/{snapshot.max_slots} "
        f"({snapshot.available_slots} available)",
    )

    if snapshot.sla_at_risk_count > 0:
        lines.append(f"SLA AT RISK: {snapshot.sla_at_risk_count} entries overdue or near deadline")

    if snapshot.resumable_conditions:
        lines.append("\nResumable tasks (conditions satisfied):")
        for r in snapshot.resumable_conditions[:5]:
            lines.append(f"  - {r.condition_id} ({r.kind}): {r.reason}")

    if snapshot.priority_ranking:
        lines.append("\nPriority ranking (top 5):")
        for s in snapshot.priority_ranking[:5]:
            lines.append(
                f"  - {s.entry_id}: score={s.raw_score:.1f} "
                f"sla_urgency={s.sla_urgency:.1f} biz={s.business_weight:.1f}",
            )

    return "\n".join(lines)
