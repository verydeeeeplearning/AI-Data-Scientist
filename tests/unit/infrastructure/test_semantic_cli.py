from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ds_agent.cli.semantic_cli import run_semantic_command
from ds_agent.config.schema import AgentConfig, DSAgentConfig, WarehouseConnectorSettings
from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorType
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.proposal import SemanticProposalType
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.semantic_proposal_router import create_semantic_proposal_approval


def _seed_semantic_workspace(workspace_dir: str) -> None:
    container = build_semantic_memory_container(workspace_dir=workspace_dir)
    container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "monthly_churn_rate",
                "display_name": "Monthly Churn Rate",
                "owner": "growth_team",
                "definition": "Monthly customer churn rate",
                "synonyms": ["customer churn"],
                "grain": "monthly",
                "unit": "ratio",
                "direction": "lower_is_better",
                "calculation": {
                    "numerator": {
                        "source": "prod.growth.subscription",
                        "filter": "event_type = 'cancel'",
                        "aggregation": "COUNT(*)",
                    },
                    "denominator": {
                        "source": "prod.growth.subscription",
                        "filter": "status = 'active'",
                        "aggregation": "COUNT(*)",
                    },
                },
                "verified_query_ids": ["vq-monthly-churn-postgres"],
            }
        )
    )
    container.trust.save(
        TableTrust.model_validate(
            {
                "fqtn": "prod.growth.subscription",
                "grade": "gold",
                "owner": "growth_team",
                "description": "Subscription fact table",
                "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                "grade_rationale": "Certified by analytics engineering",
                "last_audited": "2026-04-15",
            }
        )
    )
    container.verified_queries.save(
        VerifiedQuery.model_validate(
            {
                "vq_id": "vq-monthly-churn-postgres",
                "metric_id": "monthly_churn_rate",
                "dialect": "postgres",
                "description": "Verified monthly churn query",
                "sql_template": "SELECT 0.05 AS monthly_churn_rate",
                "referenced_tables": ["prod.growth.subscription"],
                "verified_by": "reviewer@corp.example",
                "last_verified": "2026-04-15",
                "verification_evidence": "Dashboard parity",
            }
        )
    )


def _seed_semantic_proposal(
    workspace_dir: str,
    *,
    proposal_type: SemanticProposalType = SemanticProposalType.GLOSSARY_TERM,
    summary: str = "Glossary candidate for retained customers",
    target_id: str = "term.retained_customers",
    risk: str = "medium",
    session_id: str = "session-1",
    payload: dict[str, object] | None = None,
) -> tuple[str, str]:
    container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    resolved_payload = payload or _default_proposal_payload(
        proposal_type=proposal_type,
        target_id=target_id,
    )
    submission = container.submit_semantic_proposal.execute(
        proposal_type=proposal_type,
        summary=summary,
        payload=resolved_payload,
        target_id=target_id,
        evidence_refs=["verdict:RV-42"],
        confidence=0.88,
        risk=risk,
        source_run_id="TC-1:session-1",
        source_session_id=session_id,
        source_tool_name="run_verifier",
    )
    approval = create_semantic_proposal_approval(
        approval_store=JsonApprovalStore(workspace_dir),
        proposal=submission.proposal,
        session_id=session_id,
        run_id="TC-1:session-1",
        surface="cli-test",
    )
    return submission.proposal.proposal_id, approval.approval_id


def _default_proposal_payload(
    *,
    proposal_type: SemanticProposalType,
    target_id: str,
) -> dict[str, object]:
    if proposal_type is SemanticProposalType.GLOSSARY_TERM:
        canonical_form = target_id.split(".")[-1].replace("_", " ")
        return {
            "term_id": target_id,
            "canonical_form": canonical_form,
            "definition": f"Definition for {canonical_form}.",
            "linked_metric_ids": [],
            "category": "other",
            "owner": "growth_team",
        }
    if proposal_type is SemanticProposalType.NEGATIVE_KNOWLEDGE:
        return {
            "nk_id": target_id,
            "topic": "promo churn exclusions",
            "wrong_approach": "Include promo-only cancellations in churn.",
            "why_wrong": "Promo cohorts distort the denominator.",
            "correct_approach": "Exclude promo-only cancellations from churn.",
            "recorded_at": datetime(2026, 4, 16, 9, 0, tzinfo=UTC).isoformat(),
            "recorded_by": "retrospective",
            "references": ["verdict:RV-42"],
        }
    raise AssertionError(f"Unsupported proposal type for test fixture: {proposal_type.value}")


