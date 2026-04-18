from __future__ import annotations

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.org_context import CalendarEvent, NegativeKnowledge
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.memory.semantic.prompt_hints import SemanticMemoryHintBuilder


def test_semantic_memory_hint_builder_returns_compact_summary(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )
    container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "monthly_churn_rate",
                "display_name": "Monthly Churn Rate",
                "owner": "growth_team",
                "definition": "Customer churn rate",
                "grain": "monthly",
                "unit": "ratio",
                "direction": "lower_is_better",
                "calculation": {
                    "numerator": {
                        "source": "prod.growth.subscription",
                        "filter": "event_type = 'cancel'",
                        "aggregation": "COUNT(*)",
                    }
                },
            }
        )
    )
    container.glossary.save(
        GlossaryTerm.model_validate(
            {
                "term_id": "term.churn",
                "canonical_form": "churn",
                "definition": "Customer churn",
                "category": "metric",
            }
        )
    )
    container.trust.save(
        TableTrust.model_validate(
            {
                "fqtn": "prod.growth.subscription",
                "grade": "gold",
                "owner": "growth_team",
                "description": "Subscription fact",
                "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                "grade_rationale": "Certified",
                "last_audited": "2026-04-15",
            }
        )
    )
    container.verified_queries.save(
        VerifiedQuery.model_validate(
            {
                "vq_id": "vq-churn",
                "metric_id": "monthly_churn_rate",
                "dialect": "postgres",
                "description": "Verified churn query",
                "sql_template": "SELECT 0.1 AS monthly_churn_rate",
                "referenced_tables": ["prod.growth.subscription"],
                "verified_by": "reviewer",
                "last_verified": "2026-04-15",
                "verification_evidence": "dashboard parity",
            }
        )
    )
    container.org_context.save_calendar_event(
        CalendarEvent.model_validate(
            {
                "event_id": "evt-1",
                "type": "campaign",
                "name": "Spring Promo",
                "start_date": "2026-04-10",
                "end_date": "2026-04-20",
                "description": "Promo window",
            }
        )
    )
    container.org_context.save_negative_knowledge(
        NegativeKnowledge.model_validate(
            {
                "nk_id": "nk-1",
                "topic": "monthly_churn_rate",
                "wrong_approach": "include promo cohort",
                "why_wrong": "inflates churn",
                "correct_approach": "exclude promo cohort",
                "recorded_at": "2026-04-15T00:00:00+00:00",
                "recorded_by": "retrospective",
            }
        )
    )

    hints = SemanticMemoryHintBuilder(workspace_dir).build_hints()

    assert "## Semantic Context" in hints
    assert "monthly_churn_rate" in hints
    assert "churn" in hints
    assert "Spring Promo" in hints
    assert "exclude promo cohort" in hints


def test_semantic_memory_hint_builder_returns_empty_without_db(tmp_path) -> None:
    hints = SemanticMemoryHintBuilder(str(tmp_path)).build_hints()
    assert hints == ""
