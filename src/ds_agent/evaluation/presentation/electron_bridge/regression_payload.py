"""Serialize regression-board snapshots into Electron-friendly payloads."""

from __future__ import annotations

from typing import Any

from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionBoardSnapshot,
    RegressionWindowStats,
)


def build_regression_board_payload(snapshot: RegressionBoardSnapshot) -> dict[str, Any]:
    """Return a compact payload for runtime/Electron regression dashboards."""

    return {
        "generatedAt": snapshot.generated_at,
        "totalRecords": snapshot.total_records,
        "recentWindow": snapshot.recent_window,
        "baselineWindowDays": snapshot.baseline_window_days,
        "axisKind": snapshot.axis_kind,
        "baselineSource": snapshot.baseline_source,
        "pointCount": snapshot.point_count,
        "filters": {
            "mode": snapshot.mode_filter,
            "domain": snapshot.domain_filter,
        },
        "availableDomains": list(snapshot.available_domains),
        "overall": {
            "recent": _window_stats_payload(snapshot.overall.recent),
            "baseline": _window_stats_payload(snapshot.overall.baseline),
            "deltaScore": snapshot.overall.delta_score,
            "deltaPassRate": snapshot.overall.delta_pass_rate,
        },
        "frozenBaseline": (
            None
            if snapshot.frozen_baseline is None
            else {
                "baselineId": snapshot.frozen_baseline.baseline_id,
                "commitSha": snapshot.frozen_baseline.commit_sha,
                "mode": snapshot.frozen_baseline.mode,
                "domain": snapshot.frozen_baseline.domain,
                "taskId": snapshot.frozen_baseline.task_id,
                "passRate": snapshot.frozen_baseline.pass_rate,
                "weightedScoreMean": snapshot.frozen_baseline.weighted_score_mean,
                "baselineWindowDays": snapshot.frozen_baseline.baseline_window_days,
                "sourcePointCount": snapshot.frozen_baseline.source_point_count,
                "createdAt": snapshot.frozen_baseline.created_at,
            }
        ),
        "modeSummaries": [
            {
                "mode": item.mode,
                "recordCount": item.record_count,
                "avgWeightedScore": item.avg_weighted_score,
                "passRate": item.pass_rate,
            }
            for item in snapshot.mode_summaries
        ],
        "points": [
            {
                "axisKey": item.axis_key,
                "axisLabel": item.axis_label,
                "runCount": item.run_count,
                "passRate": item.pass_rate,
                "weightedScoreMean": item.weighted_score_mean,
                "perDimensionMeans": dict(item.per_dimension_means),
                "perModeWeightedScores": dict(item.per_mode_weighted_scores),
            }
            for item in snapshot.points
        ],
        "taskSummaries": [
            {
                "taskId": item.task_id,
                "domain": item.domain,
                "difficulty": item.difficulty,
                "latestRunId": item.latest_run_id,
                "latestMode": item.latest_mode,
                "latestRecordedAt": item.latest_recorded_at,
                "latestWeightedScore": item.latest_weighted_score,
                "latestPassed": item.latest_passed,
                "passThreshold": item.pass_threshold,
                "alertOnDropBelow": item.alert_on_drop_below,
                "recentRecordCount": item.recent_record_count,
                "baselineRecordCount": item.baseline_record_count,
                "recentMeanScore": item.recent_mean_score,
                "baselineMeanScore": item.baseline_mean_score,
                "deltaScore": item.delta_score,
                "status": item.status,
            }
            for item in snapshot.task_summaries
        ],
        "dimensionSummaries": [
            {
                "name": item.name,
                "label": item.label,
                "recentRecordCount": item.recent_record_count,
                "baselineRecordCount": item.baseline_record_count,
                "recentMeanScore": item.recent_mean_score,
                "baselineMeanScore": item.baseline_mean_score,
                "deltaScore": item.delta_score,
            }
            for item in snapshot.dimension_summaries
        ],
        "alerts": [
            {
                "kind": item.kind,
                "severity": item.severity,
                "scope": item.scope,
                "scopeKey": item.scope_key,
                "dimension": item.dimension,
                "taskId": item.task_id,
                "message": item.message,
                "delta": item.delta,
                "currentValue": item.current_value,
                "baselineValue": item.baseline_value,
            }
            for item in snapshot.alerts
        ],
    }


def _window_stats_payload(stats: RegressionWindowStats) -> dict[str, Any]:
    return {
        "recordCount": stats.record_count,
        "avgWeightedScore": stats.avg_weighted_score,
        "passRate": stats.pass_rate,
    }
