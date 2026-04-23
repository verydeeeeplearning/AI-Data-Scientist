from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ds_agent.runtime.web_push_metrics import (
    JsonWebPushMetricsStore,
    WebPushMetricsSummary,
)


def _store(tmp_path: Path) -> JsonWebPushMetricsStore:
    return JsonWebPushMetricsStore(workspace_dir=str(tmp_path / 'workspace'))


def test_empty_store_returns_zero_summary(tmp_path: Path) -> None:
    store = _store(tmp_path)

    summary = store.summary('op-1', datetime.now(UTC) - timedelta(hours=1))

    assert summary == WebPushMetricsSummary(
        delivered_count=0,
        failed_count=0,
        pruned_count=0,
        unique_endpoints=0,
    )


def test_records_delivery_failure_and_prune(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_delivery('op-1', 'https://push.example/a', True)
    store.record_delivery('op-1', 'https://push.example/b', False)
    store.record_prune('op-1', 'https://push.example/b', 'http_410')

    summary = store.summary('op-1', datetime.now(UTC) - timedelta(hours=1))

    assert summary.delivered_count == 1
    assert summary.failed_count == 1
    assert summary.pruned_count == 1
    assert summary.unique_endpoints == 2


def test_summary_window_filters_out_older_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_delivery('op-1', 'https://push.example/new', True)
    record_file = store._record_file('op-1')
    older_payload = {
        'ts': (datetime.now(UTC) - timedelta(hours=5)).isoformat(),
        'operator_id': 'op-1',
        'endpoint': 'https://push.example/old',
        'kind': 'delivery',
        'ok': True,
        'reason': None,
    }
    with record_file.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(older_payload))
        handle.write('\n')

    summary = store.summary('op-1', datetime.now(UTC) - timedelta(hours=1))

    assert summary.delivered_count == 1
    assert summary.unique_endpoints == 1


def test_restart_survival_reads_written_events(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_delivery('op-1', 'https://push.example/a', True)
    store.record_prune('op-1', 'https://push.example/a', 'http_404')

    new_store = _store(tmp_path)
    summary = new_store.summary('op-1', datetime.now(UTC) - timedelta(hours=1))

    assert summary.delivered_count == 1
    assert summary.pruned_count == 1


def test_per_operator_summaries_are_isolated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_delivery('op-1', 'https://push.example/a', True)
    store.record_delivery('op-2', 'https://push.example/b', True)

    op1 = store.summary('op-1', datetime.now(UTC) - timedelta(hours=1))
    op2 = store.summary('op-2', datetime.now(UTC) - timedelta(hours=1))

    assert op1.delivered_count == 1
    assert op2.delivered_count == 1
    assert op1.unique_endpoints == 1
    assert op2.unique_endpoints == 1
