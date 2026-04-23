"""Task contract tools for LLM orchestration."""

from __future__ import annotations

import json
from typing import Literal

from ds_agent.application.dtos.task_contract import (
    AssumptionInputDTO,
    BuildDeliveryPackDTO,
    DeliveryPackInputDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    ReviewVerdictInputDTO,
    TaskContractDraftDTO,
    TaskContractUpdateDTO,
    VerifyAssumptionDTO,
)
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.errors.task_contract_errors import TaskContractError
from ds_agent.infrastructure.task_contract_container import (
    TaskContractContainer,
    build_task_contract_container,
)
from ds_agent.runtime.tool_runtime_context import get_tool_runtime_context
from ds_agent.tools.registry import tool

_container: TaskContractContainer | None = None


def set_task_contract_container(container: TaskContractContainer) -> None:
    """Wire a task contract container into the tool module."""

    global _container
    _container = container


def _get_container() -> TaskContractContainer:
    global _container
    if _container is not None:
        return _container
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _container = build_task_contract_container(str(workspace) if workspace is not None else None)
    return _container


def _ok_response(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _error_response(code: str, message: str, **payload: object) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": {"code": code, "message": message},
            **payload,
        },
        ensure_ascii=False,
    )


def _handle_error(exc: Exception) -> str:
    if isinstance(exc, TaskContractError):
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": exc.error_code,
                    "message": str(exc),
                    "metadata": exc.metadata,
                },
            },
            ensure_ascii=False,
        )
    if isinstance(exc, ValueError):
        return _error_response("VALIDATION_ERROR", str(exc))
    return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="create_task_contract",
    description=(
        "사용자 요청을 받아 TaskContract 초안(draft)을 생성한다. GoalBrief도 함께 생성되고 "
        "이 도구는 분석 실행 전에 호출되어야 한다."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "contract_type": {"type": "string"},
            "business_goal": {"type": "string"},
            "goal_brief": {"type": "object"},
            "required_deliverables": {"type": "array", "items": {"type": "object"}},
            "allowed_data_sources": {"type": "array", "items": {"type": "object"}},
            "forbidden_data_patterns": {"type": "array", "items": {"type": "string"}},
            "budget": {"type": "object"},
            "autonomy": {"type": "object"},
            "authority": {
                "type": "string",
                "enum": ["shadow", "supervised", "delegate", "autopilot", "incident", "freeze"],
            },
            "audience": {
                "type": "string",
                "enum": [
                    "junior_mentor",
                    "peer_ds",
                    "senior_staff",
                    "executive",
                    "auditor",
                ],
            },
            "mission": {"type": "string"},
            "decision_owner": {"type": "string"},
            "decision_deadline": {"type": "string"},
            "definition_of_done": {"type": "object"},
        },
        "required": [
            "session_id",
            "contract_type",
            "business_goal",
            "goal_brief",
            "required_deliverables",
        ],
    },
)
def create_task_contract(
    session_id: str,
    contract_type: str,
    business_goal: str,
    goal_brief: dict,
    required_deliverables: list[dict],
    allowed_data_sources: list[dict] | None = None,
    forbidden_data_patterns: list[str] | None = None,
    budget: dict | None = None,
    autonomy: dict | None = None,
    authority: str | None = None,
    audience: str | None = None,
    mission: str | None = None,
    decision_owner: str | None = None,
    decision_deadline: str | None = None,
    definition_of_done: dict | None = None,
) -> str:
    try:
        dto = TaskContractDraftDTO.model_validate(
            {
                "session_id": session_id,
                "contract_type": contract_type,
                "business_goal": business_goal,
                "goal_brief": goal_brief,
                "required_deliverables": required_deliverables,
                "allowed_data_sources": allowed_data_sources or [],
                "forbidden_data_patterns": forbidden_data_patterns or [],
                "budget": budget or {},
                "autonomy": autonomy or {},
                "authority": authority,
                "audience": audience,
                "mission": mission,
                "decision_owner": decision_owner,
                "decision_deadline": decision_deadline,
                "definition_of_done": definition_of_done,
            }
        )
        result = _get_container().create.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="update_task_contract",
    description="기존 TaskContract의 필드 또는 status를 갱신한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "expected_version": {"type": "integer"},
            "patch": {"type": "object"},
            "run_id": {"type": "string"},
            "transition_to": {
                "type": "string",
                "enum": ["agreed", "in_progress", "review", "closed", "abandoned"],
            },
            "reason": {"type": "string"},
        },
        "required": ["task_id", "expected_version", "patch"],
    },
)
def update_task_contract(
    task_id: str,
    expected_version: int,
    patch: dict,
    run_id: str | None = None,
    transition_to: Literal["agreed", "in_progress", "review", "closed", "abandoned"] | None = None,
    reason: str | None = None,
) -> str:
    try:
        effective_run_id = run_id
        if effective_run_id is None:
            runtime_context = get_tool_runtime_context()
            if runtime_context is not None:
                effective_run_id = runtime_context.run_id
        dto = TaskContractUpdateDTO.model_validate(
            {
                "task_id": task_id,
                "expected_version": expected_version,
                "patch": patch,
                "run_id": effective_run_id,
                "transition_to": transition_to,
                "reason": reason,
            }
        )
        result = _get_container().update.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="get_task_contract",
    description="단일 TaskContract를 하위 artifact 요약과 함께 조회한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "include": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "goal_brief",
                        "metric_specs",
                        "dataset_manifest",
                        "assumption_log",
                        "review_verdicts",
                        "delivery_pack",
                    ],
                },
            },
        },
        "required": ["task_id"],
    },
)
def get_task_contract(task_id: str, include: list[str] | None = None) -> str:
    try:
        result = _get_container().get.execute(task_id, include)
        return _ok_response(**result.model_dump(mode="json"))
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="add_assumption",
    description="LLM이 명시하지 않고 진행한 가정을 AssumptionLog에 기록한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "statement": {"type": "string"},
            "rationale": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "asked_user": {"type": "boolean"},
        },
        "required": ["task_id", "statement", "rationale", "risk_level"],
    },
)
def add_assumption(
    task_id: str,
    statement: str,
    rationale: str,
    risk_level: Literal["low", "medium", "high"],
    asked_user: bool = False,
) -> str:
    try:
        dto = AssumptionInputDTO(
            task_id=task_id,
            statement=statement,
            rationale=rationale,
            risk_level=risk_level,
            asked_user=asked_user,
        )
        result = _get_container().add_assumption.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="verify_assumption",
    description="TaskContract AssumptionLog의 특정 entry를 검증 완료로 표시한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "entry_id": {"type": "string"},
            "expected_version": {"type": "integer"},
            "verification_note": {"type": "string"},
        },
        "required": ["task_id", "entry_id", "expected_version"],
    },
)
def verify_assumption(
    task_id: str,
    entry_id: str,
    expected_version: int,
    verification_note: str | None = None,
) -> str:
    try:
        dto = VerifyAssumptionDTO(
            task_id=task_id,
            entry_id=entry_id,
            expected_version=expected_version,
            verification_note=verification_note,
        )
        result = _get_container().verify_assumption.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="list_my_contracts",
    description="현재 세션의 TaskContract 목록을 상태 필터와 함께 조회한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "status_filter": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [status.value for status in TaskContractStatus],
                },
            },
            "limit": {"type": "integer", "default": 20},
        },
        "required": ["session_id"],
    },
)
def list_my_contracts(
    session_id: str,
    status_filter: list[str] | None = None,
    limit: int = 20,
) -> str:
    try:
        parsed_statuses = (
            [TaskContractStatus(value) for value in status_filter] if status_filter else None
        )
        items = _get_container().list_contracts.execute(
            session_id,
            status_filter=parsed_statuses,
            limit=limit,
        )
        return _ok_response(contracts=[item.model_dump(mode="json") for item in items])
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="close_task_contract",
    description="모든 DoD 기준이 충족되었을 때 TaskContract를 closed로 전환한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "expected_version": {"type": "integer"},
            "closing_note": {"type": "string"},
        },
        "required": ["task_id", "expected_version", "closing_note"],
    },
)
def close_task_contract(task_id: str, expected_version: int, closing_note: str) -> str:
    try:
        result = _get_container().close.execute(
            task_id,
            expected_version=expected_version,
            closing_note=closing_note,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="record_review_verdict",
    description="TaskContract에 ReviewVerdict를 추가한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "category": {"type": "string"},
            "result": {"type": "string"},
            "reviewer": {"type": "string"},
            "summary": {"type": "string"},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task_id", "category", "result", "reviewer", "summary"],
    },
)
def record_review_verdict(
    task_id: str,
    category: str,
    result: str,
    reviewer: str,
    summary: str,
    evidence_refs: list[str] | None = None,
) -> str:
    try:
        dto = ReviewVerdictInputDTO.model_validate(
            {
                "task_id": task_id,
                "category": category,
                "result": result,
                "reviewer": reviewer,
                "summary": summary,
                "evidence_refs": evidence_refs or [],
            }
        )
        outcome = _get_container().record_review_verdict.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="build_delivery_pack",
    description=(
        "TaskContract.required_deliverables를 기반으로 audience-aware DeliveryPack 초안을 생성하고 "
        "TaskContract에 연결한다."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "audiences": {"type": "array", "items": {"type": "string"}},
            "follow_up_actions": {"type": "array", "items": {"type": "string"}},
            "source_analysis_id": {"type": "string"},
            "confidence": {"type": "number"},
            "signed_by": {"type": "string"},
            "signature": {"type": "string"},
            "global_context": {"type": "object"},
            "tenant": {"type": "string", "default": "default"},
        },
        "required": ["task_id"],
    },
)
def build_delivery_pack(
    task_id: str,
    audiences: list[str] | None = None,
    follow_up_actions: list[str] | None = None,
    source_analysis_id: str | None = None,
    confidence: float | None = None,
    signed_by: str | None = None,
    signature: str | None = None,
    global_context: dict | None = None,
    tenant: str = "default",
) -> str:
    try:
        dto = BuildDeliveryPackDTO(
            task_id=task_id,
            audiences=audiences or [],
            follow_up_actions=follow_up_actions or [],
            source_analysis_id=source_analysis_id,
            confidence=confidence,
            signed_by=signed_by,
            signature=signature,
            global_context=global_context or {},
            tenant=tenant,
        )
        outcome = _get_container().build_delivery_pack.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="render_delivery_artifact",
    description=(
        "TaskContract에 저장된 DeliveryPack artifact 하나를 실제 파일로 렌더하고 "
        "rendered_uri/status를 갱신한다."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "artifact_id": {"type": "string"},
            "analysis": {"type": ["object", "string"]},
            "output_dir": {"type": "string"},
            "audience_profile": {
                "type": "string",
                "enum": [
                    "junior_mentor",
                    "peer_ds",
                    "senior_staff",
                    "executive",
                    "auditor",
                ],
            },
        },
        "required": ["task_id", "artifact_id", "analysis", "output_dir"],
    },
)
def render_delivery_artifact(
    task_id: str,
    artifact_id: str,
    analysis: dict | str,
    output_dir: str,
    audience_profile: str | None = None,
) -> str:
    try:
        dto = RenderDeliveryArtifactDTO.model_validate(
            {
                "task_id": task_id,
                "artifact_id": artifact_id,
                "analysis": analysis,
                "output_dir": output_dir,
                "audience_profile": audience_profile,
            }
        )
        outcome = _get_container().render_delivery_artifact.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="dispatch_delivery",
    description=(
        "Rendered DeliveryPack artifact瑜?policy-aware router濡?dispatch?섏뿬 "
        "idempotent dispatch log瑜?湲곕줉?쒕떎. dry_run=true硫?policy check留?諛섑솚?쒕떎."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "artifact_ids": {"type": "array", "items": {"type": "string"}},
            "channels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "email",
                        "slack_dm",
                        "slack_channel",
                        "notion_page",
                        "confluence",
                        "jira_ticket",
                        "git_pr",
                        "compliance_system",
                    ],
                },
            },
            "dry_run": {"type": "boolean", "default": False},
            "approve_manual_review": {"type": "boolean", "default": False},
        },
        "required": ["task_id"],
    },
)
def dispatch_delivery(
    task_id: str,
    artifact_ids: list[str] | None = None,
    channels: list[str] | None = None,
    dry_run: bool = False,
    approve_manual_review: bool = False,
) -> str:
    try:
        dto = DispatchDeliveryDTO.model_validate(
            {
                "task_id": task_id,
                "artifact_ids": artifact_ids or [],
                "channels": channels or [],
                "dry_run": dry_run,
                "approve_manual_review": approve_manual_review,
            }
        )
        outcome = _get_container().dispatch_delivery.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="list_delivery_log",
    description=(
        "TaskContract stakeholder delivery dispatch log瑜?task/pack/artifact/channel "
        "湲곗?濡?議고쉶?쒕떎."
    ),
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "pack_id": {"type": "string"},
            "artifact_ids": {"type": "array", "items": {"type": "string"}},
            "channels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "email",
                        "slack_dm",
                        "slack_channel",
                        "notion_page",
                        "confluence",
                        "jira_ticket",
                        "git_pr",
                        "compliance_system",
                    ],
                },
            },
            "limit": {"type": "integer", "default": 50},
        },
        "required": ["task_id"],
    },
)
def list_delivery_log(
    task_id: str,
    pack_id: str | None = None,
    artifact_ids: list[str] | None = None,
    channels: list[str] | None = None,
    limit: int = 50,
) -> str:
    try:
        dto = ListDeliveryLogDTO.model_validate(
            {
                "task_id": task_id,
                "pack_id": pack_id,
                "artifact_ids": artifact_ids or [],
                "channels": channels or [],
                "limit": limit,
            }
        )
        outcome = _get_container().list_delivery_log.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="record_delivery_pack",
    description="TaskContract에 DeliveryPack을 기록한다.",
    category="mission",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "items": {"type": "array", "items": {"type": "object"}},
            "artifacts": {"type": "array", "items": {"type": "object"}},
            "follow_up_actions": {"type": "array", "items": {"type": "string"}},
            "source_analysis_id": {"type": "string"},
            "confidence": {"type": "number"},
            "signed_by": {"type": "string"},
            "signature": {"type": "string"},
            "global_context": {"type": "object"},
            "tenant": {"type": "string", "default": "default"},
            "status": {
                "type": "string",
                "enum": ["draft", "rendered", "dispatched", "rejected"],
                "default": "draft",
            },
        },
        "required": ["task_id"],
    },
)
def record_delivery_pack(
    task_id: str,
    items: list[dict] | None = None,
    artifacts: list[dict] | None = None,
    follow_up_actions: list[str] | None = None,
    source_analysis_id: str | None = None,
    confidence: float | None = None,
    signed_by: str | None = None,
    signature: str | None = None,
    global_context: dict | None = None,
    tenant: str = "default",
    status: str = "draft",
) -> str:
    try:
        dto = DeliveryPackInputDTO.model_validate(
            {
                "task_id": task_id,
                "items": items or [],
                "artifacts": artifacts or [],
                "follow_up_actions": follow_up_actions or [],
                "source_analysis_id": source_analysis_id,
                "confidence": confidence,
                "signed_by": signed_by,
                "signature": signature,
                "global_context": global_context or {},
                "tenant": tenant,
                "status": status,
            }
        )
        outcome = _get_container().record_delivery_pack.execute(dto)
        return _ok_response(**outcome)
    except Exception as exc:
        return _handle_error(exc)
