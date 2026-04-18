"""Build a regression-board snapshot from persisted eval records."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from statistics import fmean, median
from typing import Literal

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardBaseline,
    RegressionBoardPoint,
    RegressionBoardSnapshot,
    RegressionDimensionSummary,
    RegressionModeSummary,
    RegressionOverallSummary,
    RegressionTaskSummary,
    RegressionWindowStats,
)
from ds_agent.evaluation.domain.ports.eval_dataset_store import EvalDatasetStore
from ds_agent.evaluation.domain.ports.regression_baseline_store import RegressionBaselineStore

_OVERALL_PASS_RATE_DROP_THRESHOLD = 0.03
_DIMENSION_REGRESSION_THRESHOLD = 0.05
_ONLINE_OFFLINE_DRIFT_THRESHOLD = 0.10
_SECONDS_PER_DAY = 86_400


class BuildRegressionBoard:
    """Aggregate rolling regression metrics from the eval dataset."""

    def __init__(
        self,
        eval_store: EvalDatasetStore,
        *,
        baseline_store: RegressionBaselineStore | None = None,
    ) -> None:
        self._eval_store = eval_store
        self._baseline_store = baseline_store

    def execute(
        self,
        *,
        axis: str = "commit",
        task_catalog: tuple[GoldTask, ...] | list[GoldTask] = (),
        mode: str | None = None,
        domain: str | None = None,
        task_id: str | None = None,
        limit: int | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
    ) -> RegressionBoardSnapshot:
        resolved_axis = _normalize_axis(axis)
        tasks_by_id = {task.id: task for task in task_catalog}
        all_records = self._sorted_records(self._eval_store.load_all())
        filtered_records = [
            record
            for record in all_records
            if self._record_matches(
                record,
                tasks_by_id=tasks_by_id,
                mode=mode,
                domain=domain,
                task_id=task_id,
            )
        ]
        axis_groups = self._ordered_axis_groups(filtered_records, axis=resolved_axis)
        if limit is not None and limit > 0:
            axis_groups = axis_groups[-limit:]
        points = self._build_points(axis_groups)
        latest_point_records = axis_groups[-1][1] if axis_groups else []
        recent_records = filtered_records[-recent_window:]
        baseline_records = self._select_baseline_records(
            filtered_records,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
        )
        frozen_baseline = self._select_frozen_baseline(
            axis_kind=resolved_axis,
            mode=mode,
            domain=domain,
            task_id=task_id,
        )
        overall = RegressionOverallSummary(
            recent=(
                self._point_to_window_stats(points[-1])
                if points
                else self._build_window_stats(recent_records)
            ),
            baseline=self._build_baseline_window_stats(
                baseline_records,
                frozen_baseline=frozen_baseline,
            ),
            delta_score=self._delta(
                (
                    points[-1].weighted_score_mean
                    if points
                    else self._average_weighted_score(recent_records)
                ),
                self._baseline_average_weighted_score(
                    baseline_records,
                    frozen_baseline=frozen_baseline,
                ),
            ),
            delta_pass_rate=self._delta(
                points[-1].pass_rate if points else self._pass_rate(recent_records),
                self._baseline_pass_rate(
                    baseline_records,
                    frozen_baseline=frozen_baseline,
                ),
            ),
        )
        task_summaries = self._build_task_summaries(
            filtered_records,
            tasks_by_id=tasks_by_id,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
            frozen_baseline=frozen_baseline,
        )
        dimension_summaries = self._build_dimension_summaries(
            latest_point_records or recent_records,
            baseline_records,
            frozen_baseline=frozen_baseline,
        )
        mode_summaries = self._build_mode_summaries(filtered_records)
        alerts = self._build_alerts(
            overall=overall,
            task_summaries=task_summaries,
            dimension_summaries=dimension_summaries,
            mode_summaries=mode_summaries,
        )
        available_domains = self._available_domains(
            all_records,
            tasks_by_id=tasks_by_id,
            mode=mode,
        )
        return RegressionBoardSnapshot(
            total_records=len(filtered_records),
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
            axis_kind=resolved_axis,
            mode_filter=mode,
            domain_filter=domain,
            baseline_source="frozen" if frozen_baseline is not None else "rolling",
            available_domains=available_domains,
            overall=overall,
            points=tuple(points),
            mode_summaries=tuple(mode_summaries),
            task_summaries=tuple(task_summaries),
            dimension_summaries=tuple(dimension_summaries),
            alerts=tuple(alerts),
            frozen_baseline=frozen_baseline,
        )

    @staticmethod
    def _sorted_records(records: list[EvalDatasetRecord]) -> list[EvalDatasetRecord]:
        return sorted(records, key=lambda item: (item.recorded_at, item.run_id))

    @staticmethod
    def _record_matches(
        record: EvalDatasetRecord,
        *,
        tasks_by_id: dict[str, GoldTask],
        mode: str | None,
        domain: str | None,
        task_id: str | None,
    ) -> bool:
        if mode is not None and record.mode != mode:
            return False
        if task_id is not None and record.task_id != task_id:
            return False
        if domain is None:
            return True
        task = tasks_by_id.get(record.task_id)
        if task is not None:
            return task.domain == domain
        metadata_domain = (
            record.run_metadata.get("taskDomain") or record.run_metadata.get("domain")
        )
        return str(metadata_domain) == domain if metadata_domain is not None else False

    def _ordered_axis_groups(
        self,
        records: list[EvalDatasetRecord],
        *,
        axis: str,
    ) -> list[tuple[str, list[EvalDatasetRecord]]]:
        grouped: dict[str, list[EvalDatasetRecord]] = defaultdict(list)
        for record in records:
            grouped[_axis_key(record, axis=axis)].append(record)
        ordered = sorted(
            grouped.items(),
            key=lambda item: min(record.recorded_at for record in item[1]),
        )
        return [(axis_key, self._sorted_records(items)) for axis_key, items in ordered]

    def _build_points(
        self,
        axis_groups: list[tuple[str, list[EvalDatasetRecord]]],
    ) -> list[RegressionBoardPoint]:
        points: list[RegressionBoardPoint] = []
        for axis_key, records in axis_groups:
            points.append(
                RegressionBoardPoint(
                    axis_key=axis_key,
                    axis_label=axis_key,
                    run_count=len(records),
                    pass_rate=self._pass_rate(records) or 0.0,
                    weighted_score_mean=self._average_weighted_score(records) or 0.0,
                    per_dimension_means=_mean_dimension_scores(records),
                    per_mode_weighted_scores=_mean_mode_scores(records),
                )
            )
        return points

    def _available_domains(
        self,
        records: list[EvalDatasetRecord],
        *,
        tasks_by_id: dict[str, GoldTask],
        mode: str | None,
    ) -> tuple[str, ...]:
        domains = set[str]()
        for record in records:
            if mode is not None and record.mode != mode:
                continue
            task = tasks_by_id.get(record.task_id)
            if task is not None:
                domains.add(task.domain)
                continue
            metadata_domain = (
                record.run_metadata.get("taskDomain") or record.run_metadata.get("domain")
            )
            if metadata_domain is not None:
                domains.add(str(metadata_domain))
        return tuple(sorted(domains))

    def _select_baseline_records(
        self,
        records: list[EvalDatasetRecord],
        *,
        recent_window: int,
        baseline_window_days: int,
    ) -> list[EvalDatasetRecord]:
        if not records:
            return []
        baseline_candidates = records[:-recent_window] if len(records) > recent_window else []
        if not baseline_candidates:
            return []
        latest_recent_at = records[-1].recorded_at
        threshold = latest_recent_at - (baseline_window_days * _SECONDS_PER_DAY)
        windowed = [record for record in baseline_candidates if record.recorded_at >= threshold]
        return windowed or baseline_candidates

    def _build_task_summaries(
        self,
        records: list[EvalDatasetRecord],
        *,
        tasks_by_id: dict[str, GoldTask],
        recent_window: int,
        baseline_window_days: int,
        frozen_baseline: RegressionBoardBaseline | None = None,
    ) -> list[RegressionTaskSummary]:
        by_task: dict[str, list[EvalDatasetRecord]] = defaultdict(list)
        for record in records:
            by_task[record.task_id].append(record)
        summaries: list[RegressionTaskSummary] = []
        for task_id, task_records in by_task.items():
            ordered = self._sorted_records(task_records)
            latest = ordered[-1]
            recent_records = ordered[-recent_window:]
            baseline_records = self._select_baseline_records(
                ordered,
                recent_window=recent_window,
                baseline_window_days=baseline_window_days,
            )
            task = tasks_by_id.get(task_id)
            latest_score = latest.weighted_score
            pass_threshold = task.pass_threshold if task is not None else None
            baseline_mean = (
                frozen_baseline.task_mean_scores.get(task_id)
                if frozen_baseline is not None
                else self._average_weighted_score(baseline_records)
            )
            delta_score = self._delta(
                self._average_weighted_score(recent_records),
                baseline_mean,
            )
            status = self._task_status(
                latest_score=latest_score,
                latest_passed=latest.passed,
                pass_threshold=pass_threshold,
                delta_score=delta_score,
                has_baseline=(
                    baseline_mean is not None
                    if frozen_baseline is not None
                    else bool(baseline_records)
                ),
            )
            summaries.append(
                RegressionTaskSummary(
                    task_id=task_id,
                    domain=(None if task is None else task.domain)
                    or _metadata_text(latest, "taskDomain", "domain"),
                    difficulty=(None if task is None else task.difficulty)
                    or _metadata_text(latest, "taskDifficulty", "difficulty"),
                    latest_run_id=latest.run_id,
                    latest_mode=latest.mode,
                    latest_recorded_at=latest.recorded_at,
                    latest_weighted_score=latest_score,
                    latest_passed=latest.passed,
                    pass_threshold=pass_threshold,
                    alert_on_drop_below=None if task is None else task.alert_on_drop_below,
                    recent_record_count=len(recent_records),
                    baseline_record_count=(
                        frozen_baseline.source_point_count
                        if frozen_baseline is not None and baseline_mean is not None
                        else len(baseline_records)
                    ),
                    recent_mean_score=self._average_weighted_score(recent_records),
                    baseline_mean_score=baseline_mean,
                    delta_score=delta_score,
                    status=status,
                )
            )
        summaries.sort(
            key=lambda item: (
                self._task_status_rank(item.status),
                -(abs(item.delta_score) if item.delta_score is not None else 0.0),
                -item.latest_recorded_at,
            )
        )
        return summaries

    @staticmethod
    def _task_status(
        *,
        latest_score: float,
        latest_passed: bool,
        pass_threshold: float | None,
        delta_score: float | None,
        has_baseline: bool,
    ) -> Literal["healthy", "regressed", "failing", "insufficient_baseline"]:
        if (pass_threshold is not None and latest_score < pass_threshold) or (
            pass_threshold is None and not latest_passed
        ):
            return "failing"
        if not has_baseline:
            return "insufficient_baseline"
        if delta_score is not None and delta_score <= -_DIMENSION_REGRESSION_THRESHOLD:
            return "regressed"
        return "healthy"

    @staticmethod
    def _task_status_rank(status: str) -> int:
        ranks = {
            "failing": 0,
            "regressed": 1,
            "insufficient_baseline": 2,
            "healthy": 3,
        }
        return ranks.get(status, 9)

    def _build_dimension_summaries(
        self,
        recent_records: list[EvalDatasetRecord],
        baseline_records: list[EvalDatasetRecord],
        frozen_baseline: RegressionBoardBaseline | None = None,
    ) -> list[RegressionDimensionSummary]:
        names = {
            name
            for record in recent_records + baseline_records
            for name in record.scores
        }
        if frozen_baseline is not None:
            names |= set(frozen_baseline.dimension_mean_scores)
        summaries: list[RegressionDimensionSummary] = []
        for name in sorted(names):
            recent_values = [
                record.scores[name].value
                for record in recent_records
                if name in record.scores
            ]
            baseline_values = (
                []
                if frozen_baseline is not None
                else [
                    record.scores[name].value
                    for record in baseline_records
                    if name in record.scores
                ]
            )
            recent_mean = self._average_values(recent_values)
            baseline_mean = (
                frozen_baseline.dimension_mean_scores.get(name)
                if frozen_baseline is not None
                else self._average_values(baseline_values)
            )
            summaries.append(
                RegressionDimensionSummary(
                    name=name,
                    label=self._titleize(name),
                    recent_record_count=len(recent_values),
                    baseline_record_count=(
                        frozen_baseline.source_point_count
                        if frozen_baseline is not None and baseline_mean is not None
                        else len(baseline_values)
                    ),
                    recent_mean_score=recent_mean,
                    baseline_mean_score=baseline_mean,
                    delta_score=self._delta(recent_mean, baseline_mean),
                )
            )
        summaries.sort(
            key=lambda item: (
                item.delta_score is None,
                item.delta_score if item.delta_score is not None else 0.0,
                item.name,
            )
        )
        return summaries

    def _build_mode_summaries(
        self,
        records: list[EvalDatasetRecord],
    ) -> list[RegressionModeSummary]:
        grouped: dict[str, list[EvalDatasetRecord]] = defaultdict(list)
        for record in records:
            grouped[record.mode].append(record)
        summaries = [
            RegressionModeSummary(
                mode=mode,
                record_count=len(items),
                avg_weighted_score=self._average_weighted_score(items),
                pass_rate=self._pass_rate(items),
            )
            for mode, items in sorted(grouped.items())
        ]
        summaries.sort(key=lambda item: item.mode)
        return summaries

    def _build_alerts(
        self,
        *,
        overall: RegressionOverallSummary,
        task_summaries: list[RegressionTaskSummary],
        dimension_summaries: list[RegressionDimensionSummary],
        mode_summaries: list[RegressionModeSummary],
    ) -> list[RegressionAlert]:
        alerts: list[RegressionAlert] = []
        if (
            overall.recent.pass_rate is not None
            and overall.baseline.pass_rate is not None
            and overall.recent.pass_rate
            < overall.baseline.pass_rate - _OVERALL_PASS_RATE_DROP_THRESHOLD
        ):
            alerts.append(
                RegressionAlert(
                    kind="pass_rate_drop",
                    severity="high",
                    scope="overall",
                    message=(
                        "Gold-suite pass rate dropped below the rolling baseline by more than 3pp."
                    ),
                    delta=overall.delta_pass_rate,
                    current_value=overall.recent.pass_rate,
                    baseline_value=overall.baseline.pass_rate,
                )
            )

        for dimension_item in dimension_summaries:
            if (
                dimension_item.delta_score is not None
                and dimension_item.delta_score <= -_DIMENSION_REGRESSION_THRESHOLD
                and dimension_item.baseline_mean_score is not None
            ):
                alerts.append(
                    RegressionAlert(
                        kind="dimension_regression",
                        severity="medium",
                        scope="dimension",
                        scope_key=dimension_item.name,
                        dimension=dimension_item.name,
                        message=(
                            f"{dimension_item.label} dropped below the rolling baseline by "
                            "more than 5pp."
                        ),
                        delta=dimension_item.delta_score,
                        current_value=dimension_item.recent_mean_score,
                        baseline_value=dimension_item.baseline_mean_score,
                    )
                )

        for task_item in task_summaries:
            threshold = task_item.pass_threshold
            if (threshold is not None and task_item.latest_weighted_score < threshold) or (
                threshold is None and not task_item.latest_passed
            ):
                alerts.append(
                    RegressionAlert(
                        kind="single_task_hard_fail",
                        severity="high",
                        scope="task",
                        scope_key=task_item.task_id,
                        task_id=task_item.task_id,
                        message=f"{task_item.task_id} fell below its task pass threshold.",
                        delta=None,
                        current_value=task_item.latest_weighted_score,
                        baseline_value=threshold,
                    )
                )

        modes = {item.mode: item for item in mode_summaries}
        online = modes.get("online")
        offline = modes.get("offline")
        if (
            online is not None
            and offline is not None
            and online.avg_weighted_score is not None
            and offline.avg_weighted_score is not None
            and offline.avg_weighted_score - online.avg_weighted_score
            >= _ONLINE_OFFLINE_DRIFT_THRESHOLD
        ):
            delta = online.avg_weighted_score - offline.avg_weighted_score
            alerts.append(
                RegressionAlert(
                    kind="online_mode_drift",
                    severity="medium",
                    scope="mode",
                    scope_key="online_vs_offline",
                    message="Online score drift exceeded 10pp versus offline runs.",
                    delta=delta,
                    current_value=online.avg_weighted_score,
                    baseline_value=offline.avg_weighted_score,
                )
            )

        alerts.sort(
            key=lambda item: (
                self._severity_rank(item.severity),
                -(abs(item.delta) if item.delta is not None else 0.0),
                item.kind,
                item.scope_key or "",
            )
        )
        return alerts

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(severity, 9)

    def _build_window_stats(self, records: list[EvalDatasetRecord]) -> RegressionWindowStats:
        return RegressionWindowStats(
            record_count=len(records),
            avg_weighted_score=self._average_weighted_score(records),
            pass_rate=self._pass_rate(records),
        )

    @staticmethod
    def _point_to_window_stats(point: RegressionBoardPoint) -> RegressionWindowStats:
        return RegressionWindowStats(
            record_count=point.run_count,
            avg_weighted_score=point.weighted_score_mean,
            pass_rate=point.pass_rate,
        )

    def _build_baseline_window_stats(
        self,
        baseline_records: list[EvalDatasetRecord],
        *,
        frozen_baseline: RegressionBoardBaseline | None,
    ) -> RegressionWindowStats:
        if frozen_baseline is not None:
            return RegressionWindowStats(
                record_count=frozen_baseline.source_point_count,
                avg_weighted_score=frozen_baseline.weighted_score_mean,
                pass_rate=frozen_baseline.pass_rate,
            )
        return self._build_window_stats(baseline_records)

    def _baseline_average_weighted_score(
        self,
        baseline_records: list[EvalDatasetRecord],
        *,
        frozen_baseline: RegressionBoardBaseline | None,
    ) -> float | None:
        if frozen_baseline is not None:
            return frozen_baseline.weighted_score_mean
        return self._average_weighted_score(baseline_records)

    def _baseline_pass_rate(
        self,
        baseline_records: list[EvalDatasetRecord],
        *,
        frozen_baseline: RegressionBoardBaseline | None,
    ) -> float | None:
        if frozen_baseline is not None:
            return frozen_baseline.pass_rate
        return self._pass_rate(baseline_records)

    def _select_frozen_baseline(
        self,
        *,
        axis_kind: Literal["commit", "date"],
        mode: str | None,
        domain: str | None,
        task_id: str | None,
    ) -> RegressionBoardBaseline | None:
        if self._baseline_store is None:
            return None
        baseline = self._baseline_store.load_latest()
        if baseline is None:
            return None
        if baseline.axis_kind != axis_kind:
            return None
        if baseline.mode != mode:
            return None
        if baseline.domain != domain:
            return None
        if baseline.task_id != task_id:
            return None
        return baseline

    @staticmethod
    def _average_weighted_score(records: list[EvalDatasetRecord]) -> float | None:
        if not records:
            return None
        return float(fmean(record.weighted_score for record in records))

    @staticmethod
    def _pass_rate(records: list[EvalDatasetRecord]) -> float | None:
        if not records:
            return None
        return float(fmean(1.0 if record.passed else 0.0 for record in records))

    @staticmethod
    def _average_values(values: list[float]) -> float | None:
        if not values:
            return None
        return float(fmean(values))

    @staticmethod
    def _delta(current: float | None, baseline: float | None) -> float | None:
        if current is None or baseline is None:
            return None
        return current - baseline

    @staticmethod
    def _titleize(value: str) -> str:
        return " ".join(part.capitalize() for part in value.split("_"))


class FreezeRegressionBaseline:
    """Persist one manually frozen regression baseline."""

    def __init__(
        self,
        *,
        eval_store: EvalDatasetStore,
        baseline_store: RegressionBaselineStore,
    ) -> None:
        self._eval_store = eval_store
        self._baseline_store = baseline_store

    def execute(
        self,
        *,
        commit_sha: str,
        axis: str = "commit",
        task_catalog: tuple[GoldTask, ...] | list[GoldTask] = (),
        mode: str | None = None,
        domain: str | None = None,
        task_id: str | None = None,
        baseline_window_days: int = 14,
        window_days: int | None = None,
    ) -> RegressionBoardBaseline:
        if not commit_sha.strip():
            raise ValueError("commit_sha must not be empty.")
        resolved_axis = _normalize_axis(axis)
        resolved_window_days = window_days if window_days is not None else baseline_window_days

        builder = BuildRegressionBoard(self._eval_store)
        tasks_by_id = {task.id: task for task in task_catalog}
        all_records = builder._sorted_records(self._eval_store.load_all())
        filtered_records = [
            record
            for record in all_records
            if builder._record_matches(
                record,
                tasks_by_id=tasks_by_id,
                mode=mode,
                domain=domain,
                task_id=task_id,
            )
        ]
        if not filtered_records:
            raise ValueError("No eval dataset records matched the requested baseline scope.")

        latest_recorded_at = filtered_records[-1].recorded_at
        threshold = latest_recorded_at - (resolved_window_days * _SECONDS_PER_DAY)
        baseline_records = [
            record for record in filtered_records if record.recorded_at >= threshold
        ]
        baseline_records = baseline_records or filtered_records

        baseline = RegressionBoardBaseline(
            baseline_id=f"baseline-{uuid.uuid4().hex[:12]}",
            commit_sha=commit_sha.strip(),
            axis_kind=resolved_axis,
            mode=mode,
            domain=domain,
            task_id=task_id,
            pass_rate=BuildRegressionBoard._pass_rate(baseline_records) or 0.0,
            weighted_score_mean=_median_weighted_score(baseline_records),
            baseline_window_days=resolved_window_days,
            source_point_count=len(baseline_records),
            dimension_mean_scores=_median_dimension_scores(baseline_records),
            task_mean_scores=_median_task_scores(baseline_records),
            created_at=time.time(),
        )
        self._baseline_store.save(baseline)
        return baseline


def _median_weighted_score(records: list[EvalDatasetRecord]) -> float:
    if not records:
        return 0.0
    return float(median(record.weighted_score for record in records))


def _median_dimension_scores(records: list[EvalDatasetRecord]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        for name, score in record.scores.items():
            buckets[name].append(score.value)
    return {
        name: float(median(values))
        for name, values in sorted(buckets.items())
        if values
    }


def _median_task_scores(records: list[EvalDatasetRecord]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        buckets[record.task_id].append(record.weighted_score)
    return {
        task_id: float(median(values))
        for task_id, values in sorted(buckets.items())
        if values
    }


def _metadata_text(record: EvalDatasetRecord, *keys: str) -> str | None:
    for key in keys:
        value = record.run_metadata.get(key)
        if value is not None:
            return str(value)
    return None


def _normalize_axis(axis: str) -> Literal["commit", "date"]:
    return "date" if axis == "date" else "commit"


def _axis_key(record: EvalDatasetRecord, *, axis: str) -> str:
    if axis == "date":
        return time.strftime("%Y-%m-%d", time.gmtime(record.recorded_at))
    raw_commit = (
        record.run_metadata.get("commitSha")
        or record.run_metadata.get("commit_sha")
        or record.run_metadata.get("gitSha")
        or record.run_metadata.get("git_sha")
    )
    if raw_commit is not None and str(raw_commit).strip():
        return str(raw_commit)
    return time.strftime("%Y-%m-%d", time.gmtime(record.recorded_at))


def _mean_dimension_scores(records: list[EvalDatasetRecord]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        for name, score in record.scores.items():
            buckets[name].append(score.value)
    return {
        name: float(fmean(values))
        for name, values in sorted(buckets.items())
        if values
    }


def _mean_mode_scores(records: list[EvalDatasetRecord]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        buckets[record.mode].append(record.weighted_score)
    return {
        mode: float(fmean(values))
        for mode, values in sorted(buckets.items())
        if values
    }
