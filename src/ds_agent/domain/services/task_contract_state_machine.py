"""Pure domain rules for task contract transitions and completion checks."""

from __future__ import annotations

from collections.abc import Mapping

from ds_agent.domain.entities.review_verdict import ConfidenceGrade, ReviewVerdict, VerdictResult
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.errors.task_contract_errors import DoDUnmetError, InvalidTransitionError

_VERDICT_ORDER: Mapping[VerdictResult, int] = {"fail": 0, "warn": 1, "pass": 2}
_CONFIDENCE_ORDER: Mapping[ConfidenceGrade, int] = {
    "insufficient": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


class TaskContractValidator:
    """Completion and quality checks for contract closure."""

    @staticmethod
    def ensure_ready_to_close(bundle: TaskContractBundle) -> None:
        latest_verdict = TaskContractValidator.get_effective_review_verdict(bundle)
        if latest_verdict is None:
            raise DoDUnmetError("At least one review verdict is required before closing")
        latest_result = latest_verdict.result or "fail"
        verifier_requirements = (
            bundle.contract.definition_of_done.verifier
            if bundle.contract.definition_of_done is not None
            else None
        )
        if latest_result == "fail":
            raise DoDUnmetError("Latest review verdict failed; rerun verifier before closing")
        if verifier_requirements is not None:
            if (
                verifier_requirements.min_result is not None
                and _VERDICT_ORDER[latest_result] < _VERDICT_ORDER[verifier_requirements.min_result]
            ):
                raise DoDUnmetError(
                    "Latest review verdict does not satisfy the required verifier result"
                )
            if verifier_requirements.min_confidence_grade is not None:
                if latest_verdict.confidence is None or latest_verdict.confidence.grade is None:
                    raise DoDUnmetError(
                        "Verifier confidence is required before closing this contract"
                    )
                if (
                    _CONFIDENCE_ORDER[latest_verdict.confidence.grade]
                    < _CONFIDENCE_ORDER[verifier_requirements.min_confidence_grade]
                ):
                    raise DoDUnmetError(
                        "Latest verifier confidence is below the Definition of Done threshold"
                    )
            if verifier_requirements.require_no_blocking_issues and any(
                issue.blocking for issue in latest_verdict.blocking_issues
            ):
                raise DoDUnmetError("Verifier blocking issues must be resolved before closing")
        if bundle.delivery_pack is None:
            raise DoDUnmetError("A delivery pack is required before closing")
        if bundle.delivery_pack.status == "rejected":
            raise DoDUnmetError("Rejected delivery packs must be rebuilt before closing")
        if not bundle.delivery_pack.items:
            raise DoDUnmetError("A delivery pack must contain at least one item")
        if any(not item.delivered for item in bundle.delivery_pack.items):
            raise DoDUnmetError("All delivery items must be marked delivered before closing")

    @staticmethod
    def build_dod_summary(bundle: TaskContractBundle) -> list[str]:
        summary = (
            list(bundle.contract.definition_of_done.criteria)
            if bundle.contract.definition_of_done
            else []
        )
        latest_verdict = TaskContractValidator.get_effective_review_verdict(bundle)
        verifier_requirements = (
            bundle.contract.definition_of_done.verifier
            if bundle.contract.definition_of_done is not None
            else None
        )
        if latest_verdict is not None:
            summary.append(TaskContractValidator._build_verifier_snapshot(latest_verdict))
        if verifier_requirements is not None:
            requirements: list[str] = []
            if verifier_requirements.min_result is not None:
                requirements.append(f"result>={verifier_requirements.min_result}")
            if verifier_requirements.min_confidence_grade is not None:
                requirements.append(f"confidence>={verifier_requirements.min_confidence_grade}")
            if verifier_requirements.require_no_blocking_issues:
                requirements.append("blocking_issues=0")
            if requirements:
                summary.append("Verifier gate: " + ", ".join(requirements))
        if not summary:
            summary.extend(
                [
                    f"review verdicts={len(bundle.review_verdicts)}",
                    (
                        "delivery items="
                        f"{len(bundle.delivery_pack.items) if bundle.delivery_pack else 0}"
                    ),
                ]
            )
        elif bundle.delivery_pack is not None:
            delivered = sum(1 for item in bundle.delivery_pack.items if item.delivered)
            summary.append(
                f"delivery items delivered={delivered}/{len(bundle.delivery_pack.items)}"
            )
            summary.append(f"delivery pack status={bundle.delivery_pack.status.value}")
        return summary

    @staticmethod
    def get_effective_review_verdict(bundle: TaskContractBundle) -> ReviewVerdict | None:
        return TaskContractValidator._pick_effective_review_verdict(bundle.review_verdicts)

    @staticmethod
    def _pick_effective_review_verdict(
        review_verdicts: list[ReviewVerdict],
    ) -> ReviewVerdict | None:
        if not review_verdicts:
            return None
        preferred = [verdict for verdict in review_verdicts if verdict.category == "orchestrator"]
        candidates = preferred or review_verdicts
        return max(candidates, key=lambda verdict: (verdict.created_at, verdict.verdict_id))

    @staticmethod
    def _build_verifier_snapshot(verdict: ReviewVerdict) -> str:
        result = verdict.result or "fail"
        confidence = verdict.confidence.grade if verdict.confidence is not None else "unknown"
        blocking_issues = sum(1 for issue in verdict.blocking_issues if issue.blocking)
        return (
            f"Latest verifier={result} | confidence={confidence} | "
            f"blocking_issues={blocking_issues}"
        )


class TaskContractStateMachine:
    """Allowed transitions and state-specific preconditions."""

    _ALLOWED: Mapping[TaskContractStatus, set[TaskContractStatus]] = {
        TaskContractStatus.DRAFT: {
            TaskContractStatus.AGREED,
            TaskContractStatus.ABANDONED,
        },
        TaskContractStatus.AGREED: {
            TaskContractStatus.IN_PROGRESS,
            TaskContractStatus.ABANDONED,
        },
        TaskContractStatus.IN_PROGRESS: {
            TaskContractStatus.IN_PROGRESS,
            TaskContractStatus.REVIEW,
        },
        TaskContractStatus.REVIEW: {
            TaskContractStatus.IN_PROGRESS,
            TaskContractStatus.CLOSED,
            TaskContractStatus.ABANDONED,
        },
        TaskContractStatus.CLOSED: set(),
        TaskContractStatus.ABANDONED: set(),
    }

    @classmethod
    def validate_transition(
        cls,
        bundle: TaskContractBundle,
        target_status: TaskContractStatus,
    ) -> None:
        current_status = bundle.contract.status
        allowed = cls._ALLOWED.get(current_status, set())
        if target_status not in allowed:
            raise InvalidTransitionError(
                f"Transition {current_status.value} -> {target_status.value} is not allowed"
            )

        if (
            current_status == TaskContractStatus.DRAFT
            and target_status == TaskContractStatus.AGREED
        ):
            if bundle.goal_brief is None:
                raise InvalidTransitionError("GoalBrief is required before agreeing a contract")
            if not bundle.contract.required_deliverables:
                raise InvalidTransitionError(
                    "At least one deliverable is required before agreement"
                )

        if (
            current_status == TaskContractStatus.IN_PROGRESS
            and target_status == TaskContractStatus.REVIEW
            and not bundle.review_verdicts
        ):
            raise InvalidTransitionError("At least one review verdict is required for review")

        if (
            current_status == TaskContractStatus.REVIEW
            and target_status == TaskContractStatus.CLOSED
        ):
            TaskContractValidator.ensure_ready_to_close(bundle)
