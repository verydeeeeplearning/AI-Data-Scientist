"""Task contract use cases."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ds_agent.application.dtos.task_contract import (
    AssumptionInputDTO,
    BuildDeliveryPackDTO,
    DeliveryPackInputDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    ReviewVerdictInputDTO,
    TaskContractDraftDTO,
    TaskContractListItemDTO,
    TaskContractUpdateDTO,
    TaskContractViewDTO,
    VerifyAssumptionDTO,
)
from ds_agent.application.ports.task_contract_support import (
    Clock,
    DeliveryArtifactDispatcher,
    DeliveryArtifactRenderer,
    DeliveryDispatchLogReader,
    EventPublisher,
    IdGenerator,
)
from ds_agent.domain.entities.assumption_log import AssumptionEntry, AssumptionLog
from ds_agent.domain.entities.delivery_pack import (
    AudienceKind,
    DeliveryArtifact,
    DeliveryItem,
    DeliveryPack,
    DeliveryPackStatus,
)
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.task_contract import (
    AutonomyBoundary,
    Budget,
    DataSourceGrant,
    DefinitionOfDone,
    DeliverableSpec,
    TaskContract,
    TaskContractStatus,
)
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import (
    TaskContractNotFoundError,
    VersionConflictError,
)
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.domain.services.delivery_pack_planner import plan_delivery_artifact
from ds_agent.domain.services.task_contract_state_machine import (
    TaskContractStateMachine,
    TaskContractValidator,
)

_PATCHABLE_FIELDS = frozenset(
    {
        "type",
        "business_goal",
        "primary_kpi_id",
        "secondary_kpi_ids",
        "decision_owner",
        "decision_deadline",
        "allowed_data_sources",
        "forbidden_data_patterns",
        "budget",
        "required_deliverables",
        "autonomy",
        "definition_of_done",
        "authority",
        "audience",
        "mission",
    }
)


def _normalize_delivery_audience(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "peer_ds": AudienceKind.DS_PEER.value,
        "junior_mentor": AudienceKind.JUNIOR_MENTEE.value,
    }
    return aliases.get(normalized, normalized)


class _BaseTaskContractUseCase:
    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        publisher: EventPublisher,
    ) -> None:
        self._store = store
        self._clock = clock
        self._publisher = publisher

    def _load_bundle(self, task_id: str) -> TaskContractBundle:
        bundle = self._store.get_bundle(task_id)
        if bundle is None:
            raise TaskContractNotFoundError(f"Task contract not found: {task_id}")
        return bundle

    @staticmethod
    def _build_event(
        *,
        event_type: str,
        task_id: str,
        occurred_at: datetime,
        payload: dict[str, Any],
    ) -> TaskContractEvent:
        return TaskContractEvent(
            event_type=event_type,
            task_id=task_id,
            occurred_at=occurred_at,
            payload=payload,
        )

    def _publish(self, event: TaskContractEvent) -> None:
        self._publisher.publish(event)

    @staticmethod
    def _ensure_version(contract: TaskContract, expected_version: int) -> None:
        if contract.version != expected_version:
            raise VersionConflictError(
                f"Expected version {expected_version}, got {contract.version}"
            )

    @staticmethod
    def _apply_patch(contract: TaskContract, patch: dict[str, Any]) -> TaskContract:
        invalid = sorted(key for key in patch if key not in _PATCHABLE_FIELDS)
        if invalid:
            raise ValueError(f"Unsupported patch fields: {', '.join(invalid)}")

        payload = contract.model_dump(mode="python")
        for key, value in patch.items():
            if key == "budget":
                payload[key] = Budget.model_validate(value)
            elif key == "autonomy":
                payload[key] = AutonomyBoundary.model_validate(value)
            elif key == "allowed_data_sources":
                payload[key] = [DataSourceGrant.model_validate(item) for item in value]
            elif key == "required_deliverables":
                payload[key] = [DeliverableSpec.model_validate(item) for item in value]
            elif key == "definition_of_done":
                payload[key] = None if value is None else DefinitionOfDone.model_validate(value)
            else:
                payload[key] = value
        return TaskContract.model_validate(payload)


class CreateTaskContractUseCase(_BaseTaskContractUseCase):
    """Create a new draft task contract and linked goal brief."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        ids: IdGenerator,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._ids = ids

    def execute(self, dto: TaskContractDraftDTO) -> dict[str, Any]:
        now = self._clock.now()
        task_id = self._ids.new_task_id(now)
        goal_brief = GoalBrief(
            brief_id=self._ids.new_artifact_id("GB"),
            task_id=task_id,
            created_at=now,
            updated_at=now,
            **dto.goal_brief.model_dump(),
        )
        assumption_log = AssumptionLog(
            log_id=self._ids.new_artifact_id("AL"),
            task_id=task_id,
        )
        contract = TaskContract(
            task_id=task_id,
            session_id=dto.session_id,
            type=dto.contract_type,
            status=TaskContractStatus.DRAFT,
            business_goal=dto.business_goal,
            decision_owner=dto.decision_owner,
            decision_deadline=dto.decision_deadline,
            allowed_data_sources=dto.allowed_data_sources,
            forbidden_data_patterns=dto.forbidden_data_patterns,
            budget=dto.budget,
            required_deliverables=dto.required_deliverables,
            autonomy=dto.autonomy,
            definition_of_done=dto.definition_of_done,
            authority=dto.authority,
            audience=dto.audience,
            mission=dto.mission,
            goal_brief_id=goal_brief.brief_id,
            assumption_log_id=assumption_log.log_id,
            created_at=now,
            updated_at=now,
            created_by="user" if dto.created_by == "user" else "agent",
        )
        bundle = TaskContractBundle(
            contract=contract,
            goal_brief=goal_brief,
            assumption_log=assumption_log,
        ).sync_references()
        event = self._build_event(
            event_type="task_contract.created",
            task_id=task_id,
            occurred_at=now,
            payload={"status": contract.status.value},
        )
        self._store.create_bundle(bundle, events=[event])
        self._publish(event)
        return {
            "task_id": task_id,
            "status": contract.status.value,
            "goal_brief_id": goal_brief.brief_id,
            "new_version": contract.version,
            "next_suggested_action": "사용자에게 초안 확인 요청",
        }


