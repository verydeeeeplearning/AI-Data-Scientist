"""Resolve mission-pack required delivery channels against persisted dispatch logs."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.application.ports.task_contract_support import DeliveryDispatchLogReader
from ds_agent.application.services.mission_required_checks import MissionPackLoaderPort
from ds_agent.domain.entities.delivery_pack import DeliveryChannel
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle

_DELIVERY_CHANNEL_IDS = frozenset(channel.value for channel in DeliveryChannel)
_SATISFIED_DISPATCH_STATUSES = frozenset({"sent", "duplicate"})


@dataclass(frozen=True)
class MissionRequiredDeliveryChannelsResolution:
    """Resolved view of one mission pack's required delivery-channel contract."""

    mission_name: str
    mission_loaded: bool
    dispatch_log_available: bool
    required_delivery_channels: tuple[str, ...]
    mapped_required_delivery_channels: dict[str, str]
    unmapped_required_delivery_channels: tuple[str, ...]
    satisfied_delivery_channels: tuple[str, ...]
    missing_delivery_channels: tuple[str, ...]
    delivery_pack_id: str | None = None

    @property
    def resolved_delivery_channels(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for required_channel in self.required_delivery_channels:
            channel = self.mapped_required_delivery_channels.get(required_channel)
            if channel is None or channel in seen:
                continue
            ordered.append(channel)
            seen.add(channel)
        return tuple(ordered)


class MissionRequiredDeliveryChannelResolver:
    """Translate mission delivery-channel requirements into persisted dispatch evidence."""

    def __init__(
        self,
        mission_loader: MissionPackLoaderPort | None = None,
        dispatch_log_reader: DeliveryDispatchLogReader | None = None,
    ) -> None:
        self._mission_loader = mission_loader
        self._dispatch_log_reader = dispatch_log_reader

    def resolve_for_bundle(
        self,
        bundle: TaskContractBundle,
    ) -> MissionRequiredDeliveryChannelsResolution | None:
        mission_name = bundle.contract.mission
        if not mission_name:
            return None
        if self._mission_loader is None:
            return MissionRequiredDeliveryChannelsResolution(
                mission_name=mission_name,
                mission_loaded=False,
                dispatch_log_available=self._dispatch_log_reader is not None,
                required_delivery_channels=(),
                mapped_required_delivery_channels={},
                unmapped_required_delivery_channels=(),
                satisfied_delivery_channels=(),
                missing_delivery_channels=(),
                delivery_pack_id=bundle.delivery_pack.pack_id if bundle.delivery_pack else None,
            )
        pack = self._mission_loader.try_load(mission_name)
        if pack is None:
            return MissionRequiredDeliveryChannelsResolution(
                mission_name=mission_name,
                mission_loaded=False,
                dispatch_log_available=self._dispatch_log_reader is not None,
                required_delivery_channels=(),
                mapped_required_delivery_channels={},
                unmapped_required_delivery_channels=(),
                satisfied_delivery_channels=(),
                missing_delivery_channels=(),
                delivery_pack_id=bundle.delivery_pack.pack_id if bundle.delivery_pack else None,
            )
        return self.resolve_pack(pack, bundle)

    def resolve_pack(
        self,
        pack: MissionPack,
        bundle: TaskContractBundle,
    ) -> MissionRequiredDeliveryChannelsResolution:
        mapped: dict[str, str] = {}
        unmapped: list[str] = []
        for required_channel in pack.required_delivery_channels:
            channel = _resolve_required_delivery_channel(required_channel)
            if channel is not None:
                mapped[required_channel] = channel
                continue
            unmapped.append(required_channel)

        delivery_pack_id = (
            bundle.delivery_pack.pack_id if bundle.delivery_pack is not None else None
        )
        if self._dispatch_log_reader is None:
            return MissionRequiredDeliveryChannelsResolution(
                mission_name=pack.name,
                mission_loaded=True,
                dispatch_log_available=False,
                required_delivery_channels=pack.required_delivery_channels,
                mapped_required_delivery_channels=mapped,
                unmapped_required_delivery_channels=tuple(unmapped),
                satisfied_delivery_channels=(),
                missing_delivery_channels=tuple(
                    required_channel
                    for required_channel in pack.required_delivery_channels
                    if required_channel in mapped
                ),
                delivery_pack_id=delivery_pack_id,
            )

        satisfied_channels: set[str] = set()
        if delivery_pack_id is not None and mapped:
            records = self._dispatch_log_reader.query(
                task_id=bundle.contract.task_id,
                pack_id=delivery_pack_id,
                channels={DeliveryChannel(channel) for channel in mapped.values()},
                limit=max(50, len(mapped) * 10),
            ).records
            satisfied_channels = {
                record.channel.value
                for record in records
                if record.status in _SATISFIED_DISPATCH_STATUSES
            }

        satisfied: list[str] = []
        missing: list[str] = []
        seen_satisfied: set[str] = set()
        for required_channel in pack.required_delivery_channels:
            mapped_channel = mapped.get(required_channel)
            if mapped_channel is None:
                continue
            if mapped_channel in satisfied_channels:
                if mapped_channel not in seen_satisfied:
                    satisfied.append(mapped_channel)
                    seen_satisfied.add(mapped_channel)
                continue
            missing.append(required_channel)

        return MissionRequiredDeliveryChannelsResolution(
            mission_name=pack.name,
            mission_loaded=True,
            dispatch_log_available=True,
            required_delivery_channels=pack.required_delivery_channels,
            mapped_required_delivery_channels=mapped,
            unmapped_required_delivery_channels=tuple(unmapped),
            satisfied_delivery_channels=tuple(satisfied),
            missing_delivery_channels=tuple(missing),
            delivery_pack_id=delivery_pack_id,
        )


def _resolve_required_delivery_channel(required_channel: str) -> str | None:
    normalized = required_channel.strip().lower().replace("-", "_")
    if normalized in _DELIVERY_CHANNEL_IDS:
        return normalized
    return None
