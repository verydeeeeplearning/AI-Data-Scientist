"""Plain-text renderers for task contract surfaces."""

from __future__ import annotations

import json
from collections.abc import Sequence

from ds_agent.application.dtos.task_contract import TaskContractListItemDTO, TaskContractViewDTO
from ds_agent.presentation.verdict_presenters import (
    pick_effective_review_verdict,
    render_verdict_snapshot,
)


def render_task_contract_list(items: Sequence[TaskContractListItemDTO]) -> str:
    """Render a compact multiline list."""

    if not items:
        return "No task contracts found."

    lines = ["Task contracts:"]
    for item in items:
        lines.append(
            f"- {item.task_id} | {item.status} | v{item.version} | {item.type} | "
            f"{item.business_goal}"
        )
    return "\n".join(lines)


def render_task_contract_summary(view: TaskContractViewDTO) -> str:
    """Render one contract for CLI and Telegram surfaces."""

    contract = view.contract
    deliverables = ", ".join(
        f"{item.type}:{item.format}->{item.audience}" for item in contract.required_deliverables
    )
    open_assumptions = [
        entry
        for entry in (view.assumption_log.entries if view.assumption_log is not None else [])
        if not entry.verified
    ]
    lines = [
        f"Task contract: {contract.task_id}",
        f"Status: {contract.status.value} | Version: {contract.version}",
        f"Type: {contract.type}",
        f"Business goal: {contract.business_goal}",
    ]
    if contract.authority is not None or contract.audience is not None or contract.mission:
        lines.append(
            "Autonomy: "
            f"authority={contract.authority.value if contract.authority is not None else '-'} | "
            f"audience={contract.audience.value if contract.audience is not None else '-'} | "
            f"mission={contract.mission or '-'}"
        )
    if view.goal_brief is not None:
        lines.append(f"Decision: {view.goal_brief.decision_to_make}")
    if contract.decision_owner:
        lines.append(f"Owner: {contract.decision_owner}")
    if deliverables:
        lines.append(f"Deliverables: {deliverables}")
    if open_assumptions:
        lines.append(f"Open assumptions: {len(open_assumptions)}")
    effective_verdict = pick_effective_review_verdict(view.review_verdicts)
    if effective_verdict is not None:
        lines.append(f"Latest verifier: {render_verdict_snapshot(effective_verdict)}")
    if view.delivery_pack is not None:
        lines.append(
            "Delivery pack: "
            f"{view.delivery_pack.status.value} | "
            f"{len(view.delivery_pack.artifacts) or len(view.delivery_pack.items)} artifacts"
        )
    if view.dod_summary:
        lines.append("DoD summary:")
        lines.extend(f"  {item}" for item in view.dod_summary)
    return "\n".join(lines)


def render_task_contract_markdown(view: TaskContractViewDTO) -> str:
    """Render a markdown export."""

    contract = view.contract
    sections = [
        f"# Task Contract {contract.task_id}",
        "",
        f"- Status: `{contract.status.value}`",
        f"- Version: `{contract.version}`",
        f"- Type: `{contract.type}`",
        f"- Business goal: {contract.business_goal}",
    ]
    if contract.authority is not None or contract.audience is not None or contract.mission:
        authority = contract.authority.value if contract.authority is not None else "-"
        audience = contract.audience.value if contract.audience is not None else "-"
        sections.extend(
            [
                f"- Authority: `{authority}`",
                f"- Audience: `{audience}`",
                f"- Mission: `{contract.mission or '-'}`",
            ]
        )
    if view.goal_brief is not None:
        sections.extend(
            [
                "",
                "## Goal Brief",
                f"- Business question: {view.goal_brief.business_question}",
                f"- DS problem: {view.goal_brief.ds_problem_statement}",
                f"- Decision: {view.goal_brief.decision_to_make}",
                f"- Baseline: {view.goal_brief.comparison_baseline}",
            ]
        )
    if contract.required_deliverables:
        sections.extend(["", "## Deliverables"])
        sections.extend(
            f"- {item.type} -> {item.audience} ({item.format})"
            for item in contract.required_deliverables
        )
    if view.assumption_log is not None and view.assumption_log.entries:
        sections.extend(["", "## Assumptions"])
        sections.extend(
            (f"- [{entry.risk_level}] {entry.statement} | verified={str(entry.verified).lower()}")
            for entry in view.assumption_log.entries
        )
    if view.review_verdicts:
        sections.extend(["", "## Review Verdicts"])
        sections.extend(
            (
                f"- {item.category}: {render_verdict_snapshot(item)} "
                f"({item.reviewer}) - {item.summary}"
            )
            for item in view.review_verdicts
        )
    if view.delivery_pack is not None:
        sections.extend(["", "## Delivery Pack"])
        sections.append(f"- Status: `{view.delivery_pack.status.value}`")
        if view.delivery_pack.artifacts:
            sections.extend(
                (
                    "- "
                    f"{artifact.type.value} -> {artifact.audience.value} ({artifact.format.value}) "
                    f"[dispatch={artifact.dispatch_mode}]"
                )
                for artifact in view.delivery_pack.artifacts
            )
        else:
            sections.extend(
                (
                    "- "
                    f"{item.deliverable_type}: {item.artifact_path} "
                    f"(delivered={str(item.delivered).lower()})"
                )
                for item in view.delivery_pack.items
            )
    if view.dod_summary:
        sections.extend(["", "## DoD Summary"])
        sections.extend(f"- {item}" for item in view.dod_summary)
    return "\n".join(sections)


def render_task_contract_json(view: TaskContractViewDTO) -> str:
    """Render a stable JSON export."""

    return json.dumps(view.model_dump(mode="json"), ensure_ascii=False, indent=2)