class UpdateTaskContractUseCase(_BaseTaskContractUseCase):
    """Patch a contract and optionally transition its status."""

    def execute(self, dto: TaskContractUpdateDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        self._ensure_version(bundle.contract, dto.expected_version)
        now = self._clock.now()
        updated_contract = self._apply_patch(bundle.contract, dto.patch)
        bundle.contract = updated_contract
        if dto.transition_to is not None:
            TaskContractStateMachine.validate_transition(bundle, dto.transition_to)
            bundle.contract.status = dto.transition_to
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.updated"
            if dto.transition_to is None
            else "task_contract.state_transition",
            task_id=bundle.contract.task_id,
            occurred_at=now,
            payload={
                "status": bundle.contract.status.value,
                "reason": dto.reason,
                "patch_fields": sorted(dto.patch.keys()),
            },
        )
        self._store.save_bundle(bundle, expected_version=dto.expected_version, events=[event])
        self._publish(event)
        return {
            "task_id": bundle.contract.task_id,
            "status": bundle.contract.status.value,
            "new_version": bundle.contract.version,
        }


class AddAssumptionUseCase(_BaseTaskContractUseCase):
    """Append an assumption and touch the parent contract."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        ids: IdGenerator,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._ids = ids

    def execute(self, dto: AssumptionInputDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        if bundle.assumption_log is None:
            bundle.assumption_log = AssumptionLog(
                log_id=self._ids.new_artifact_id("AL"),
                task_id=dto.task_id,
            )
        now = self._clock.now()
        previous_version = bundle.contract.version
        entry = AssumptionEntry(
            entry_id=self._ids.new_artifact_id("AS"),
            statement=dto.statement,
            rationale=dto.rationale,
            risk_level=dto.risk_level,
            asked_user=dto.asked_user,
            created_at=now,
        )
        bundle.assumption_log.entries.append(entry)
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.assumption_added",
            task_id=dto.task_id,
            occurred_at=now,
            payload={
                "entry_id": entry.entry_id,
                "risk_level": entry.risk_level,
            },
        )
        self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
        self._publish(event)
        return {
            "entry_id": entry.entry_id,
            "requires_user_confirmation": entry.risk_level == "high" and not entry.asked_user,
            "new_version": bundle.contract.version,
        }


class VerifyAssumptionUseCase(_BaseTaskContractUseCase):
    """Mark a persisted assumption as verified and record the verification note."""

    def execute(self, dto: VerifyAssumptionDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        if bundle.contract.version != dto.expected_version:
            raise VersionConflictError(
                f"Task contract version mismatch: expected {dto.expected_version}, "
                f"found {bundle.contract.version}"
            )
        if bundle.assumption_log is None:
            raise ValueError(f"Assumption log not found for task contract: {dto.task_id}")

        entry = next(
            (item for item in bundle.assumption_log.entries if item.entry_id == dto.entry_id),
            None,
        )
        if entry is None:
            raise ValueError(f"Assumption entry not found: {dto.entry_id}")
        if entry.verified:
            raise ValueError(f"Assumption entry already verified: {dto.entry_id}")

        now = self._clock.now()
        entry.verified = True
        entry.verification_note = (
            dto.verification_note.strip() if dto.verification_note is not None else None
        ) or None
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.assumption_verified",
            task_id=dto.task_id,
            occurred_at=now,
            payload={
                "entry_id": entry.entry_id,
                "verification_note": entry.verification_note,
            },
        )
        self._store.save_bundle(bundle, expected_version=dto.expected_version, events=[event])
        self._publish(event)
        return {
            "entry_id": entry.entry_id,
            "verified": True,
            "verification_note": entry.verification_note,
            "new_version": bundle.contract.version,
        }


class RecordReviewVerdictUseCase(_BaseTaskContractUseCase):
    """Persist one review verdict."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        ids: IdGenerator,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._ids = ids

    def execute(self, dto: ReviewVerdictInputDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        now = self._clock.now()
        previous_version = bundle.contract.version
        verdict = ReviewVerdict(
            verdict_id=dto.verdict_id or self._ids.new_artifact_id("RV"),
            task_id=dto.task_id,
            category=dto.category,
            result=dto.result,
            reviewer=dto.reviewer,
            summary=dto.summary,
            evidence_refs=dto.evidence_refs,
            created_at=now,
            run_id=dto.run_id,
            layers=dto.layers,
            blocking_issues=dto.blocking_issues,
            confidence=dto.confidence,
            recommended_actions=dto.recommended_actions,
            metadata=dto.metadata,
        )
        bundle.review_verdicts.append(verdict)
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.review_verdict_recorded",
            task_id=dto.task_id,
            occurred_at=now,
            payload={
                "verdict_id": verdict.verdict_id,
                "result": verdict.result,
                "category": verdict.category,
            },
        )
        self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
        self._publish(event)
        return {
            "verdict_id": verdict.verdict_id,
            "result": verdict.result,
            "new_version": bundle.contract.version,
        }


