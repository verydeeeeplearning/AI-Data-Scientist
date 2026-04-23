"""Phase-0 autonomy policy helpers.

This module introduces the new authority and audience axes while keeping the
legacy 3-mode configuration available as a compatibility layer.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.interfaces.certification import CertificationStore
from ds_agent.domain.value_objects.action_class import ActionClass, WriteEffect, get_action_class
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.action_matrix import ActionMatrix, Verdict


@dataclass(frozen=True, slots=True)
class AutonomyContext:
    """Resolved autonomy context for one run or tool decision."""

    authority: AuthorityMode
    audience: AudiencePersona
    mission: str | None = None
    legacy_mode: str | None = None


@dataclass(frozen=True, slots=True)
class AutonomyDecision:
    """Result of the phase-0 autonomy evaluation."""

    context: AutonomyContext
    requires_approval: bool = False
    blocked: bool = False
    reason: str = "auto"
    escalation_signals: tuple[str, ...] = ()


class AutonomyPolicy:
    """Resolve the autonomy axes and apply a minimal phase-0 policy."""

    def __init__(
        self,
        matrix: ActionMatrix | None = None,
        *,
        certification_store: CertificationStore | None = None,
    ) -> None:
        self._matrix = matrix or ActionMatrix.default()
        self._certification_store = certification_store

    def resolve_context(
        self,
        *,
        authority: AuthorityMode | str | None = None,
        audience: AudiencePersona | str | None = None,
        mission: str | None = None,
        legacy_mode: str | None = None,
    ) -> AutonomyContext:
        resolved_authority = (
            AuthorityMode.coerce(authority)
            if authority is not None
            else AuthorityMode.from_legacy_agent_mode(legacy_mode)
        )
        resolved_audience = (
            AudiencePersona.coerce(audience)
            if audience is not None
            else AudiencePersona.from_legacy_agent_mode(legacy_mode)
        )
        return AutonomyContext(
            authority=resolved_authority,
            audience=resolved_audience,
            mission=mission,
            legacy_mode=legacy_mode,
        )

    def evaluate(
        self,
        *,
        action_is_safe: bool,
        action_class: ActionClass | str | None = None,
        action_arguments: dict[str, object] | None = None,
        authority: AuthorityMode | str | None = None,
        audience: AudiencePersona | str | None = None,
        mission: str | None = None,
        mission_pack: MissionPack | None = None,
        latest_review_verdict: ReviewVerdict | None = None,
        legacy_mode: str | None = None,
    ) -> AutonomyDecision:
        """Apply a minimal approval/blocking overlay.

        Phase 0 intentionally stays coarse-grained. Full action-class and mission
        boundary enforcement lands in later phases.
        """

        context = self.resolve_context(
            authority=_resolve_authority(authority, mission_pack, legacy_mode),
            audience=_resolve_audience(audience, mission_pack, legacy_mode),
            mission=mission or (mission_pack.name if mission_pack is not None else None),
            legacy_mode=legacy_mode,
        )

        normalized_legacy = _normalize_legacy_mode(legacy_mode)
        if authority is None and normalized_legacy == "step-by-step":
            return AutonomyDecision(
                context=context,
                requires_approval=True,
                reason="legacy_step_by_step_requires_approval",
            )

        if context.authority.requires_certification and not _is_autopilot_certified(
            mission_pack,
            self._certification_store,
        ):
            return AutonomyDecision(
                context=context,
                requires_approval=True,
                reason="missing_certification",
            )

        if action_class is not None:
            resolved_action_class = (
                action_class
                if isinstance(action_class, ActionClass)
                else get_action_class(action_class)
            )
            action_name = resolved_action_class.name
            override = None
            if mission_pack is not None:
                override = mission_pack.policy_override(action_name, context.authority)
            verdict = (
                Verdict(override)
                if override is not None
                else self._matrix.lookup(resolved_action_class, context.authority)
            )
            if verdict == Verdict.SKIP:
                return AutonomyDecision(
                    context=context,
                    blocked=True,
                    reason="action_matrix_skip",
                )
            if mission_pack is not None and not mission_pack.is_within_boundary(
                action_name,
                action_arguments,
            ):
                return AutonomyDecision(
                    context=context,
                    requires_approval=True,
                    reason="mission_boundary_out_of_scope",
                )
            if (
                context.authority is AuthorityMode.FREEZE
                and resolved_action_class.write_side_effect is not WriteEffect.NONE
            ):
                return AutonomyDecision(
                    context=context,
                    blocked=True,
                    reason="freeze_mode_blocks_writes",
                )
            if context.authority is AuthorityMode.INCIDENT and action_name in {
                "prod_deploy",
                "email_send",
            }:
                return AutonomyDecision(
                    context=context,
                    requires_approval=True,
                    reason="incident_still_requires_approval_for_irreversible",
                )
            escalation_signals = _matched_mission_auto_escalation_signals(
                mission_pack=mission_pack,
                action_arguments=action_arguments,
                latest_review_verdict=latest_review_verdict,
                action_class=resolved_action_class,
            )
            if escalation_signals and _requires_approval_for_auto_escalation(
                action_is_safe,
                resolved_action_class,
            ):
                return AutonomyDecision(
                    context=context,
                    requires_approval=True,
                    reason="mission_auto_escalation_triggered",
                    escalation_signals=escalation_signals,
                )
            if verdict in {Verdict.ASK, Verdict.APPROVE, Verdict.DUAL}:
                return AutonomyDecision(
                    context=context,
                    requires_approval=True,
                    reason=(
                        f"mission_override_{verdict.value}"
                        if override is not None
                        else f"action_matrix_{verdict.value}"
                    ),
                )
            return AutonomyDecision(
                context=context,
                reason="mission_override_auto" if override is not None else "action_matrix_auto",
            )

        if context.authority in {AuthorityMode.SHADOW, AuthorityMode.FREEZE} and not action_is_safe:
            return AutonomyDecision(
                context=context,
                blocked=True,
                reason="authority_blocks_non_safe_actions",
            )

        if context.authority is AuthorityMode.SUPERVISED and not action_is_safe:
            return AutonomyDecision(
                context=context,
                requires_approval=True,
                reason="supervised_requires_approval_for_non_safe_actions",
            )

        escalation_signals = _matched_mission_auto_escalation_signals(
            mission_pack=mission_pack,
            action_arguments=action_arguments,
            latest_review_verdict=latest_review_verdict,
            action_class=None,
        )
        if escalation_signals and _requires_approval_for_auto_escalation(action_is_safe, None):
            return AutonomyDecision(
                context=context,
                requires_approval=True,
                reason="mission_auto_escalation_triggered",
                escalation_signals=escalation_signals,
            )

        return AutonomyDecision(context=context)


def _normalize_legacy_mode(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    if normalized == "step-by-step":
        return normalized
    if normalized in {"auto", "supervised"}:
        return normalized
    raise ValueError(f"Unsupported legacy agent mode: {value}")


def _resolve_authority(
    authority: AuthorityMode | str | None,
    mission_pack: MissionPack | None,
    legacy_mode: str | None,
) -> AuthorityMode | str:
    if authority is not None:
        return authority
    if mission_pack is not None and mission_pack.authority_default is not None:
        return mission_pack.authority_default
    return AuthorityMode.from_legacy_agent_mode(legacy_mode)


def _resolve_audience(
    audience: AudiencePersona | str | None,
    mission_pack: MissionPack | None,
    legacy_mode: str | None,
) -> AudiencePersona | str:
    if audience is not None:
        return audience
    if mission_pack is not None and mission_pack.audience_default is not None:
        return mission_pack.audience_default
    return AudiencePersona.from_legacy_agent_mode(legacy_mode)


def _is_autopilot_certified(
    mission_pack: MissionPack | None,
    certification_store: CertificationStore | None,
) -> bool:
    if mission_pack is None or mission_pack.certification is None:
        return False

    if mission_pack.certification.is_certified_for(AuthorityMode.AUTOPILOT):
        return True

    if certification_store is None:
        return False

    return certification_store.is_certified(
        mission_pack.name,
        AuthorityMode.AUTOPILOT,
        mission_version=mission_pack.version,
    )


_DIRECT_SIGNAL_ARGUMENT_KEYS = frozenset(
    {
        "mission_auto_escalation_signals",
        "mission_auto_escalate_when",
        "auto_escalation_signals",
        "auto_escalate_signals",
        "escalation_signals",
        "signals",
        "warning_types",
        "verifier_findings",
    }
)
_DIRECT_SIGNAL_VALUE_KEYS = frozenset(
    {
        "warning_type",
        "warningType",
        "signal",
        "signal_name",
        "signalName",
    }
)


def _matched_mission_auto_escalation_signals(
    *,
    mission_pack: MissionPack | None,
    action_arguments: Mapping[str, object] | None,
    latest_review_verdict: ReviewVerdict | None,
    action_class: ActionClass | None,
) -> tuple[str, ...]:
    if mission_pack is None or not mission_pack.auto_escalate_when:
        return ()

    available_signals = _collect_mission_auto_escalation_signals(
        action_arguments=action_arguments,
        latest_review_verdict=latest_review_verdict,
        action_class=action_class,
    )
    return tuple(
        signal
        for signal in mission_pack.auto_escalate_when
        if _normalize_signal(signal) in available_signals
    )


def _collect_mission_auto_escalation_signals(
    *,
    action_arguments: Mapping[str, object] | None,
    latest_review_verdict: ReviewVerdict | None,
    action_class: ActionClass | None,
) -> set[str]:
    signals: set[str] = set()
    _collect_action_argument_signals(signals, action_arguments)
    _collect_review_verdict_signals(signals, latest_review_verdict)
    if action_class is not None and action_class.name in {"prod_deploy", "staging_deploy"}:
        signals.update({"deployment_requested", "deploy_needed"})
    return signals


def _collect_action_argument_signals(
    signals: set[str],
    arguments: Mapping[str, object] | None,
) -> None:
    if arguments is None:
        return

    for key, value in arguments.items():
        if isinstance(value, bool) and value:
            _add_signal_with_aliases(signals, key)

        if key in _DIRECT_SIGNAL_ARGUMENT_KEYS or key in _DIRECT_SIGNAL_VALUE_KEYS:
            _extend_signal_values(signals, value)
            continue

        if isinstance(value, Mapping):
            _collect_action_argument_signals(signals, value)
            continue

        if (
            key in {"warnings", "issues"}
            and isinstance(value, Iterable)
            and not isinstance(value, (str, bytes))
        ):
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                for nested_key in _DIRECT_SIGNAL_VALUE_KEYS:
                    nested_value = item.get(nested_key)
                    if nested_value is not None:
                        _extend_signal_values(signals, nested_value)


def _collect_review_verdict_signals(
    signals: set[str],
    verdict: ReviewVerdict | None,
) -> None:
    if verdict is None:
        return

    confidence = verdict.confidence
    if confidence is not None and confidence.grade in {"low", "insufficient"}:
        signals.add("confidence_low")

    for issue in verdict.blocking_issues:
        _add_signal_with_aliases(signals, issue.issue_id)
        _add_signal_with_aliases(signals, issue.check_id)

    for layer in verdict.layers:
        for check in layer.checks:
            if check.status in {"warn", "fail", "error"}:
                _add_signal_with_aliases(signals, check.check_id)

    metadata = verdict.metadata
    _collect_action_argument_signals(signals, metadata)

    failures = metadata.get("mission_required_check_failures")
    _extend_signal_values(signals, failures)

    results = metadata.get("mission_required_check_results")
    if isinstance(results, Mapping):
        for check_id, status in results.items():
            normalized_status = _normalize_signal(status)
            if normalized_status not in {"pass", "passed", "ok", "success"}:
                _add_signal_with_aliases(signals, check_id)


def _extend_signal_values(signals: set[str], value: object) -> None:
    if isinstance(value, str):
        _add_signal_with_aliases(signals, value)
        return
    if isinstance(value, Mapping):
        _collect_action_argument_signals(signals, value)
        return
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for item in value:
            _extend_signal_values(signals, item)


def _add_signal_with_aliases(signals: set[str], raw: object) -> None:
    normalized = _normalize_signal(raw)
    if normalized is None:
        return
    signals.add(normalized)
    signals.update(_signal_aliases(normalized))


def _signal_aliases(signal: str) -> set[str]:
    aliases: set[str] = set()

    if signal in {"baseline_compare", "baseline_comparison"}:
        aliases.update({"baseline_compare", "baseline_comparison", "baseline_not_beaten"})
    if signal in {"sample_ratio_mismatch", "sample_ratio_mismatch_detected"}:
        aliases.update({"sample_ratio_mismatch", "sample_ratio_mismatch_detected"})
    if signal == "power_analysis":
        aliases.add("rollout_requested_without_power")
    if signal == "metric_definition_confirmed":
        aliases.update({"ambiguous_metric_definition", "metric_definition_conflict"})
    if signal == "schema_drift":
        aliases.add("source_data_untrusted")
    if "pii" in signal:
        aliases.update({"pii_detected", "sensitive_data_detected"})
    if "sensitive" in signal:
        aliases.add("sensitive_data_detected")
    if "fairness" in signal:
        aliases.add("fairness_risk_detected")

    return aliases


def _normalize_signal(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def _requires_approval_for_auto_escalation(
    action_is_safe: bool,
    action_class: ActionClass | None,
) -> bool:
    return not (action_is_safe and (action_class is None or action_class.is_read_only))
