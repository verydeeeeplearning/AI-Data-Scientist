"""Pure domain rules for task contract transitions and completion checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

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
_MISSION_CHECK_FAILURE_STATUSES = frozenset({"error", "fail", "missing"})


class MissionArtifactResolution(Protocol):
    """Structural protocol for optional mission artifact gating."""

    mission_name: str
    mission_loaded: bool
    required_artifacts: tuple[str, ...]
    mapped_required_artifacts: Mapping[str, tuple[str, ...]]
    unmapped_required_artifacts: tuple[str, ...]
    missing_contract_artifacts: tuple[str, ...]
    missing_delivery_artifacts: tuple[str, ...]


class MissionDeliveryChannelResolution(Protocol):
    """Structural protocol for optional mission delivery-channel gating."""

    mission_name: str
    mission_loaded: bool
    dispatch_log_available: bool
    required_delivery_channels: tuple[str, ...]
    mapped_required_delivery_channels: Mapping[str, str]
    unmapped_required_delivery_channels: tuple[str, ...]
    satisfied_delivery_channels: tuple[str, ...]
    missing_delivery_channels: tuple[str, ...]
    delivery_pack_id: str | None


@dataclass(frozen=True, slots=True)
class MissionRequiredCheckGate:
    """Structured view over verifier-backed mission required-check metadata."""

    mission_name: str
    mission_loaded: bool
    required_checks: tuple[str, ...]
    mapped_required_checks: dict[str, tuple[str, ...]]
    unmapped_required_checks: tuple[str, ...]
    required_check_results: dict[str, str]
    required_check_failures: tuple[str, ...]


class TaskContractValidator:
    """Completion and quality checks for contract closure."""

    @staticmethod
    def ensure_ready_to_close(
        bundle: TaskContractBundle,
        mission_artifact_resolution: MissionArtifactResolution | None = None,
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution | None = None,
    ) -> None:
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
        TaskContractValidator.ensure_mission_required_checks_ready_for_close(bundle)
        if bundle.delivery_pack is None:
            raise DoDUnmetError("A delivery pack is required before closing")
        if bundle.delivery_pack.status == "rejected":
            raise DoDUnmetError("Rejected delivery packs must be rebuilt before closing")
        if not bundle.delivery_pack.items:
            raise DoDUnmetError("A delivery pack must contain at least one item")
        if any(not item.delivered for item in bundle.delivery_pack.items):
            raise DoDUnmetError("All delivery items must be marked delivered before closing")
        TaskContractValidator.ensure_mission_artifacts_ready_for_close(mission_artifact_resolution)
        TaskContractValidator.ensure_mission_delivery_channels_ready_for_close(
            mission_delivery_channel_resolution
        )

    @staticmethod
    def ensure_mission_artifacts_declared_for_review(
        mission_artifact_resolution: MissionArtifactResolution | None = None,
    ) -> None:
        if mission_artifact_resolution is None:
            return
        if not mission_artifact_resolution.mission_loaded:
            raise InvalidTransitionError(
                "Mission pack could not be loaded; required artifacts cannot be validated",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="review",
                    failure="mission_pack_unavailable",
                ),
            )
        if mission_artifact_resolution.unmapped_required_artifacts:
            missing = ", ".join(mission_artifact_resolution.unmapped_required_artifacts)
            raise InvalidTransitionError(
                "Mission required artifacts are not mapped to the current delivery "
                f"vocabulary: {missing}",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="review",
                    failure="unmapped_required_artifacts",
                ),
            )
        if mission_artifact_resolution.missing_contract_artifacts:
            missing = ", ".join(mission_artifact_resolution.missing_contract_artifacts)
            raise InvalidTransitionError(
                f"Mission required artifacts are missing from required_deliverables: {missing}",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="review",
                    failure="missing_contract_artifacts",
                ),
            )

    @staticmethod
    def ensure_auto_verifier_verdict_ready_for_review(
        bundle: TaskContractBundle,
        *,
        current_run_id: str | None = None,
    ) -> None:
        latest_verdict = TaskContractValidator.get_effective_review_verdict(bundle)
        if latest_verdict is None:
            raise InvalidTransitionError(
                "At least one review verdict is required for review",
                metadata=TaskContractValidator._build_review_gate_error_metadata(
                    bundle.review_verdicts,
                    failure="missing_review_verdict",
                    latest_verdict=None,
                ),
            )
        if not TaskContractValidator._is_auto_verifier_verdict(latest_verdict):
            raise InvalidTransitionError(
                "Latest orchestrator verdict must come from auto verifier before moving to review",
                metadata=TaskContractValidator._build_review_gate_error_metadata(
                    bundle.review_verdicts,
                    failure="latest_verdict_not_auto_verifier",
                    latest_verdict=latest_verdict,
                ),
            )
        if latest_verdict.run_id is None or not latest_verdict.run_id.strip():
            raise InvalidTransitionError(
                "Latest auto verifier verdict must include a run id before moving to review",
                metadata=TaskContractValidator._build_review_gate_error_metadata(
                    bundle.review_verdicts,
                    failure="latest_verdict_missing_run_id",
                    latest_verdict=latest_verdict,
                ),
            )
        expected_run_id = (current_run_id or "").strip()
        actual_run_id = latest_verdict.run_id.strip()
        if expected_run_id and actual_run_id != expected_run_id:
            raise InvalidTransitionError(
                "Latest auto verifier verdict must match the active run before moving to review",
                metadata=TaskContractValidator._build_review_gate_error_metadata(
                    bundle.review_verdicts,
                    failure="stale_review_verdict",
                    latest_verdict=latest_verdict,
                    expected_run_id=expected_run_id,
                ),
            )
        TaskContractValidator.ensure_mission_required_checks_ready_for_review(bundle)

    @staticmethod
    def ensure_mission_required_checks_ready_for_review(bundle: TaskContractBundle) -> None:
        gate = TaskContractValidator._extract_mission_required_check_gate(bundle)
        if gate is None:
            return
        if not gate.mission_loaded:
            raise InvalidTransitionError(
                "Mission pack could not be loaded; required checks cannot be validated",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="review",
                    failure="mission_pack_unavailable",
                ),
            )
        if gate.unmapped_required_checks:
            missing = ", ".join(gate.unmapped_required_checks)
            raise InvalidTransitionError(
                "Mission required checks are not mapped to the current verifier "
                f"inventory: {missing}",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="review",
                    failure="unmapped_required_checks",
                ),
            )
        if gate.required_check_failures:
            missing = ", ".join(gate.required_check_failures)
            raise InvalidTransitionError(
                f"Mission required checks must pass before moving to review: {missing}",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="review",
                    failure="failed_required_checks",
                ),
            )

    @staticmethod
    def ensure_mission_required_checks_ready_for_close(bundle: TaskContractBundle) -> None:
        gate = TaskContractValidator._extract_mission_required_check_gate(bundle)
        if gate is None:
            return
        if not gate.mission_loaded:
            raise DoDUnmetError(
                "Mission pack could not be loaded; required checks cannot be validated",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="close",
                    failure="mission_pack_unavailable",
                ),
            )
        if gate.unmapped_required_checks:
            missing = ", ".join(gate.unmapped_required_checks)
            raise DoDUnmetError(
                "Mission required checks are not mapped to the current verifier "
                f"inventory: {missing}",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="close",
                    failure="unmapped_required_checks",
                ),
            )
        if gate.required_check_failures:
            missing = ", ".join(gate.required_check_failures)
            raise DoDUnmetError(
                f"Mission required checks must pass before closing: {missing}",
                metadata=TaskContractValidator._build_mission_required_check_error_metadata(
                    gate,
                    transition_target="close",
                    failure="failed_required_checks",
                ),
            )

    @staticmethod
    def ensure_mission_artifacts_ready_for_close(
        mission_artifact_resolution: MissionArtifactResolution | None = None,
    ) -> None:
        if mission_artifact_resolution is None:
            return
        if not mission_artifact_resolution.mission_loaded:
            raise DoDUnmetError(
                "Mission pack could not be loaded; required artifacts cannot be validated",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="close",
                    failure="mission_pack_unavailable",
                ),
            )
        if mission_artifact_resolution.unmapped_required_artifacts:
            missing = ", ".join(mission_artifact_resolution.unmapped_required_artifacts)
            raise DoDUnmetError(
                "Mission required artifacts are not mapped to the current delivery "
                f"vocabulary: {missing}",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="close",
                    failure="unmapped_required_artifacts",
                ),
            )
        if mission_artifact_resolution.missing_contract_artifacts:
            missing = ", ".join(mission_artifact_resolution.missing_contract_artifacts)
            raise DoDUnmetError(
                f"Mission required artifacts are missing from required_deliverables: {missing}",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="close",
                    failure="missing_contract_artifacts",
                ),
            )
        if mission_artifact_resolution.missing_delivery_artifacts:
            missing = ", ".join(mission_artifact_resolution.missing_delivery_artifacts)
            raise DoDUnmetError(
                f"Mission required artifacts are missing from delivered outputs: {missing}",
                metadata=TaskContractValidator._build_mission_artifact_error_metadata(
                    mission_artifact_resolution,
                    transition_target="close",
                    failure="missing_delivery_artifacts",
                ),
            )

    @staticmethod
    def ensure_mission_delivery_channels_ready_for_close(
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution | None = None,
    ) -> None:
        if mission_delivery_channel_resolution is None:
            return
        if not mission_delivery_channel_resolution.mission_loaded:
            raise DoDUnmetError(
                "Mission pack could not be loaded; required delivery channels cannot be validated",
                metadata=TaskContractValidator._build_mission_delivery_channel_error_metadata(
                    mission_delivery_channel_resolution,
                    transition_target="close",
                    failure="mission_pack_unavailable",
                ),
            )
        if (
            not mission_delivery_channel_resolution.required_delivery_channels
            and not mission_delivery_channel_resolution.unmapped_required_delivery_channels
        ):
            return
        if not mission_delivery_channel_resolution.dispatch_log_available:
            raise DoDUnmetError(
                "Delivery dispatch log is unavailable; required delivery channels "
                "cannot be validated",
                metadata=TaskContractValidator._build_mission_delivery_channel_error_metadata(
                    mission_delivery_channel_resolution,
                    transition_target="close",
                    failure="dispatch_log_unavailable",
                ),
            )
        if mission_delivery_channel_resolution.unmapped_required_delivery_channels:
            missing = ", ".join(
                mission_delivery_channel_resolution.unmapped_required_delivery_channels
            )
            raise DoDUnmetError(
                "Mission required delivery channels are not mapped to the current "
                f"delivery vocabulary: {missing}",
                metadata=TaskContractValidator._build_mission_delivery_channel_error_metadata(
                    mission_delivery_channel_resolution,
                    transition_target="close",
                    failure="unmapped_required_delivery_channels",
                ),
            )
        if mission_delivery_channel_resolution.missing_delivery_channels:
            missing = ", ".join(mission_delivery_channel_resolution.missing_delivery_channels)
            raise DoDUnmetError(
                "Mission required delivery channels are missing from persisted "
                f"dispatch records: {missing}",
                metadata=TaskContractValidator._build_mission_delivery_channel_error_metadata(
                    mission_delivery_channel_resolution,
                    transition_target="close",
                    failure="missing_delivery_channels",
                ),
            )

    @staticmethod
    def build_dod_summary(
        bundle: TaskContractBundle,
        mission_artifact_resolution: MissionArtifactResolution | None = None,
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution | None = None,
    ) -> list[str]:
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
        summary.extend(TaskContractValidator._build_mission_required_check_summary(bundle))
        summary.extend(
            TaskContractValidator._build_mission_artifact_summary(mission_artifact_resolution)
        )
        summary.extend(
            TaskContractValidator._build_mission_delivery_channel_summary(
                mission_delivery_channel_resolution
            )
        )
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

    @staticmethod
    def _is_auto_verifier_verdict(verdict: ReviewVerdict) -> bool:
        source = str(verdict.metadata.get("source") or "").strip().lower()
        reviewer = verdict.reviewer.strip().lower()
        return (
            verdict.category == "orchestrator"
            and source == "auto_verifier"
            and reviewer in {"verifier", "verifier_orchestrator"}
        )

    @staticmethod
    def _build_review_gate_error_metadata(
        review_verdicts: list[ReviewVerdict],
        *,
        failure: str,
        latest_verdict: ReviewVerdict | None,
        expected_run_id: str | None = None,
    ) -> dict[str, object]:
        orchestrator_verdicts = [
            verdict for verdict in review_verdicts if verdict.category == "orchestrator"
        ]
        metadata: dict[str, object] = {
            "kind": "verifier_review_gate",
            "transition_target": "review",
            "failure": failure,
            "review_verdict_count": len(review_verdicts),
            "orchestrator_verdict_count": len(orchestrator_verdicts),
        }
        if expected_run_id is not None:
            metadata["expected_run_id"] = expected_run_id
        if latest_verdict is None:
            return metadata
        metadata.update(
            {
                "latest_verdict_id": latest_verdict.verdict_id,
                "latest_verdict_category": latest_verdict.category,
                "latest_verdict_reviewer": latest_verdict.reviewer,
                "latest_verdict_run_id": latest_verdict.run_id,
                "latest_verdict_source": latest_verdict.metadata.get("source"),
            }
        )
        return metadata

    @staticmethod
    def _build_mission_artifact_summary(
        mission_artifact_resolution: MissionArtifactResolution | None,
    ) -> list[str]:
        if mission_artifact_resolution is None:
            return []

        mission_name = mission_artifact_resolution.mission_name
        if not mission_artifact_resolution.mission_loaded:
            return [f"Mission artifacts [{mission_name}]: mission pack unavailable"]

        required = ", ".join(mission_artifact_resolution.required_artifacts) or "none"
        summary = [f"Mission artifacts [{mission_name}]: required={required}"]
        if mission_artifact_resolution.unmapped_required_artifacts:
            summary.append(
                "Mission artifacts gate: unmapped="
                + ", ".join(mission_artifact_resolution.unmapped_required_artifacts)
            )
        if mission_artifact_resolution.missing_contract_artifacts:
            summary.append(
                "Mission artifacts gate: contract_missing="
                + ", ".join(mission_artifact_resolution.missing_contract_artifacts)
            )
        if mission_artifact_resolution.missing_delivery_artifacts:
            summary.append(
                "Mission artifacts gate: delivery_missing="
                + ", ".join(mission_artifact_resolution.missing_delivery_artifacts)
            )
        if len(summary) == 1:
            summary.append("Mission artifacts gate: ready")
        return summary

    @staticmethod
    def _build_mission_required_check_summary(bundle: TaskContractBundle) -> list[str]:
        gate = TaskContractValidator._extract_mission_required_check_gate(bundle)
        if gate is None:
            return []
        if not gate.mission_loaded:
            return [f"Mission checks [{gate.mission_name}]: mission pack unavailable"]

        required = ", ".join(gate.required_checks) or "none"
        summary = [f"Mission checks [{gate.mission_name}]: required={required}"]
        if gate.unmapped_required_checks:
            summary.append(
                "Mission checks gate: unmapped=" + ", ".join(gate.unmapped_required_checks)
            )
        if gate.required_check_failures:
            summary.append("Mission checks gate: failed=" + ", ".join(gate.required_check_failures))
        elif gate.required_check_results:
            summary.append("Mission checks gate: ready")
        return summary

    @staticmethod
    def _build_mission_artifact_error_metadata(
        mission_artifact_resolution: MissionArtifactResolution,
        *,
        transition_target: str,
        failure: str,
    ) -> dict[str, object]:
        return {
            "kind": "mission_artifact_gate",
            "transition_target": transition_target,
            "failure": failure,
            "mission_name": mission_artifact_resolution.mission_name,
            "mission_loaded": mission_artifact_resolution.mission_loaded,
            "required_artifacts": list(mission_artifact_resolution.required_artifacts),
            "mapped_required_artifacts": {
                required_artifact: list(mapped_artifacts)
                for required_artifact, mapped_artifacts in (
                    mission_artifact_resolution.mapped_required_artifacts.items()
                )
            },
            "unmapped_required_artifacts": list(
                mission_artifact_resolution.unmapped_required_artifacts
            ),
            "missing_contract_artifacts": list(
                mission_artifact_resolution.missing_contract_artifacts
            ),
            "missing_delivery_artifacts": list(
                mission_artifact_resolution.missing_delivery_artifacts
            ),
        }

    @staticmethod
    def _build_mission_required_check_error_metadata(
        gate: MissionRequiredCheckGate,
        *,
        transition_target: str,
        failure: str,
    ) -> dict[str, object]:
        return {
            "kind": "mission_check_gate",
            "transition_target": transition_target,
            "failure": failure,
            "mission_name": gate.mission_name,
            "mission_loaded": gate.mission_loaded,
            "required_checks": list(gate.required_checks),
            "mapped_required_checks": {
                required_check: list(mapped_check_ids)
                for required_check, mapped_check_ids in gate.mapped_required_checks.items()
            },
            "unmapped_required_checks": list(gate.unmapped_required_checks),
            "required_check_results": dict(gate.required_check_results),
            "required_check_failures": list(gate.required_check_failures),
        }

    @staticmethod
    def _build_mission_delivery_channel_summary(
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution | None,
    ) -> list[str]:
        if mission_delivery_channel_resolution is None:
            return []

        mission_name = mission_delivery_channel_resolution.mission_name
        if not mission_delivery_channel_resolution.mission_loaded:
            return [f"Mission delivery channels [{mission_name}]: mission pack unavailable"]
        if (
            not mission_delivery_channel_resolution.required_delivery_channels
            and not mission_delivery_channel_resolution.unmapped_required_delivery_channels
        ):
            return []
        if not mission_delivery_channel_resolution.dispatch_log_available:
            return [f"Mission delivery channels [{mission_name}]: dispatch log unavailable"]

        required = (
            ", ".join(mission_delivery_channel_resolution.required_delivery_channels) or "none"
        )
        summary = [f"Mission delivery channels [{mission_name}]: required={required}"]
        if mission_delivery_channel_resolution.satisfied_delivery_channels:
            summary.append(
                "Mission delivery channels gate: satisfied="
                + ", ".join(mission_delivery_channel_resolution.satisfied_delivery_channels)
            )
        if mission_delivery_channel_resolution.unmapped_required_delivery_channels:
            summary.append(
                "Mission delivery channels gate: unmapped="
                + ", ".join(mission_delivery_channel_resolution.unmapped_required_delivery_channels)
            )
        if mission_delivery_channel_resolution.missing_delivery_channels:
            summary.append(
                "Mission delivery channels gate: delivery_missing="
                + ", ".join(mission_delivery_channel_resolution.missing_delivery_channels)
            )
        if len(summary) == 1:
            summary.append("Mission delivery channels gate: ready")
        return summary

    @staticmethod
    def _build_mission_delivery_channel_error_metadata(
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution,
        *,
        transition_target: str,
        failure: str,
    ) -> dict[str, object]:
        return {
            "kind": "mission_delivery_channel_gate",
            "transition_target": transition_target,
            "failure": failure,
            "mission_name": mission_delivery_channel_resolution.mission_name,
            "mission_loaded": mission_delivery_channel_resolution.mission_loaded,
            "dispatch_log_available": mission_delivery_channel_resolution.dispatch_log_available,
            "required_delivery_channels": list(
                mission_delivery_channel_resolution.required_delivery_channels
            ),
            "mapped_required_delivery_channels": dict(
                mission_delivery_channel_resolution.mapped_required_delivery_channels
            ),
            "unmapped_required_delivery_channels": list(
                mission_delivery_channel_resolution.unmapped_required_delivery_channels
            ),
            "satisfied_delivery_channels": list(
                mission_delivery_channel_resolution.satisfied_delivery_channels
            ),
            "missing_delivery_channels": list(
                mission_delivery_channel_resolution.missing_delivery_channels
            ),
            "delivery_pack_id": mission_delivery_channel_resolution.delivery_pack_id,
        }

    @staticmethod
    def _extract_mission_required_check_gate(
        bundle: TaskContractBundle,
    ) -> MissionRequiredCheckGate | None:
        latest_verdict = TaskContractValidator.get_effective_review_verdict(bundle)
        if latest_verdict is None:
            return None

        metadata = latest_verdict.metadata
        relevant_keys = {
            "mission_name",
            "mission_pack_loaded",
            "mission_required_checks",
            "mission_required_check_map",
            "mission_unmapped_required_checks",
            "mission_required_check_results",
            "mission_required_check_failures",
        }
        if not any(key in metadata for key in relevant_keys):
            return None

        mission_name = (
            str(metadata.get("mission_name") or bundle.contract.mission or "unknown").strip()
            or "unknown"
        )
        mission_loaded = metadata.get("mission_pack_loaded") is not False
        required_checks = _tuple_from_string_list(metadata.get("mission_required_checks"))
        unmapped_required_checks = _tuple_from_string_list(
            metadata.get("mission_unmapped_required_checks")
        )
        mapped_required_checks = _mapped_required_check_ids(
            metadata.get("mission_required_check_map")
        )
        required_check_results = _string_dict(metadata.get("mission_required_check_results"))
        required_check_failures = _tuple_from_string_list(
            metadata.get("mission_required_check_failures")
        ) or tuple(
            required_check
            for required_check, status in required_check_results.items()
            if status in _MISSION_CHECK_FAILURE_STATUSES
        )
        return MissionRequiredCheckGate(
            mission_name=mission_name,
            mission_loaded=mission_loaded,
            required_checks=required_checks,
            mapped_required_checks=mapped_required_checks,
            unmapped_required_checks=unmapped_required_checks,
            required_check_results=required_check_results,
            required_check_failures=required_check_failures,
        )


def _tuple_from_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        candidate = item.strip()
        if candidate:
            normalized.append(candidate)
    return tuple(normalized)


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        normalized[raw_key.strip()] = raw_value.strip()
    return normalized


def _mapped_required_check_ids(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        check_ids = _tuple_from_string_list(raw_value)
        if check_ids:
            normalized[raw_key.strip()] = check_ids
    return normalized


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
        *,
        current_run_id: str | None = None,
        mission_artifact_resolution: MissionArtifactResolution | None = None,
        mission_delivery_channel_resolution: MissionDeliveryChannelResolution | None = None,
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
        ):
            TaskContractValidator.ensure_auto_verifier_verdict_ready_for_review(
                bundle,
                current_run_id=current_run_id,
            )
            TaskContractValidator.ensure_mission_artifacts_declared_for_review(
                mission_artifact_resolution
            )

        if (
            current_status == TaskContractStatus.REVIEW
            and target_status == TaskContractStatus.CLOSED
        ):
            TaskContractValidator.ensure_ready_to_close(
                bundle,
                mission_artifact_resolution=mission_artifact_resolution,
                mission_delivery_channel_resolution=mission_delivery_channel_resolution,
            )