class BuildDeliveryPackUseCase(_BaseTaskContractUseCase):
    """Derive a typed stakeholder delivery pack from required deliverables."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        ids: IdGenerator,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._ids = ids

    def execute(self, dto: BuildDeliveryPackDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        now = self._clock.now()
        previous_version = bundle.contract.version
        selected_audiences = (
            {_normalize_delivery_audience(value) for value in dto.audiences}
            if dto.audiences
            else None
        )

        artifacts = []
        planned_audiences: set[str] = set()
        for deliverable in bundle.contract.required_deliverables:
            normalized_audience = _normalize_delivery_audience(deliverable.audience)
            if selected_audiences is not None and normalized_audience not in selected_audiences:
                continue
            artifacts.append(
                plan_delivery_artifact(
                    deliverable,
                    artifact_id=self._ids.new_artifact_id("DA"),
                )
            )
            planned_audiences.add(normalized_audience)

        if not artifacts:
            raise ValueError("No required deliverables matched the requested audiences")

        if selected_audiences is not None:
            missing = sorted(selected_audiences - planned_audiences)
            if missing:
                raise ValueError(
                    "Requested delivery audiences are not present in required_deliverables: "
                    + ", ".join(missing)
                )

        delivery_pack = DeliveryPack(
            pack_id=self._ids.new_artifact_id("DP"),
            task_id=dto.task_id,
            follow_up_actions=dto.follow_up_actions,
            generated_at=now,
            source_analysis_id=dto.source_analysis_id,
            confidence=dto.confidence or 1.0,
            signed_by=dto.signed_by or "ds-agent",
            signature=dto.signature,
            global_context=dto.global_context,
            artifacts=artifacts,
            status=DeliveryPackStatus.DRAFT,
            tenant=dto.tenant,
        )
        bundle.delivery_pack = delivery_pack
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.delivery_pack_built",
            task_id=dto.task_id,
            occurred_at=now,
            payload={
                "pack_id": delivery_pack.pack_id,
                "artifact_count": len(delivery_pack.artifacts),
                "audiences": [artifact.audience.value for artifact in delivery_pack.artifacts],
                "status": delivery_pack.status.value,
            },
        )
        self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
        self._publish(event)
        return {
            "pack_id": delivery_pack.pack_id,
            "items": len(delivery_pack.items),
            "artifacts": len(delivery_pack.artifacts),
            "audiences": [artifact.audience.value for artifact in delivery_pack.artifacts],
            "artifact_ids": [artifact.artifact_id for artifact in delivery_pack.artifacts],
            "status": delivery_pack.status.value,
            "new_version": bundle.contract.version,
        }


class RenderDeliveryArtifactUseCase(_BaseTaskContractUseCase):
    """Render one persisted delivery artifact and update the stored delivery pack."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        publisher: EventPublisher,
        renderer: DeliveryArtifactRenderer,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._renderer = renderer

    def execute(self, dto: RenderDeliveryArtifactDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        if bundle.delivery_pack is None:
            raise ValueError("A delivery pack must be built before artifacts can be rendered")

        artifact = next(
            (
                candidate
                for candidate in bundle.delivery_pack.artifacts
                if candidate.artifact_id == dto.artifact_id
            ),
            None,
        )
        if artifact is None:
            raise ValueError(f"Unknown delivery artifact: {dto.artifact_id}")

        rendered = self._renderer.render(
            pack=bundle.delivery_pack,
            artifact_id=dto.artifact_id,
            analysis=dto.analysis,
            output_dir=Path(dto.output_dir),
            audience_profile=dto.audience_profile,
        )

        updated_artifacts = [
            item.model_copy(
                update={
                    "rendered_uri": str(rendered.output_path),
                    "verifier_report_id": rendered.verifier_report_id,
                }
            )
            if item.artifact_id == dto.artifact_id
            else item
            for item in bundle.delivery_pack.artifacts
        ]
        next_status = (
            DeliveryPackStatus.REJECTED
            if rendered.verifier_status == "rejected"
            else DeliveryPackStatus.RENDERED
        )
        pack_payload = bundle.delivery_pack.model_dump(mode="python")
        pack_payload.update(
            {
                "artifacts": updated_artifacts,
                "items": [],
                "generated_at": self._clock.now(),
                "status": next_status,
            }
        )
        bundle.delivery_pack = DeliveryPack.model_validate(pack_payload)
        previous_version = bundle.contract.version
        bundle.contract.updated_at = self._clock.now()
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.delivery_artifact_rendered",
            task_id=dto.task_id,
            occurred_at=bundle.contract.updated_at,
            payload={
                "pack_id": bundle.delivery_pack.pack_id,
                "artifact_id": dto.artifact_id,
                "output_path": str(rendered.output_path),
                "verifier_status": rendered.verifier_status,
                "pack_status": bundle.delivery_pack.status.value,
            },
        )
        self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
        self._publish(event)
        return {
            "pack_id": bundle.delivery_pack.pack_id,
            "artifact_id": dto.artifact_id,
            "output_path": str(rendered.output_path),
            "format": rendered.format.value,
            "verifier_status": rendered.verifier_status,
            "verifier_report_id": rendered.verifier_report_id,
            "flagged_claims": list(rendered.flagged_claims),
            "pack_status": bundle.delivery_pack.status.value,
            "new_version": bundle.contract.version,
        }