def _write_pack(pack_dir: Path) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "\n".join(
            [
                "pack_id: acme_pack",
                'display_name: "ACME Pack"',
                "owner: data_platform_team",
                "version: 1.0.0",
                "requires_semantic_layer_schema_version: 6",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        "\n".join(
            [
                "metric_id: monthly_churn_rate",
                "display_name: Monthly Churn Rate",
                "owner: growth_team",
                'definition: "Monthly customer churn rate"',
                "synonyms:",
                "  - customer churn",
                "grain: monthly",
                "unit: ratio",
                "direction: lower_is_better",
                "calculation:",
                "  numerator:",
                "    source: prod.growth.subscription",
                "    filter: event_type = 'cancel'",
                "    aggregation: COUNT(*)",
                "  denominator:",
                "    source: prod.growth.subscription",
                "    filter: status = 'active'",
                "    aggregation: COUNT(*)",
            ]
        ),
        encoding="utf-8",
    )


class _FakeWarehouseAdapter:
    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="growth")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        assert schema == "growth"
        return [TableInfo(name="subscription", schema=schema)]

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        assert schema == "growth"
        assert table == "subscription"
        return [ColumnInfo(name="subscriber_id", data_type="uuid", nullable=False)]

    def execute_query(self, spec):
        raise NotImplementedError

    def estimate_cost(self, spec):
        raise NotImplementedError

    def validate_query(self, sql: str):
        raise NotImplementedError


class _FakeBigQueryWarehouseAdapter:
    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="analytics")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        assert schema == "analytics"
        return [TableInfo(name="sessions", schema=schema)]

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        assert schema == "analytics"
        assert table == "sessions"
        return [ColumnInfo(name="session_id", data_type="STRING", nullable=False)]

    def execute_query(self, spec):
        raise NotImplementedError

    def estimate_cost(self, spec):
        raise NotImplementedError

    def validate_query(self, sql: str):
        raise NotImplementedError


class _FakeLookerSyncSource:
    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        source_name: str = "looker",
        owner: str = "looker",
    ) -> None:
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._owner = owner
        self.name = source_name

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return [
            Metric.model_validate(
                {
                    "metric_id": "monthly_active_users",
                    "display_name": "Monthly Active Users",
                    "owner": self._owner,
                    "definition": "Looker MAU metric",
                    "synonyms": ["mau"],
                    "grain": "monthly",
                    "unit": "count",
                    "direction": "higher_is_better",
                    "calculation": {
                        "numerator": {
                            "source": "analytics.sessions",
                            "filter": "is_active = true",
                            "aggregation": "COUNT(DISTINCT user_id)",
                        }
                    },
                }
            )
        ]

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return [
            GlossaryTerm.model_validate(
                {
                    "term_id": "term.monthly_active_users",
                    "canonical_form": "monthly active users",
                    "definition": "Looker business term for MAU.",
                    "linked_metric_ids": ["monthly_active_users"],
                    "category": "metric",
                    "owner": self._owner,
                }
            )
        ]

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return []

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return [
            VerifiedQuery.model_validate(
                {
                    "vq_id": "look-123",
                    "metric_id": "monthly_active_users",
                    "dialect": "bigquery",
                    "description": "Looker MAU explore SQL",
                    "sql_template": (
                        "SELECT COUNT(DISTINCT user_id) AS monthly_active_users "
                        "FROM analytics.sessions"
                    ),
                    "referenced_tables": ["analytics.sessions"],
                    "verified_by": self._owner,
                    "last_verified": "2026-04-16",
                    "verification_evidence": "https://looker.example/looks/123",
                }
            )
        ]


