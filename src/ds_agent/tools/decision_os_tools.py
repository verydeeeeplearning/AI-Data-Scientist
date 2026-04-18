"""Decision OS tools for run comparison and promotion workflows."""

from __future__ import annotations

import json

from ds_agent.domain.entities.promotion import TargetStage
from ds_agent.domain.entities.review_artifact import ReviewSkillName
from ds_agent.infrastructure.decision_os_container import (
    DecisionOsContainer,
    build_decision_os_container,
)
from ds_agent.tools.registry import tool

_container: DecisionOsContainer | None = None


def set_decision_os_container(container: DecisionOsContainer) -> None:
    """Wire a Decision OS container into the tool module."""

    global _container
    _container = container


def _get_container() -> DecisionOsContainer:
    global _container
    if _container is not None:
        return _container

    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _container = build_decision_os_container(str(workspace) if workspace is not None else None)
    return _container


def _ok_response(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _error_response(code: str, message: str, **payload: object) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}, **payload},
        ensure_ascii=False,
    )


@tool(
    name="compare_runs",
    description=(
        "Compares two Decision OS experiment runs and returns a structured run-diff "
        "covering features, config, metrics, verifier status, code, and data snapshot."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "run_a_id": {"type": "string"},
            "run_b_id": {"type": "string"},
        },
        "required": ["run_a_id", "run_b_id"],
    },
)
def compare_runs(run_a_id: str, run_b_id: str) -> str:
    try:
        result = _get_container().compare_runs.execute(run_a_id, run_b_id)
        return _ok_response(**result.model_dump(mode="json"))
    except LookupError as exc:
        return _error_response("RUN_NOT_FOUND", str(exc))
    except ValueError as exc:
        return _error_response("VALIDATION_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="request_promotion",
    description=(
        "Creates a Decision OS promotion-gate decision for one candidate run, "
        "runs the current policy checks, and initializes the DS -> Lead -> MLOps "
        "approval chain."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "candidate_run_id": {"type": "string"},
            "target_stage": {
                "type": "string",
                "enum": ["staging", "production", "canary"],
            },
            "approvers": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rollback_plan_ref": {"type": "string"},
        },
        "required": [
            "candidate_run_id",
            "target_stage",
            "approvers",
            "rollback_plan_ref",
        ],
    },
)
def request_promotion(
    candidate_run_id: str,
    target_stage: TargetStage,
    approvers: list[str],
    rollback_plan_ref: str,
) -> str:
    try:
        result = _get_container().request_promotion.execute(
            candidate_run_id=candidate_run_id,
            target_stage=target_stage,
            approvers=approvers,
            rollback_plan_ref=rollback_plan_ref,
        )
        return _ok_response(**result.model_dump(mode="json"))
    except LookupError as exc:
        return _error_response("RUN_NOT_FOUND", str(exc))
    except ValueError as exc:
        return _error_response("VALIDATION_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="get_post_deploy_status",
    description=(
        "Returns the recent Decision OS post-deploy monitoring summary for one model, "
        "including drift, metric, service-level, and remediation status."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "model_id": {"type": "string"},
            "window": {"type": "string"},
        },
        "required": ["model_id"],
    },
)
def get_post_deploy_status(model_id: str, window: str = "7d") -> str:
    try:
        result = _get_container().get_post_deploy_status.execute(model_id=model_id, window=window)
        return _ok_response(**result.model_dump(mode="json"))
    except LookupError as exc:
        return _error_response("STATUS_NOT_FOUND", str(exc))
    except ValueError as exc:
        return _error_response("VALIDATION_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="record_review_artifact",
    description=(
        "Persists one structured shared-skill review artifact for a Decision OS experiment run "
        "so the Review tab can render backtesting, causal, uncertainty, or retrain-vs-rollback cards."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "run_id": {"type": "string"},
            "skill_name": {
                "type": "string",
                "enum": [
                    "backtesting",
                    "causal-assumption-check",
                    "uncertainty-quantification",
                    "retrain-vs-rollback",
                ],
            },
            "summary": {"type": "string"},
            "artifact": {"type": "object"},
            "narrative": {"type": "string"},
        },
        "required": ["run_id", "skill_name", "summary", "artifact"],
    },
)
def record_review_artifact(
    run_id: str,
    skill_name: ReviewSkillName,
    summary: str,
    artifact: dict[str, object],
    narrative: str | None = None,
) -> str:
    try:
        run = _get_container().record_review_artifact.execute(
            run_id=run_id,
            skill_name=skill_name,
            summary=summary,
            artifact=artifact,
            narrative=narrative,
        )
        return _ok_response(
            run_id=run.run_id,
            review_artifacts=[item.model_dump(mode="json") for item in run.review_artifacts],
            review_artifact_count=len(run.review_artifacts),
        )
    except LookupError as exc:
        return _error_response("RUN_NOT_FOUND", str(exc))
    except ValueError as exc:
        return _error_response("VALIDATION_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="get_review_artifacts",
    description=(
        "Returns the structured review artifacts already stored for one Decision OS experiment run."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "run_id": {"type": "string"},
        },
        "required": ["run_id"],
    },
)
def get_review_artifacts(run_id: str) -> str:
    try:
        artifacts = _get_container().get_review_artifacts.execute(run_id)
        return _ok_response(
            run_id=run_id,
            review_artifacts=[item.model_dump(mode="json") for item in artifacts],
            review_artifact_count=len(artifacts),
        )
    except LookupError as exc:
        return _error_response("RUN_NOT_FOUND", str(exc))
    except ValueError as exc:
        return _error_response("VALIDATION_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_response(type(exc).__name__.upper(), str(exc))
