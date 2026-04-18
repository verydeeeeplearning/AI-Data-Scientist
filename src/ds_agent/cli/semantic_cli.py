"""Semantic-memory CLI helpers."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from ds_agent.cli.semantic_proposal_cli import run_semantic_proposal_command
from ds_agent.config.loader import get_default_config_path, load_config
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.application.dtos import (
    LoadSemanticPackResultDTO,
    ResolveMetricResultDTO,
    RestoreSemanticSnapshotResultDTO,
    SemanticSnapshotSummaryDTO,
    SyncSemanticSourceResultDTO,
    TableTrustDecisionDTO,
    VerifiedQueryResultDTO,
)
from ds_agent.memory.semantic.application.ports import (
    ExternalSemanticSource,
    SemanticSyncPolicy,
)
from ds_agent.memory.semantic.domain.trust import TrustGrade
from ds_agent.memory.semantic.infrastructure.adapters import (
    BigQuerySchemaAdapter,
    DbtMetricFlowAdapter,
    LookerAdapter,
    PostgresSchemaAdapter,
    SnowflakeSchemaAdapter,
    UnityCatalogAdapter,
)
from ds_agent.memory.semantic.infrastructure.pack_paths import resolve_semantic_pack_dir

if TYPE_CHECKING:
    from ds_agent.config.schema import DSAgentConfig


def run_semantic_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
    config: DSAgentConfig | None = None,
) -> int:
    """Run `ds-agent semantic ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) or ["help"])
    container = build_semantic_memory_container(workspace_dir=workspace_dir)

    if args.command == "help":
        parser.print_help()
        return 0

    if args.command == "proposal":
        return run_semantic_proposal_command(
            args.proposal_argv or [],
            console=console,
            workspace_dir=workspace_dir,
        )

    if args.command == "snapshot":
        if args.snapshot_command == "list":
            snapshots = container.list_semantic_snapshots.execute(limit=args.limit)
            console.print(_render_snapshot_list(snapshots))
            return 0

        restored = container.restore_semantic_snapshot.execute(args.snapshot_id)
        console.print(_render_restore_snapshot_result(restored))
        return 0

    if args.command == "sync":
        sync_source, policy = _build_sync_source(args, config=config)
        since = _parse_since(args.since)
        sync_result = container.sync_semantic_source.execute(
            sync_source,
            policy=policy,
            since=since,
            dry_run=not args.apply,
        )
        console.print(_render_sync_result(sync_result, source_kind=args.sync_source))
        return 0

    if args.command == "lookup":
        lookup_result = container.resolve_metric.execute(
            args.query,
            grain=args.grain,
        )
        console.print(_render_lookup_result(lookup_result))
        return 0

    if args.command == "trust":
        trust_result = container.check_table_trust.execute(
            list(args.fqtns),
            allow_untrusted=args.allow_untrusted,
        )
        console.print(_render_trust_result(trust_result))
        return 0

    if args.command == "verified-query":
        bindings = _parse_bindings(args.bindings or [])
        verified_query_result = container.find_verified_query.execute(
            args.metric_id,
            dialect=args.dialect,
            bindings=bindings or None,
        )
        console.print(_render_verified_query_result(verified_query_result))
        return 0

    resolved_pack_dir, source = resolve_semantic_pack_dir(
        pack_dir=args.pack_dir,
        skill_name=args.skill_name,
        workspace_dir=workspace_dir,
    )
    load_pack_result = container.load_semantic_pack.execute(
        str(resolved_pack_dir),
        dry_run=not args.apply,
        allow_definition_updates=args.allow_definition_updates,
    )
    console.print(_render_load_pack_result(load_pack_result, source=source))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent semantic", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("help", add_help=False)

    proposal = subparsers.add_parser("proposal", add_help=False)
    proposal.add_argument("proposal_argv", nargs=argparse.REMAINDER)

    snapshot = subparsers.add_parser("snapshot", add_help=False)
    snapshot_subparsers = snapshot.add_subparsers(dest="snapshot_command", required=True)

    snapshot_list = snapshot_subparsers.add_parser("list", add_help=False)
    snapshot_list.add_argument("--limit", type=int, default=20)

    snapshot_restore = snapshot_subparsers.add_parser("restore", add_help=False)
    snapshot_restore.add_argument("snapshot_id")

    lookup = subparsers.add_parser("lookup", add_help=False)
    lookup.add_argument("query")
    lookup.add_argument(
        "--grain",
        choices=["hourly", "daily", "weekly", "monthly", "quarterly", "yearly"],
        default=None,
    )

    trust = subparsers.add_parser("trust", add_help=False)
    trust.add_argument("fqtns", nargs="+")
    trust.add_argument("--allow-untrusted", action="store_true")

    verified_query = subparsers.add_parser("verified-query", add_help=False)
    verified_query.add_argument("metric_id")
    verified_query.add_argument(
        "--dialect",
        choices=["postgres", "bigquery", "snowflake", "duckdb", "databricks_sql"],
        default="postgres",
    )
    verified_query.add_argument("--bind", dest="bindings", action="append", default=[])

    load_pack = subparsers.add_parser("load-pack", add_help=False)
    load_pack.add_argument("--pack-dir")
    load_pack.add_argument("--skill-name")
    load_pack.add_argument("--apply", action="store_true")
    load_pack.add_argument("--allow-definition-updates", action="store_true")

    sync = subparsers.add_parser("sync", add_help=False)
    sync_subparsers = sync.add_subparsers(dest="sync_source", required=True)

    postgres_sync = sync_subparsers.add_parser("postgres", add_help=False)
    _configure_connector_sync_parser(postgres_sync)

    bigquery_sync = sync_subparsers.add_parser("bigquery", add_help=False)
    _configure_connector_sync_parser(bigquery_sync)

    snowflake_sync = sync_subparsers.add_parser("snowflake", add_help=False)
    _configure_connector_sync_parser(snowflake_sync)

    dbt_sync = sync_subparsers.add_parser("dbt", add_help=False)
    dbt_sync.add_argument("--endpoint")
    dbt_sync.add_argument("--token")
    dbt_sync.add_argument("--token-env")
    dbt_sync.add_argument("--source-name", default="dbt_metricflow")
    dbt_sync.add_argument("--owner", default="dbt_metricflow")
    dbt_sync.add_argument("--apply", action="store_true")
    dbt_sync.add_argument("--overwrite", action="store_true")
    dbt_sync.add_argument("--namespace", default="dbt:")
    dbt_sync.add_argument("--since")
    dbt_sync.add_argument("--allow-grade", action="append", default=[])

    unity_sync = sync_subparsers.add_parser("unity-catalog", add_help=False)
    _configure_remote_sync_parser(
        unity_sync,
        default_source_name="unity_catalog",
        default_owner="unity_catalog",
        default_namespace="unity:",
    )

    looker_sync = sync_subparsers.add_parser("looker", add_help=False)
    _configure_remote_sync_parser(
        looker_sync,
        default_source_name="looker",
        default_owner="looker",
        default_namespace="looker:",
    )

    return parser


def _parse_bindings(items: Sequence[str]) -> dict[str, object]:
    bindings: dict[str, object] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("bindings must use key=value format")
        key, value = item.split("=", 1)
        bindings[key] = value
    return bindings


def _render_lookup_result(lookup: ResolveMetricResultDTO) -> Table:
    table = Table(title="Semantic Lookup")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("query", lookup.query)
    table.add_row("kind", lookup.kind)
    if lookup.best_match is None:
        table.add_row("match", "no approved metric match")
        return table
    metric = lookup.best_match.metric
    table.add_row("metric_id", metric.metric_id)
    table.add_row("display_name", metric.display_name)
    table.add_row("owner", metric.owner)
    table.add_row("definition", metric.definition)
    table.add_row("synonyms", ", ".join(metric.synonyms) or "-")
    table.add_row("related_metrics", ", ".join(metric.related_metrics) or "-")
    table.add_row("verified_queries", ", ".join(metric.verified_query_ids) or "-")
    return table


def _render_trust_result(decision: TableTrustDecisionDTO) -> Table:
    table = Table(title="Semantic Trust")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("action", decision.action)
    table.add_row("missing_tables", ", ".join(decision.missing_tables) or "-")
    table.add_row("warnings", "; ".join(decision.warnings) or "-")
    for item in decision.tables:
        table.add_row(
            item.fqtn,
            f"{item.grade.value} | owner={item.owner} | refresh={item.refresh.cadence}",
        )
    return table


def _render_verified_query_result(resolved: VerifiedQueryResultDTO) -> Table:
    table = Table(title="Verified Query")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    if resolved.query is None:
        table.add_row("status", "not found")
        return table
    table.add_row("vq_id", resolved.query.vq_id)
    table.add_row("dialect", resolved.query.dialect)
    table.add_row("metric_id", resolved.query.metric_id or "-")
    table.add_row("verified_by", resolved.query.verified_by)
    table.add_row("last_verified", str(resolved.query.last_verified))
    table.add_row("referenced_tables", ", ".join(resolved.query.referenced_tables) or "-")
    table.add_row("sql", resolved.rendered_sql or resolved.query.sql_template)
    return table


def _render_load_pack_result(loaded: LoadSemanticPackResultDTO, *, source: str) -> Table:
    table = Table(title="Semantic Pack Load")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("source", source)
    table.add_row("pack_id", loaded.pack_id or "-")
    table.add_row("display_name", loaded.display_name or "-")
    table.add_row("dry_run", str(loaded.dry_run))
    table.add_row("snapshot_id", loaded.snapshot_id or "-")
    table.add_row("metric_diffs", str(len(loaded.metric_diffs)))
    table.add_row("glossary_diffs", str(len(loaded.glossary_diffs)))
    table.add_row("trust_diffs", str(len(loaded.trust_diffs)))
    table.add_row("verified_query_diffs", str(len(loaded.verified_query_diffs)))
    table.add_row(
        "applied",
        ", ".join(
            [
                *loaded.applied_metric_ids,
                *loaded.applied_glossary_term_ids,
                *loaded.applied_table_ids,
                *loaded.applied_verified_query_ids,
            ]
        )
        or "-",
    )
    return table


def _render_sync_result(
    synced: SyncSemanticSourceResultDTO,
    *,
    source_kind: str,
) -> Table:
    table = Table(title="Semantic Source Sync")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("source_kind", source_kind)
    table.add_row("source_name", synced.source_name)
    table.add_row("dry_run", str(synced.dry_run))
    table.add_row("overwrite", str(synced.overwrite))
    table.add_row("namespace", synced.id_namespace or "-")
    table.add_row("snapshot_id", synced.snapshot_id or "-")
    table.add_row("since", synced.since.isoformat() if synced.since is not None else "-")
    table.add_row("allowed_grades", ", ".join(synced.allowed_grades) or "-")
    table.add_row("metric_diffs", str(len(synced.metric_diffs)))
    table.add_row("glossary_diffs", str(len(synced.glossary_diffs)))
    table.add_row("trust_diffs", str(len(synced.trust_diffs)))
    table.add_row("verified_query_diffs", str(len(synced.verified_query_diffs)))
    table.add_row(
        "applied",
        ", ".join(
            [
                *synced.applied_metric_ids,
                *synced.applied_glossary_term_ids,
                *synced.applied_table_ids,
                *synced.applied_verified_query_ids,
            ]
        )
        or "-",
    )
    return table


def _render_snapshot_list(snapshots: list[SemanticSnapshotSummaryDTO]) -> Table:
    table = Table(title="Semantic Snapshots")
    table.add_column("snapshot_id", style="bold")
    table.add_column("source")
    table.add_column("created_at")
    table.add_column("total_rows", justify="right")
    table.add_column("note")
    if not snapshots:
        table.add_row("-", "-", "-", "0", "no snapshots")
        return table
    for item in snapshots:
        table.add_row(
            item.snapshot_id,
            item.source_name,
            item.created_at.isoformat(),
            str(item.total_rows),
            item.note or "-",
        )
    return table


def _render_restore_snapshot_result(restored: RestoreSemanticSnapshotResultDTO) -> Table:
    table = Table(title="Semantic Snapshot Restore")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("snapshot_id", restored.snapshot.snapshot_id)
    table.add_row("source_name", restored.snapshot.source_name)
    table.add_row("created_at", restored.snapshot.created_at.isoformat())
    table.add_row("restored_rows", str(restored.restored_rows))
    table.add_row("restored_tables", ", ".join(restored.restored_tables) or "-")
    table.add_row("note", restored.snapshot.note or "-")
    return table


def _build_sync_source(
    args: argparse.Namespace,
    *,
    config: DSAgentConfig | None,
) -> tuple[ExternalSemanticSource, SemanticSyncPolicy]:
    if args.sync_source in {"postgres", "bigquery", "snowflake"}:
        resolved_config = config or load_config(get_default_config_path())
        connector_settings = resolved_config.connectors.get(args.connector)
        if connector_settings is None:
            raise ValueError(f"Unknown connector: {args.connector}")
        connector = connector_settings.to_domain(args.connector)
        if connector.type.value != args.sync_source:
            raise ValueError(
                f"semantic sync {args.sync_source} requires a {args.sync_source} connector"
            )

        from ds_agent.infrastructure.persistence.connector_factory import create_connector_adapter

        warehouse_adapter = create_connector_adapter(connector)
        source: ExternalSemanticSource
        if args.sync_source == "postgres":
            source = PostgresSchemaAdapter(
                connector,
                warehouse_adapter,
                owner=args.owner,
            )
        elif args.sync_source == "bigquery":
            source = BigQuerySchemaAdapter(
                connector,
                warehouse_adapter,
                owner=args.owner,
            )
        else:
            source = SnowflakeSchemaAdapter(
                connector,
                warehouse_adapter,
                owner=args.owner,
            )
        policy = SemanticSyncPolicy(
            source_name=args.connector,
            overwrite=bool(args.overwrite),
            id_namespace=args.namespace,
            allowed_grades=_resolve_allowed_grades(args.allow_grade),
        )
        return source, policy

    normalized_source = args.sync_source.replace("-", "_")
    if normalized_source == "dbt":
        endpoint_env = "DS_AGENT_DBT_METRICFLOW_ENDPOINT"
        token_env = "DS_AGENT_DBT_METRICFLOW_TOKEN"
        source = DbtMetricFlowAdapter(
            _resolve_remote_endpoint(args.endpoint, env_var=endpoint_env, label="dbt sync"),
            auth_token=_resolve_remote_token(args, default_env_var=token_env),
            source_name=args.source_name,
            owner=args.owner or "dbt_metricflow",
        )
        policy = SemanticSyncPolicy(
            source_name=args.source_name,
            overwrite=bool(args.overwrite),
            id_namespace=args.namespace,
            allowed_grades=_resolve_allowed_grades(args.allow_grade),
        )
        return source, policy

    if normalized_source == "unity_catalog":
        source = UnityCatalogAdapter(
            _resolve_remote_endpoint(
                args.endpoint,
                env_var="DS_AGENT_UNITY_CATALOG_ENDPOINT",
                label="unity-catalog sync",
            ),
            auth_token=_resolve_remote_token(
                args,
                default_env_var="DS_AGENT_UNITY_CATALOG_TOKEN",
            ),
            source_name=args.source_name,
            owner=args.owner or "unity_catalog",
        )
        policy = SemanticSyncPolicy(
            source_name=args.source_name,
            overwrite=bool(args.overwrite),
            id_namespace=args.namespace,
            allowed_grades=_resolve_allowed_grades(args.allow_grade),
        )
        return source, policy

    source = LookerAdapter(
        _resolve_remote_endpoint(
            args.endpoint,
            env_var="DS_AGENT_LOOKER_ENDPOINT",
            label="looker sync",
        ),
        auth_token=_resolve_remote_token(
            args,
            default_env_var="DS_AGENT_LOOKER_TOKEN",
        ),
        source_name=args.source_name,
        owner=args.owner or "looker",
    )
    policy = SemanticSyncPolicy(
        source_name=args.source_name,
        overwrite=bool(args.overwrite),
        id_namespace=args.namespace,
        allowed_grades=_resolve_allowed_grades(args.allow_grade),
    )
    return source, policy


def _resolve_allowed_grades(values: Sequence[str]) -> list[TrustGrade]:
    if not values:
        return [TrustGrade.GOLD, TrustGrade.SILVER]
    return [TrustGrade(value) for value in values]


def _parse_since(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("since must be an ISO-8601 datetime") from exc


def _configure_connector_sync_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--connector", required=True)
    parser.add_argument("--owner")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--namespace")
    parser.add_argument("--since")
    parser.add_argument("--allow-grade", action="append", default=[])


def _configure_remote_sync_parser(
    parser: argparse.ArgumentParser,
    *,
    default_source_name: str,
    default_owner: str,
    default_namespace: str,
) -> None:
    parser.add_argument("--endpoint")
    parser.add_argument("--token")
    parser.add_argument("--token-env")
    parser.add_argument("--source-name", default=default_source_name)
    parser.add_argument("--owner", default=default_owner)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--namespace", default=default_namespace)
    parser.add_argument("--since")
    parser.add_argument("--allow-grade", action="append", default=[])


def _resolve_remote_endpoint(
    explicit_value: str | None,
    *,
    env_var: str,
    label: str,
) -> str:
    endpoint = str(explicit_value or os.environ.get(env_var) or "").strip()
    if endpoint:
        return endpoint
    raise ValueError(f"{label} requires --endpoint or {env_var}")


def _resolve_remote_token(
    args: argparse.Namespace,
    *,
    default_env_var: str,
) -> str | None:
    token = str(args.token or "").strip()
    if not token and args.token_env:
        token = os.environ.get(str(args.token_env), "")
    if not token:
        token = os.environ.get(default_env_var, "")
    return token or None
