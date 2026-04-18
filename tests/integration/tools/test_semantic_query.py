from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.org_context import CalendarEvent, NegativeKnowledge
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.tools._semantic_common import set_semantic_memory_container
from ds_agent.tools.registry import ToolRegistry


def _load_modules() -> None:
    for module_name in [
        "ds_agent.tools.lookup_term",
        "ds_agent.tools.describe_table_trust",
        "ds_agent.tools.semantic_query",
    ]:
        importlib.import_module(module_name)


def _seed_semantic_memory(tmp_path):
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
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
                "caveats": ["Exclude promo cohort."],
            }
        )
    )
    container.glossary.save(
        GlossaryTerm.model_validate(
            {
                "term_id": "term.churn",
                "canonical_form": "churn",
                "definition": "Customer churn",
                "synonyms": ["customer churn"],
                "linked_metric_ids": ["monthly_churn_rate"],
                "category": "metric",
                "owner": "growth_team",
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
    container.org_context.save_negative_knowledge(
        NegativeKnowledge.model_validate(
            {
                "nk_id": "nk-churn-promo",
                "topic": "monthly_churn_rate",
                "wrong_approach": "include promo cohort",
                "why_wrong": "inflates churn",
                "correct_approach": "exclude promo cohort",
                "recorded_at": "2026-04-15T00:00:00+00:00",
                "recorded_by": "retrospective",
            }
        )
    )
    container.org_context.save_calendar_event(
        CalendarEvent.model_validate(
            {
                "event_id": "evt-spring-promo",
                "type": "campaign",
                "name": "Spring Promotion",
                "start_date": "2026-04-10",
                "end_date": "2026-04-20",
                "description": "Marketing promotion",
                "impact_hint": "Churn may be temporarily distorted.",
            }
        )
    )
    return container


def _seed_builtin_pack(tmp_path):
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    pack_dir = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ds_agent"
        / "skills"
        / "domain"
        / "domain-pack-enterprise"
    )
    result = container.load_semantic_pack.execute(str(pack_dir), dry_run=False)
    assert len(result.applied_metric_ids) >= 10
    return container


@pytest.fixture(autouse=True)
def _reset_semantic_container():
    set_semantic_memory_container(None)
    yield
    set_semantic_memory_container(None)


@pytest.mark.asyncio
async def test_semantic_query_prefers_verified_query(tmp_path) -> None:
    _load_modules()
    set_semantic_memory_container(_seed_semantic_memory(tmp_path))

    payload = json.loads(
        await ToolRegistry.dispatch(
            "semantic_query",
            {
                "question": "Show monthly churn rate",
                "required_grain": "monthly",
                "as_of_date": "2026-04-16",
            },
        )
    )

    assert payload["kind"] == "verified"
    assert payload["verified_query_id"] == "vq-monthly-churn-postgres"
    assert payload["next_action"] == "execute"
    assert payload["negative_knowledge"]
    assert payload["calendar_hints"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "metric_id", "verified_query_id"),
    [
        ("이탈률", "monthly_churn_rate", "vq-monthly-churn-postgres"),
        ("MAU", "monthly_active_users", "vq-mau-postgres"),
        ("LTV", "lifetime_value", "vq-ltv-postgres"),
    ],
)
async def test_semantic_query_builtin_pack_returns_verified_for_core_kpis(
    tmp_path,
    question: str,
    metric_id: str,
    verified_query_id: str,
) -> None:
    _load_modules()
    set_semantic_memory_container(_seed_builtin_pack(tmp_path))

    payload = json.loads(
        await ToolRegistry.dispatch(
            "semantic_query",
            {
                "question": question,
                "required_grain": "monthly",
            },
        )
    )

    assert payload["kind"] == "verified"
    assert payload["metric"]["metric_id"] == metric_id
    assert payload["verified_query_id"] == verified_query_id
    assert payload["next_action"] == "execute"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("grade", "expected_next_action", "warning_fragment"),
    [
        ("bronze", "ask_user", "manual confirmation required"),
        ("untrusted", "block", "untrusted table referenced"),
    ],
)
async def test_semantic_query_warns_for_bronze_or_untrusted_tables(
    tmp_path,
    grade: str,
    expected_next_action: str,
    warning_fragment: str,
) -> None:
    _load_modules()
    container = _seed_builtin_pack(tmp_path)
    container.trust.save(
        TableTrust.model_validate(
            {
                "fqtn": "prod.product.user_activity_daily",
                "grade": grade,
                "owner": "product_analytics",
                "description": "Temporarily downgraded activity mart for trust-policy validation.",
                "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                "grade_rationale": "Synthetic downgrade for semantic_query trust coverage.",
                "last_audited": "2026-04-16",
            }
        )
    )
    set_semantic_memory_container(container)

    payload = json.loads(
        await ToolRegistry.dispatch(
            "semantic_query",
            {
                "question": "MAU",
                "required_grain": "monthly",
            },
        )
    )

    assert payload["kind"] == "verified"
    assert payload["metric"]["metric_id"] == "monthly_active_users"
    assert payload["verified_query_id"] == "vq-mau-postgres"
    assert payload["trust_report"][0]["grade"] == grade
    assert payload["next_action"] == expected_next_action
    assert any(warning_fragment in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_lookup_term_returns_glossary_matches(tmp_path) -> None:
    _load_modules()
    set_semantic_memory_container(_seed_semantic_memory(tmp_path))

    payload = json.loads(await ToolRegistry.dispatch("lookup_term", {"query": "customer churn"}))

    assert payload["count"] == 1
    assert payload["matches"][0]["canonical_form"] == "churn"


@pytest.mark.asyncio
async def test_describe_table_trust_returns_policy(tmp_path) -> None:
    _load_modules()
    set_semantic_memory_container(_seed_semantic_memory(tmp_path))

    payload = json.loads(
        await ToolRegistry.dispatch(
            "describe_table_trust",
            {"fqtns": ["prod.growth.subscription"]},
        )
    )

    assert payload["action"] == "allow"
    assert payload["tables"][0]["grade"] == "gold"
