"""Resolve mission-pack required artifacts against contract and delivery state."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.application.services.mission_required_checks import MissionPackLoaderPort
from ds_agent.domain.entities.delivery_pack import ArtifactType
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle

DELIVERY_ARTIFACT_IDS: tuple[str, ...] = tuple(artifact.value for artifact in ArtifactType)
REQUIRED_ARTIFACT_ALIASES: dict[str, tuple[str, ...]] = {
    "evaluation_report": ("ds_experiment_note",),
    "model_card": ("ml_handoff_spec",),
    "sql_notes": ("notebook", "ds_appendix"),
}


@dataclass(frozen=True)
class MissionRequiredArtifactsResolution:
    """Resolved view of one mission pack's required-artifact contract."""

    mission_name: str
    mission_loaded: bool
    required_artifacts: tuple[str, ...]
    mapped_required_artifacts: dict[str, tuple[str, ...]]
    unmapped_required_artifacts: tuple[str, ...]
    missing_contract_artifacts: tuple[str, ...]
    missing_delivery_artifacts: tuple[str, ...]

    @property
    def resolved_artifact_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for required_artifact in self.required_artifacts:
            for artifact_id in self.mapped_required_artifacts.get(required_artifact, ()):
                if artifact_id in seen:
                    continue
                ordered.append(artifact_id)
                seen.add(artifact_id)
        return tuple(ordered)


class MissionRequiredArtifactResolver:
    """Translate mission required artifacts into current delivery vocabulary."""

    def __init__(self, mission_loader: MissionPackLoaderPort | None = None) -> None:
        self._mission_loader = mission_loader

    def resolve_for_bundle(
        self,
        bundle: TaskContractBundle,
    ) -> MissionRequiredArtifactsResolution | None:
        mission_name = bundle.contract.mission
        if not mission_name:
            return None
        if self._mission_loader is None:
            return MissionRequiredArtifactsResolution(
                mission_name=mission_name,
                mission_loaded=False,
                required_artifacts=(),
                mapped_required_artifacts={},
                unmapped_required_artifacts=(),
                missing_contract_artifacts=(),
                missing_delivery_artifacts=(),
            )
        pack = self._mission_loader.try_load(mission_name)
        if pack is None:
            return MissionRequiredArtifactsResolution(
                mission_name=mission_name,
                mission_loaded=False,
                required_artifacts=(),
                mapped_required_artifacts={},
                unmapped_required_artifacts=(),
                missing_contract_artifacts=(),
                missing_delivery_artifacts=(),
            )
        return self.resolve_pack(pack, bundle)

    def resolve_pack(
        self,
        pack: MissionPack,
        bundle: TaskContractBundle,
    ) -> MissionRequiredArtifactsResolution:
        mapped: dict[str, tuple[str, ...]] = {}
        unmapped: list[str] = []
        for required_artifact in pack.required_artifacts:
            artifact_ids = _resolve_required_artifact(required_artifact)
            if artifact_ids:
                mapped[required_artifact] = artifact_ids
                continue
            unmapped.append(required_artifact)

        contract_types = {deliverable.type for deliverable in bundle.contract.required_deliverables}
        delivered_types = {
            item.deliverable_type
            for item in (bundle.delivery_pack.items if bundle.delivery_pack is not None else [])
            if item.delivered
        }
        missing_contract = [
            required_artifact
            for required_artifact in pack.required_artifacts
            if mapped.get(required_artifact)
            and not any(
                artifact_id in contract_types for artifact_id in mapped[required_artifact]
            )
        ]
        missing_delivery = [
            required_artifact
            for required_artifact in pack.required_artifacts
            if mapped.get(required_artifact)
            and not any(
                artifact_id in delivered_types for artifact_id in mapped[required_artifact]
            )
        ]
        return MissionRequiredArtifactsResolution(
            mission_name=pack.name,
            mission_loaded=True,
            required_artifacts=pack.required_artifacts,
            mapped_required_artifacts=mapped,
            unmapped_required_artifacts=tuple(unmapped),
            missing_contract_artifacts=tuple(missing_contract),
            missing_delivery_artifacts=tuple(missing_delivery),
        )


def _resolve_required_artifact(required_artifact: str) -> tuple[str, ...]:
    normalized = required_artifact.strip().lower()
    if normalized in DELIVERY_ARTIFACT_IDS:
        return (normalized,)
    return REQUIRED_ARTIFACT_ALIASES.get(normalized, ())
