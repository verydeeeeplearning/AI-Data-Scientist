"""Usage summary service for cost-governance surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from ds_agent.runtime.organization_store import JsonOrganizationStore

DEFAULT_WARNING_THRESHOLD_PCT = 80.0


@dataclass(slots=True)
class UsageSummary:
    actor_id: str
    monthly_cost_usd: float
    monthly_budget_usd: float | None
    budget_used_pct: float
    cache_savings_usd: float
    session_cost_usd: float
    today_cost_usd: float
    remaining_budget_usd: float | None
    month_run_count: int
    warning_level: str
    warning_threshold_pct: float
    by_model: list[dict[str, object]]
    recent_runs: list[dict[str, object]]

    @property
    def limit_exceeded(self) -> bool:
        return self.warning_level == "exhausted"

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        return {
            "actorId": payload["actor_id"],
            "monthlyCostUsd": payload["monthly_cost_usd"],
            "monthlyBudgetUsd": payload["monthly_budget_usd"],
            "budgetUsedPct": payload["budget_used_pct"],
            "cacheSavingsUsd": payload["cache_savings_usd"],
            "sessionCostUsd": payload["session_cost_usd"],
            "todayCostUsd": payload["today_cost_usd"],
            "remainingBudgetUsd": payload["remaining_budget_usd"],
            "monthRunCount": payload["month_run_count"],
            "warningLevel": payload["warning_level"],
            "warningThresholdPct": payload["warning_threshold_pct"],
            "limitExceeded": self.limit_exceeded,
            "byModel": payload["by_model"],
            "recentRuns": payload["recent_runs"],
        }


class UsageSummaryService:
    """Build monthly, daily, and per-session usage summaries."""

    def __init__(self, usage_store: JsonOrganizationStore) -> None:
        self._usage_store = usage_store

    def get_summary(
        self,
        *,
        actor_id: str,
        monthly_budget_usd: float | None,
        warning_threshold_pct: float = DEFAULT_WARNING_THRESHOLD_PCT,
        current_session_id: str | None = None,
        now: float | None = None,
    ) -> UsageSummary:
        month_start, month_end = self._usage_store.month_range(now)
        today_start, today_end = self._day_range(now)
        monthly_records = self._usage_store.list_usage_records(
            start_ts=month_start,
            end_ts=month_end,
            actor_id=actor_id,
        )
        today_records = self._usage_store.list_usage_records(
            start_ts=today_start,
            end_ts=today_end,
            actor_id=actor_id,
        )
        monthly_cost = sum(record.cost_usd for record in monthly_records)
        today_cost = sum(record.cost_usd for record in today_records)
        session_cost = (
            sum(
                record.cost_usd
                for record in monthly_records
                if record.session_id == current_session_id
            )
            if current_session_id
            else 0.0
        )
        cache_savings = sum(record.cache_savings_usd for record in monthly_records)
        budget = (
            float(monthly_budget_usd)
            if monthly_budget_usd is not None and float(monthly_budget_usd) > 0
            else None
        )
        threshold_pct = min(max(float(warning_threshold_pct), 1.0), 99.0)
        budget_used_pct = (monthly_cost / budget) * 100 if budget else 0.0
        remaining_budget = None if budget is None else max(budget - monthly_cost, 0.0)
        if budget is not None and monthly_cost >= budget:
            warning_level = "exhausted"
        elif budget is not None and budget_used_pct >= threshold_pct:
            warning_level = "warning"
        else:
            warning_level = "ok"

        by_model_map: dict[str, dict[str, object]] = {}
        for record in monthly_records:
            key = record.model or record.provider or "unknown"
            summary = by_model_map.setdefault(
                key,
                {
                    "model": key,
                    "provider": record.provider,
                    "costUsd": 0.0,
                    "runCount": 0,
                },
            )
            summary["costUsd"] = float(summary["costUsd"]) + record.cost_usd  # type: ignore[arg-type]
            summary["runCount"] = int(summary["runCount"]) + 1  # type: ignore[call-overload]

        recent_runs = [
            {
                "runId": record.run_id,
                "sessionId": record.session_id,
                "provider": record.provider,
                "model": record.model,
                "costUsd": record.cost_usd,
                "cacheSavingsUsd": record.cache_savings_usd,
                "recordedAt": record.recorded_at,
            }
            for record in monthly_records[:5]
        ]

        return UsageSummary(
            actor_id=actor_id,
            monthly_cost_usd=monthly_cost,
            monthly_budget_usd=budget,
            budget_used_pct=budget_used_pct,
            cache_savings_usd=cache_savings,
            session_cost_usd=session_cost,
            today_cost_usd=today_cost,
            remaining_budget_usd=remaining_budget,
            month_run_count=len(monthly_records),
            warning_level=warning_level,
            warning_threshold_pct=threshold_pct,
            by_model=sorted(
                by_model_map.values(),
                key=lambda item: (-float(item["costUsd"]), str(item["model"])),  # type: ignore[arg-type]
            ),
            recent_runs=[dict(r) for r in recent_runs],
        )

    @staticmethod
    def _day_range(now: float | None = None) -> tuple[float, float]:
        dt = datetime.fromtimestamp(datetime.now().timestamp() if now is None else now)
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start.timestamp(), end.timestamp()
