"""Aggregate view of a task contract and its child artifacts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ds_agent.domain.entities.assumption_log import AssumptionEntry, AssumptionLog
from ds_agent.domain.entities.dataset_manifest import DatasetManifest
from ds_agent.domain.entities.delivery_pack import DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.metric_spec import MetricSpec
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract


class TaskContractBundle(BaseModel):
    """Aggregate used by repositories, use cases, and prompt rendering."""

    contract: TaskContract
    goal_brief: GoalBrief | None = None
    metric_specs: list[MetricSpec] = Field(default_factory=list)
    dataset_manifest: DatasetManifest | None = None
    assumption_log: AssumptionLog | None = None
    review_verdicts: list[ReviewVerdict] = Field(default_factory=list)
    delivery_pack: DeliveryPack | None = None

    def sync_references(self) -> TaskContractBundle:
        """Keep root foreign-key references aligned with loaded artifacts."""
        self.contract.goal_brief_id = self.goal_brief.brief_id if self.goal_brief else None
        self.contract.dataset_manifest_id = (
            self.dataset_manifest.manifest_id if self.dataset_manifest else None
        )
        self.contract.assumption_log_id = (
            self.assumption_log.log_id if self.assumption_log else None
        )
        self.contract.delivery_pack_id = self.delivery_pack.pack_id if self.delivery_pack else None
        self.contract.metric_spec_ids = [metric.metric_id for metric in self.metric_specs]
        self.contract.review_verdict_ids = [verdict.verdict_id for verdict in self.review_verdicts]
        return self

    @property
    def primary_metric(self) -> MetricSpec | None:
        if self.contract.primary_kpi_id:
            for metric in self.metric_specs:
                if metric.metric_id == self.contract.primary_kpi_id:
                    return metric
        for metric in self.metric_specs:
            if metric.is_primary_kpi:
                return metric
        return None

    @property
    def risky_assumptions(self) -> list[AssumptionEntry]:
        if self.assumption_log is None:
            return []
        return [
            entry
            for entry in self.assumption_log.entries
            if entry.risk_level in {"medium", "high"} and not entry.verified
        ]