class _FakeUnityCatalogSyncSource:
    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        source_name: str = "unity_catalog",
        owner: str = "unity_catalog",
    ) -> None:
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._owner = owner
        self.name = source_name

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return []

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return []

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return [
            TableTrust.model_validate(
                {
                    "fqtn": "main.analytics.orders",
                    "grade": "gold",
                    "owner": self._owner,
                    "description": "Unity Catalog curated orders table",
                    "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                    "grade_rationale": "unity_catalog:gold; lineage_complete",
                    "last_audited": "2026-04-16",
                }
            )
        ]

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return []


def test_semantic_cli_lookup_renders_metric_summary(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    _seed_semantic_workspace(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_semantic_command(
        ["lookup", "customer churn"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "monthly_churn_rate" in output
    assert "Monthly Churn Rate" in output


def test_semantic_cli_lookup_reads_runtime_semantic_db_by_default(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    runtime_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    runtime_container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "net_revenue_retention",
                "display_name": "Net Revenue Retention",
                "owner": "finance_team",
                "definition": "Monthly NRR percentage",
                "synonyms": ["nrr"],
                "grain": "monthly",
                "unit": "percentage",
                "direction": "higher_is_better",
                "calculation": {
                    "numerator": {
                        "source": "prod.finance.account_monthly",
                        "filter": "period_state = 'closed'",
                        "aggregation": "SUM(expansion_mrr)",
                    },
                    "denominator": {
                        "source": "prod.finance.account_monthly",
                        "filter": "period_state = 'closed'",
                        "aggregation": "SUM(starting_mrr)",
                    },
                },
            }
        )
    )
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_semantic_command(
        ["lookup", "nrr"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "net_revenue_retention" in output
    assert "Net Revenue Retention" in output


def test_semantic_cli_load_pack_applies_workspace_pack(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_semantic_command(
        ["load-pack", "--pack-dir", str(pack_dir), "--apply"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "Semantic Pack Load" in output
    assert "monthly_churn_rate" in output


def test_semantic_cli_snapshot_list_and_restore(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    _seed_semantic_workspace(workspace_dir)
    container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    container.snapshots.create(
        snapshot_id="semantic_snapshot-001",
        source_name="test",
        created_at=datetime(2026, 4, 16, 13, 0, tzinfo=UTC),
        note="baseline semantic state",
    )
    container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "monthly_churn_rate",
                "display_name": "Monthly Churn Rate",
                "owner": "growth_team",
                "definition": "Updated churn definition",
                "synonyms": ["gross churn"],
                "grain": "monthly",
                "unit": "ratio",
                "direction": "lower_is_better",
                "calculation": {
                    "numerator": {
                        "source": "prod.growth.subscription",
                        "filter": "event_type = 'cancel'",
                        "aggregation": "COUNT(*)",
                    },
                    "denominator": {
                        "source": "prod.growth.subscription",
                        "filter": "status = 'active'",
                        "aggregation": "COUNT(*)",
                    },
                },
                "verified_query_ids": ["vq-monthly-churn-postgres"],
            }
        )
    )
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    list_exit_code = run_semantic_command(
        ["snapshot", "list"],
        console=console,
        workspace_dir=workspace_dir,
    )
    restore_exit_code = run_semantic_command(
        ["snapshot", "restore", "semantic_snapshot-001"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert list_exit_code == 0
    assert restore_exit_code == 0
    output = out.getvalue()
    assert "Semantic Snapshots" in output
    assert "semantic_snapshot-001" in output
    restored_metric = container.metrics.get("monthly_churn_rate")
    assert restored_metric is not None
    assert restored_metric.definition == "Monthly customer churn rate"


def test_semantic_cli_sync_postgres_applies_connector_schema(tmp_path, monkeypatch) -> None:
    workspace_dir = str(tmp_path)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=workspace_dir),
        connectors={
            "analytics_prod": WarehouseConnectorSettings(
                type=ConnectorType.POSTGRES,
                label="Analytics Postgres",
                options={
                    "host": "localhost",
                    "database": "prod",
                    "schema": "growth",
                },
            )
        },
    )
    monkeypatch.setattr(
        "ds_agent.infrastructure.persistence.connector_factory.create_connector_adapter",
        lambda connector: _FakeWarehouseAdapter(),
    )

    exit_code = run_semantic_command(
        ["sync", "postgres", "--connector", "analytics_prod", "--apply"],
        console=console,
        workspace_dir=workspace_dir,
        config=config,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "Semantic Source Sync" in output
    assert "prod.growth.subscription" in output
    container = build_semantic_memory_container(workspace_dir=workspace_dir)
    assert container.trust.get("prod.growth.subscription") is not None


def test_semantic_cli_sync_bigquery_applies_connector_schema(tmp_path, monkeypatch) -> None:
    workspace_dir = str(tmp_path)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=workspace_dir),
        connectors={
            "warehouse_bq": WarehouseConnectorSettings(
                type=ConnectorType.BIGQUERY,
                label="Warehouse BigQuery",
                options={
                    "project_id": "analytics-project",
                    "schema": "analytics",
                },
            )
        },
    )
    monkeypatch.setattr(
        "ds_agent.infrastructure.persistence.connector_factory.create_connector_adapter",
        lambda connector: _FakeBigQueryWarehouseAdapter(),
    )

    exit_code = run_semantic_command(
        ["sync", "bigquery", "--connector", "warehouse_bq", "--apply"],
        console=console,
        workspace_dir=workspace_dir,
        config=config,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "Semantic Source Sync" in output
    assert "analytics-project.analytics.sessions" in output
    container = build_semantic_memory_container(workspace_dir=workspace_dir)
    assert container.trust.get("analytics-project.analytics.sessions") is not None


def test_semantic_cli_sync_looker_applies_remote_semantic_artifacts(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    with patch("ds_agent.cli.semantic_cli.LookerAdapter", _FakeLookerSyncSource):
        exit_code = run_semantic_command(
            ["sync", "looker", "--endpoint", "https://looker.example/api", "--apply"],
            console=console,
            workspace_dir=workspace_dir,
        )

    assert exit_code == 0
    output = out.getvalue()
    assert "Semantic Source Sync" in output
    assert "looker:monthly_active_users" in output
    container = build_semantic_memory_container(workspace_dir=workspace_dir)
    assert container.metrics.get("looker:monthly_active_users") is not None
    assert container.glossary.get("term.monthly_active_users") is not None
    assert container.verified_queries.get("looker:look-123") is not None


def test_semantic_cli_sync_unity_catalog_applies_remote_trust(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    with patch("ds_agent.cli.semantic_cli.UnityCatalogAdapter", _FakeUnityCatalogSyncSource):
        exit_code = run_semantic_command(
            [
                "sync",
                "unity-catalog",
                "--endpoint",
                "https://unity.example/catalog",
                "--apply",
            ],
            console=console,
            workspace_dir=workspace_dir,
        )

    assert exit_code == 0
    output = out.getvalue()
    assert "Semantic Source Sync" in output
    assert "main.analytics.orders" in output
    container = build_semantic_memory_container(workspace_dir=workspace_dir)
    assert container.trust.get("main.analytics.orders") is not None


def test_semantic_cli_proposal_list_renders_pending_entry(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    proposal_id, approval_id = _seed_semantic_proposal(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_semantic_command(
        ["proposal", "list"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert proposal_id in output
    assert approval_id in output
    assert "Glossary candidate for retained customers" in output


def test_semantic_cli_proposal_list_filters_by_type_and_risk(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    glossary_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        target_id="term.retained_customers",
        risk="medium",
    )
    negative_knowledge_id, _ = _seed_semantic_proposal(
        workspace_dir,
        proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
        summary="Negative knowledge for promo churn exclusions",
        target_id="nk.promo_churn_exclusion",
        risk="high",
        session_id="session-2",
    )
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_semantic_command(
        [
            "proposal",
            "list",
            "--approval-status",
            "all",
            "--proposal-type",
            "negative_knowledge",
            "--risk",
            "high",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert negative_knowledge_id in output
    assert "Negative knowledge for promo churn" in output
    assert glossary_proposal_id not in output


def test_semantic_cli_proposal_reject_updates_approval_and_proposal(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    proposal_id, approval_id = _seed_semantic_proposal(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_semantic_command(
        ["proposal", "reject", approval_id, "--actor", "cli@test", "--reason", "duplicate"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    proposal_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    proposal = proposal_container.proposals.get(proposal_id)
    approval = JsonApprovalStore(workspace_dir).get(approval_id)

    assert proposal is not None
    assert proposal.status.value == "rejected"
    assert approval is not None
    assert approval.status.value == "rejected"
    assert approval.response == "duplicate"


def test_semantic_cli_proposal_approve_many_filters_pending_records(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    first_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        target_id="term.retained_customers_a",
        session_id="session-batch",
        risk="low",
    )
    second_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        target_id="term.retained_customers_b",
        session_id="session-batch",
        risk="low",
    )
    untouched_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
        summary="Negative knowledge outside batch scope",
        target_id="nk.outside_batch_scope",
        session_id="session-other",
        risk="high",
    )
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_semantic_command(
        [
            "proposal",
            "approve-many",
            "--session-id",
            "session-batch",
            "--proposal-type",
            "glossary_term",
            "--risk",
            "low",
            "--actor",
            "cli@test",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    proposal_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    first_proposal = proposal_container.proposals.get(first_proposal_id)
    second_proposal = proposal_container.proposals.get(second_proposal_id)
    untouched_proposal = proposal_container.proposals.get(untouched_proposal_id)

    assert first_proposal is not None
    assert first_proposal.status.value == "approved"
    assert second_proposal is not None
    assert second_proposal.status.value == "approved"
    assert untouched_proposal is not None
    assert untouched_proposal.status.value == "pending"


def test_semantic_cli_proposal_approve_then_apply_materializes_payload(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    proposal_id, approval_id = _seed_semantic_proposal(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    approve_exit_code = run_semantic_command(
        ["proposal", "approve", proposal_id, "--actor", "cli@test"],
        console=console,
        workspace_dir=workspace_dir,
    )
    apply_exit_code = run_semantic_command(
        ["proposal", "apply", proposal_id, "--actor", "cli@test"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert approve_exit_code == 0
    assert apply_exit_code == 0
    proposal_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    proposal = proposal_container.proposals.get(proposal_id)
    glossary_term = proposal_container.glossary.get("term.retained_customers")
    approval = JsonApprovalStore(workspace_dir).get(approval_id)

    assert proposal is not None
    assert proposal.status.value == "applied"
    assert glossary_term is not None
    assert glossary_term.term_id == "term.retained_customers"
    assert approval is not None
    assert approval.metadata["semanticProposalOutcome"]["action"] == "apply"


def test_semantic_cli_proposal_apply_many_materializes_filtered_payloads(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    first_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        target_id="term.batch_apply_a",
        session_id="session-apply",
        risk="medium",
    )
    second_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        target_id="term.batch_apply_b",
        session_id="session-apply",
        risk="medium",
    )
    untouched_proposal_id, _ = _seed_semantic_proposal(
        workspace_dir,
        proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
        summary="Negative knowledge outside apply batch",
        target_id="nk.outside_apply_batch",
        session_id="session-apply",
        risk="high",
    )
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_semantic_command(
        [
            "proposal",
            "apply-many",
            "--session-id",
            "session-apply",
            "--proposal-type",
            "glossary_term",
            "--actor",
            "cli@test",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    proposal_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    first_proposal = proposal_container.proposals.get(first_proposal_id)
    second_proposal = proposal_container.proposals.get(second_proposal_id)
    untouched_proposal = proposal_container.proposals.get(untouched_proposal_id)
    first_term = proposal_container.glossary.get("term.batch_apply_a")
    second_term = proposal_container.glossary.get("term.batch_apply_b")

    assert first_proposal is not None
    assert first_proposal.status.value == "applied"
    assert second_proposal is not None
    assert second_proposal.status.value == "applied"
    assert untouched_proposal is not None
    assert untouched_proposal.status.value == "pending"
    assert first_term is not None
    assert first_term.term_id == "term.batch_apply_a"
    assert second_term is not None
    assert second_term.term_id == "term.batch_apply_b"
