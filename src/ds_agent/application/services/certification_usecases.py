"""Autonomy certification submission and status use cases."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ds_agent.domain.entities.certification import (
    CertificationRecord,
    CertificationStats,
    certification_rank,
)
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.interfaces.certification import CertificationStore
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class MissionPackLoaderPort(Protocol):
    """Port for loading a mission pack by name."""

    def load(self, name: str) -> MissionPack: ...


@dataclass(frozen=True, slots=True)
class SubmitCertificationInput:
    """Operator request to certify a mission at a target level."""

    mission_name: str
    target_level: AuthorityMode | str
    approved_by: tuple[str, ...] = ()
    evidence_ref: str | None = None


@dataclass(frozen=True, slots=True)
class SubmitCertificationResult:
    """Outcome of certification submission."""

    mission_name: str
    mission_version: int
    target_level: AuthorityMode
    status: str
    current_level: AuthorityMode | None
    required_approvers: int
    approved_by: tuple[str, ...]
    gaps: tuple[str, ...]
    stats: CertificationStats
    certification: CertificationRecord | None = None


@dataclass(frozen=True, slots=True)
class CertificationStatusResult:
    """Mission certification status assembled from YAML + SQLite evidence."""

    mission_name: str
    mission_version: int
    current_level: AuthorityMode | None
    effective_level: AuthorityMode | None
    next_target: AuthorityMode | None
    required_approvers: int
    certified_for_next_target: bool
    gaps: tuple[str, ...]
    stats: CertificationStats
    latest_certification: CertificationRecord | None = None


class SubmitCertificationUseCase:
    """Evaluate certification readiness and persist an approval when eligible."""

    def __init__(
        self,
        mission_loader: MissionPackLoaderPort,
        certification_store: CertificationStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._mission_loader = mission_loader
        self._certification_store = certification_store
        self._clock = clock or _utc_now

    def execute(self, input_dto: SubmitCertificationInput) -> SubmitCertificationResult:
        pack = self._mission_loader.load(input_dto.mission_name)
        if pack.certification is None:
            raise ValueError(f"Mission '{pack.name}' does not define certification requirements.")

        target_level = AuthorityMode.coerce(input_dto.target_level)
        stats = self._certification_store.stats_for(pack.name, mission_version=pack.version)
        gaps = pack.certification.evaluate(target_level, stats)
        requirement = pack.certification.requirements(target_level)
        approved_by = _normalize_approvers(input_dto.approved_by)

        if gaps:
            return SubmitCertificationResult(
                mission_name=pack.name,
                mission_version=pack.version,
                target_level=target_level,
                status="pending",
                current_level=pack.certification.current_level,
                required_approvers=requirement.owner_approvals,
                approved_by=approved_by,
                gaps=gaps,
                stats=stats,
            )

        if len(approved_by) < requirement.owner_approvals:
            return SubmitCertificationResult(
                mission_name=pack.name,
                mission_version=pack.version,
                target_level=target_level,
                status="awaiting_approval",
                current_level=pack.certification.current_level,
                required_approvers=requirement.owner_approvals,
                approved_by=approved_by,
                gaps=(),
                stats=stats,
            )

        record = CertificationRecord(
            mission_name=pack.name,
            mission_version=pack.version,
            level=target_level,
            transition_from=pack.certification.current_level,
            approved_by=approved_by,
            approved_at=self._clock(),
            evidence_ref=input_dto.evidence_ref,
            next_review=pack.certification.next_review,
        )
        self._certification_store.save_certification(record)
        return SubmitCertificationResult(
            mission_name=pack.name,
            mission_version=pack.version,
            target_level=target_level,
            status="certified",
            current_level=pack.certification.current_level,
            required_approvers=requirement.owner_approvals,
            approved_by=approved_by,
            gaps=(),
            stats=stats,
            certification=record,
        )


class GetCertificationStatusUseCase:
    """Assemble effective certification status for one mission pack."""

    def __init__(
        self,
        mission_loader: MissionPackLoaderPort,
        certification_store: CertificationStore,
    ) -> None:
        self._mission_loader = mission_loader
        self._certification_store = certification_store

    def execute(self, mission_name: str) -> CertificationStatusResult:
        pack = self._mission_loader.load(mission_name)
        if pack.certification is None:
            raise ValueError(f"Mission '{pack.name}' does not define certification requirements.")

        spec = pack.certification
        stats = self._certification_store.stats_for(pack.name, mission_version=pack.version)
        latest = self._certification_store.latest_certification(
            pack.name,
            mission_version=pack.version,
        )
        effective_level = _higher_level(
            spec.current_level,
            None if latest is None else latest.level,
        )
        next_target = spec.next_target
        required_approvers = 0
        certified_for_next_target = False
        gaps: tuple[str, ...] = ()
        if next_target is not None:
            requirement = spec.requirements(next_target)
            required_approvers = requirement.owner_approvals
            certified_for_next_target = (
                spec.is_certified_for(next_target)
                or self._certification_store.is_certified(
                    pack.name,
                    next_target,
                    mission_version=pack.version,
                )
            )
            gaps = spec.evaluate(next_target, stats)

        return CertificationStatusResult(
            mission_name=pack.name,
            mission_version=pack.version,
            current_level=spec.current_level,
            effective_level=effective_level,
            next_target=next_target,
            required_approvers=required_approvers,
            certified_for_next_target=certified_for_next_target,
            gaps=gaps,
            stats=stats,
            latest_certification=latest,
        )


def _normalize_approvers(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        normalized.append(item)
        seen.add(key)
    return tuple(normalized)


def _higher_level(
    left: AuthorityMode | None,
    right: AuthorityMode | None,
) -> AuthorityMode | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if certification_rank(left) >= certification_rank(right) else right


def _utc_now() -> datetime:
    return datetime.now(UTC)