class DispatchDeliveryUseCase(_BaseTaskContractUseCase):
    """Dispatch rendered delivery-pack artifacts through channel adapters."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        publisher: EventPublisher,
        dispatcher: DeliveryArtifactDispatcher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._dispatcher = dispatcher

    def execute(self, dto: DispatchDeliveryDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        if bundle.delivery_pack is None:
            raise ValueError("A delivery pack must exist before dispatch can run")
        if bundle.delivery_pack.status == DeliveryPackStatus.REJECTED:
            raise ValueError("Rejected delivery packs cannot be dispatched")

        result = self._dispatcher.dispatch(
            pack=bundle.delivery_pack,
            artifact_ids=set(dto.artifact_ids) or None,
            channels=set(dto.channels) or None,
            dry_run=dto.dry_run,
            approve_manual_review=dto.approve_manual_review,
        )

        pack_status = bundle.delivery_pack.status
        new_version = bundle.contract.version

        if not dto.dry_run:
            successful_channels = {
                receipt.artifact_id: receipt.channel.value
                for receipt in result.receipts
                if receipt.status in {"sent", "duplicate"}
            }
            pack_payload = bundle.delivery_pack.model_dump(mode="python")
            if successful_channels:
                pack_payload["items"] = [
                    item.model_copy(
                        update={
                            "delivered": True,
                            "delivery_channel": successful_channels.get(
                                item.artifact_id,
                                item.delivery_channel,
                            ),
                        }
                    )
                    if item.artifact_id in successful_channels
                    else item
                    for item in bundle.delivery_pack.items
                ]
            if result.dispatch_status == "dispatched":
                pack_status = DeliveryPackStatus.DISPATCHED
                pack_payload["status"] = pack_status
            bundle.delivery_pack = DeliveryPack.model_validate(pack_payload)
            previous_version = bundle.contract.version
            bundle.contract.updated_at = self._clock.now()
            bundle.contract.version += 1
            new_version = bundle.contract.version
            bundle.sync_references()
            event = self._build_event(
                event_type="task_contract.delivery_dispatched",
                task_id=dto.task_id,
                occurred_at=bundle.contract.updated_at,
                payload={
                    "pack_id": bundle.delivery_pack.pack_id,
                    "dispatch_status": result.dispatch_status,
                    "artifact_ids": sorted(set(dto.artifact_ids)),
                    "channels": [channel.value for channel in dto.channels],
                    "sent": result.sent_count,
                    "blocked": result.blocked_count,
                    "failed": result.failed_count,
                    "duplicates": result.duplicate_count,
                    "pack_status": pack_status.value,
                },
            )
            self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
            self._publish(event)

        payload = result.model_dump(mode="json")
        payload.update(
            {
                "sent": result.sent_count,
                "blocked": result.blocked_count,
                "failed": result.failed_count,
                "duplicates": result.duplicate_count,
                "pack_status": pack_status.value,
                "new_version": new_version,
            }
        )
        return payload


class ListDeliveryLogUseCase(_BaseTaskContractUseCase):
    """Load persisted delivery dispatch-log records for one task contract."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        publisher: EventPublisher,
        reader: DeliveryDispatchLogReader,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._reader = reader

    def execute(self, dto: ListDeliveryLogDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        result = self._reader.query(
            task_id=dto.task_id,
            pack_id=dto.pack_id,
            artifact_ids=set(dto.artifact_ids) or None,
            channels=set(dto.channels) or None,
            limit=dto.limit,
        )
        if bundle.delivery_pack is not None and (
            dto.pack_id is None or dto.pack_id == bundle.delivery_pack.pack_id
        ):
            result = result.model_copy(
                update={"summary": self._reader.summarize(pack=bundle.delivery_pack)}
            )
        payload = result.model_dump(mode="json")
        payload["returned"] = result.returned
        return payload


class RecordDeliveryPackUseCase(_BaseTaskContractUseCase):
    """Persist a rendered delivery pack."""

    def __init__(
        self,
        store: TaskContractStore,
        clock: Clock,
        ids: IdGenerator,
        publisher: EventPublisher,
    ) -> None:
        super().__init__(store=store, clock=clock, publisher=publisher)
        self._ids = ids

    def execute(self, dto: DeliveryPackInputDTO) -> dict[str, Any]:
        bundle = self._load_bundle(dto.task_id)
        now = self._clock.now()
        previous_version = bundle.contract.version
        delivery_pack = DeliveryPack(
            pack_id=self._ids.new_artifact_id("DP"),
            task_id=dto.task_id,
            items=[DeliveryItem.model_validate(item) for item in dto.items],
            follow_up_actions=dto.follow_up_actions,
            generated_at=now,
            source_analysis_id=dto.source_analysis_id,
            confidence=dto.confidence or 1.0,
            signed_by=dto.signed_by or "ds-agent",
            signature=dto.signature,
            global_context=dto.global_context,
            artifacts=[DeliveryArtifact.model_validate(item) for item in dto.artifacts],
            status=DeliveryPackStatus(dto.status),
            tenant=dto.tenant,
        )
        bundle.delivery_pack = delivery_pack
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        event = self._build_event(
            event_type="task_contract.delivery_pack_recorded",
            task_id=dto.task_id,
            occurred_at=now,
            payload={"pack_id": delivery_pack.pack_id, "items": len(delivery_pack.items)},
        )
        self._store.save_bundle(bundle, expected_version=previous_version, events=[event])
        self._publish(event)
        return {
            "pack_id": delivery_pack.pack_id,
            "items": len(delivery_pack.items),
            "artifacts": len(delivery_pack.artifacts),
            "status": delivery_pack.status.value,
            "new_version": bundle.contract.version,
        }


class GetTaskContractUseCase(_BaseTaskContractUseCase):
    """Load a detailed contract view."""

    def execute(self, task_id: str, include: list[str] | None = None) -> TaskContractViewDTO:
        bundle = self._load_bundle(task_id)
        include_set = set(include) if include is not None else None
        return TaskContractViewDTO.from_bundle(
            bundle,
            include=include_set,
            dod_summary=TaskContractValidator.build_dod_summary(bundle),
        )


class ListTaskContractsUseCase(_BaseTaskContractUseCase):
    """List contracts for one session."""

    def execute(
        self,
        session_id: str | None = None,
        *,
        status_filter: list[TaskContractStatus] | None = None,
        limit: int = 20,
    ) -> list[TaskContractListItemDTO]:
        contracts = self._store.list_contracts(
            session_id,
            statuses=status_filter,
            limit=limit,
        )
        return [TaskContractListItemDTO.from_contract(contract) for contract in contracts]


class CloseTaskContractUseCase(_BaseTaskContractUseCase):
    """Transition a contract from review to closed."""

    def execute(self, task_id: str, *, expected_version: int, closing_note: str) -> dict[str, Any]:
        bundle = self._load_bundle(task_id)
        self._ensure_version(bundle.contract, expected_version)
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)
        now = self._clock.now()
        bundle.contract.status = TaskContractStatus.CLOSED
        bundle.contract.updated_at = now
        bundle.contract.version += 1
        bundle.sync_references()
        dod_summary = TaskContractValidator.build_dod_summary(bundle)
        event = self._build_event(
            event_type="task_contract.closed",
            task_id=task_id,
            occurred_at=now,
            payload={"closing_note": closing_note, "dod_summary": dod_summary},
        )
        self._store.save_bundle(bundle, expected_version=expected_version, events=[event])
        self._publish(event)
        return {
            "task_id": bundle.contract.task_id,
            "status": bundle.contract.status.value,
            "new_version": bundle.contract.version,
            "dod_summary": dod_summary,
        }
