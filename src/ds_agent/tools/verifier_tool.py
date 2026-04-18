"""Verifier orchestration tools."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ds_agent.application.dtos.task_contract import ReviewVerdictInputDTO
from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.task_contract import DeliverableSpec, TaskContract
from ds_agent.infrastructure.task_contract_container import (
    TaskContractContainer,
    build_task_contract_container,
)
from ds_agent.infrastructure.verifier_container import VerifierContainer, build_verifier_container
from ds_agent.runtime.tool_runtime_context import get_tool_runtime_context
from ds_agent.runtime.verifier_shadow_runtime import snapshot_shadow_runtime_log
from ds_agent.tools.path_utils import get_active_workspace
from ds_agent.tools.registry import tool

_container: VerifierContainer | None = None


def set_verifier_container(container: VerifierContainer) -> None:
    """Wire a verifier container into the tool module."""

    global _container
    _container = container


def _get_container(workspace_dir: str | None = None) -> VerifierContainer:
    global _container
    if _container is not None and workspace_dir is None:
        return _container
    if workspace_dir is None:
        workspace = get_active_workspace()
        workspace_dir = str(workspace) if workspace is not None else None
    container = build_verifier_container(workspace_dir)
    if workspace_dir is None:
        _container = container
    return container


def _build_task_contract(
    *,
    task_id: str,
    session_id: str,
    task_type: str,
    business_goal: str,
    required_deliverables: list[dict[str, Any]] | None = None,
) -> TaskContract:
    now = datetime.now()
    return TaskContract(
        task_id=task_id,
        session_id=session_id,
        type=task_type,
        business_goal=business_goal,
        required_deliverables=[
            DeliverableSpec.model_validate(item)
            for item in (
                required_deliverables
                or [{"type": "exec_brief", "audience": "executive", "format": "md"}]
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _error_response(code: str, message: str) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": {"code": code, "message": message},
        },
        ensure_ascii=False,
    )


def _load_task_contract(
    *,
    workspace_dir: str | None,
    task_id: str,
    session_id: str,
    task_type: str,
    business_goal: str,
    required_deliverables: list[dict[str, Any]] | None,
) -> tuple[TaskContract, TaskContractContainer | None]:
    container = build_task_contract_container(workspace_dir)
    bundle = container.store.get_bundle(task_id)
    if bundle is not None:
        return bundle.contract, container
    return (
        _build_task_contract(
            task_id=task_id,
            session_id=session_id,
            task_type=task_type,
            business_goal=business_goal,
            required_deliverables=required_deliverables,
        ),
        None,
    )


@tool(
    name="run_verifier",
    description=(
        "Run the 4-layer verifier orchestrator and persist the verdict. "
        "Optional artifacts.semantic_candidates can be attached so successful "
        "verifier outcomes create pending semantic-memory proposals."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "session_id": {"type": "string"},
            "task_type": {"type": "string"},
            "business_goal": {"type": "string"},
            "artifacts": {
                "type": "object",
                "description": (
                    "Verifier inputs. May include semantic_candidates for verified "
                    "query / glossary / trust write-back proposals."
                ),
            },
            "run_log": {"type": "array", "items": {"type": "object"}},
            "evidence_refs": {"type": "array", "items": {"type": "object"}},
            "workspace_dir": {"type": "string"},
            "required_deliverables": {"type": "array", "items": {"type": "object"}},
            "shadow_mode": {"type": "boolean"},
        },
        "required": ["task_id", "session_id", "task_type", "business_goal"],
    },
)
async def run_verifier(
    task_id: str,
    session_id: str,
    task_type: str,
    business_goal: str,
    artifacts: dict[str, Any] | None = None,
    run_log: list[dict[str, Any]] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    workspace_dir: str | None = None,
    required_deliverables: list[dict[str, Any]] | None = None,
    shadow_mode: bool | None = None,
) -> str:
    try:
        task_contract, task_contract_container = _load_task_contract(
            workspace_dir=workspace_dir,
            task_id=task_id,
            session_id=session_id,
            task_type=task_type,
            business_goal=business_goal,
            required_deliverables=required_deliverables,
        )
        merged_run_log = _merge_runtime_shadow_log(run_log)
        ctx = VerifierContext(
            run_id=f"{task_contract.task_id}:{task_contract.session_id}",
            task_contract=task_contract,
            artifacts=artifacts or {},
            run_log=merged_run_log,
            evidence_refs=[EvidenceRef.model_validate(item) for item in (evidence_refs or [])],
            config=VerifierConfig(
                shadow_mode=_resolve_shadow_mode(shadow_mode, merged_run_log),
            ),
            workspace_path=workspace_dir,
        )
        verdict = await _get_container(workspace_dir).orchestrator.run(ctx)
        task_contract_record = None
        if task_contract_container is not None:
            task_contract_record = task_contract_container.record_review_verdict.execute(
                ReviewVerdictInputDTO(
                    task_id=task_id,
                    verdict_id=verdict.verdict_id,
                    category=verdict.category,
                    result=verdict.result,
                    reviewer=verdict.reviewer,
                    summary=verdict.summary,
                    evidence_refs=verdict.evidence_refs,
                    run_id=verdict.run_id,
                    layers=verdict.layers,
                    blocking_issues=verdict.blocking_issues,
                    confidence=verdict.confidence,
                    recommended_actions=verdict.recommended_actions,
                    metadata=verdict.metadata,
                )
            )
        return json.dumps(
            {
                "ok": True,
                "summary": verdict.summary,
                "artifact_ref": f"verdict:{verdict.verdict_id}",
                "payload": verdict.model_dump(mode="json"),
                "task_contract_recorded": task_contract_record is not None,
                "task_contract_version": (
                    task_contract_record["new_version"]
                    if task_contract_record is not None
                    else None
                ),
                "shadow_mode": ctx.config.shadow_mode,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="get_review_verdict",
    description="Load a persisted verifier verdict by id.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "verdict_id": {"type": "string"},
            "workspace_dir": {"type": "string"},
        },
        "required": ["verdict_id"],
    },
)
async def get_review_verdict(verdict_id: str, workspace_dir: str | None = None) -> str:
    try:
        verdict = _get_container(workspace_dir).repo.get(verdict_id)
        if verdict is None:
            return _error_response("NOT_FOUND", f"review verdict not found: {verdict_id}")
        return json.dumps(
            {"ok": True, "payload": verdict.model_dump(mode="json")}, ensure_ascii=False
        )
    except Exception as exc:
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="get_verifier_shadow_comparison",
    description="Load a persisted verifier shadow comparison by id.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "comparison_id": {"type": "string"},
            "workspace_dir": {"type": "string"},
        },
        "required": ["comparison_id"],
    },
)
async def get_verifier_shadow_comparison(
    comparison_id: str,
    workspace_dir: str | None = None,
) -> str:
    try:
        record = _get_container(workspace_dir).shadow_repo.get(comparison_id)
        if record is None:
            return _error_response(
                "NOT_FOUND",
                f"verifier shadow comparison not found: {comparison_id}",
            )
        return json.dumps(
            {
                "ok": True,
                "summary": (
                    f"{round(record.match_rate * 100)}% match | "
                    f"mismatches={record.mismatch_count}/{record.applicable_count}"
                ),
                "payload": record.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="list_verifier_shadow_comparisons",
    description="List persisted verifier shadow comparisons for one task or verdict.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "verdict_id": {"type": "string"},
            "workspace_dir": {"type": "string"},
            "mismatches_only": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
    },
)
async def list_verifier_shadow_comparisons(
    task_id: str | None = None,
    verdict_id: str | None = None,
    workspace_dir: str | None = None,
    mismatches_only: bool = False,
    limit: int = 10,
) -> str:
    try:
        if not task_id and not verdict_id:
            return _error_response("INVALID_ARGUMENT", "task_id or verdict_id is required")
        container = _get_container(workspace_dir)
        if verdict_id:
            records = container.shadow_repo.list_for_verdict(verdict_id)
        else:
            records = container.shadow_repo.list_for_task(task_id or "")
        if mismatches_only:
            records = [record for record in records if record.mismatch_count > 0]
        limited = records[: max(limit, 1)]
        return json.dumps(
            {
                "ok": True,
                "items": [
                    {
                        "comparison_id": record.comparison_id,
                        "verdict_id": record.verdict_id,
                        "task_id": record.task_id,
                        "created_at": record.created_at.isoformat(),
                        "match_rate": record.match_rate,
                        "applicable_count": record.applicable_count,
                        "mismatch_count": record.mismatch_count,
                    }
                    for record in limited
                ],
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error_response(type(exc).__name__.upper(), str(exc))


def _merge_runtime_shadow_log(run_log: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged = list(run_log or [])
    runtime_context = get_tool_runtime_context()
    if runtime_context is None:
        return merged
    runtime_log = snapshot_shadow_runtime_log(
        runtime_context.session_id,
        runtime_context.run_id,
    )
    if not runtime_log:
        return merged
    seen = {json.dumps(item, sort_keys=True, ensure_ascii=False) for item in merged}
    for item in runtime_log:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if marker in seen:
            continue
        merged.append(item)
        seen.add(marker)
    return merged


def _resolve_shadow_mode(
    shadow_mode: bool | None,
    run_log: list[dict[str, Any]],
) -> bool:
    if shadow_mode is not None:
        return shadow_mode
    return any(item.get("event") in {"tool.call", "harness.warning", "drift.detected"} for item in run_log)
