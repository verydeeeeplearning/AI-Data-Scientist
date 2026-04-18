"""Regenerate the built-in enterprise semantic pack and checksum."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ds_agent.memory.semantic.infrastructure.yaml_metric_loader import YamlMetricLoader

PACK_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "ds_agent"
    / "skills"
    / "domain"
    / "domain-pack-enterprise"
)


METRICS: list[dict[str, Any]] = [
    {
        "file": "monthly_churn_rate.yaml",
        "metric_id": "monthly_churn_rate",
        "display_name": "Monthly Churn Rate",
        "owner": "growth_team",
        "definition": "Monthly customer churn rate for active subscriptions.",
        "synonyms": ["customer churn", "churn rate", "logo churn", "이탈률"],
        "grain": "monthly",
        "unit": "ratio",
        "direction": "lower_is_better",
        "related_metrics": ["net_revenue_retention", "lifetime_value"],
        "caveats": [
            "Exclude promotional cohorts when comparing against baseline retention.",
            "Review B2B and B2C segments separately for board reporting.",
        ],
        "verified_query_ids": [
            "vq-monthly-churn-postgres",
            "vq-monthly-churn-bigquery",
        ],
        "calculation": {
            "numerator": (
                "prod.growth.subscription",
                "event_type = 'cancel'",
                "COUNT(*)",
            ),
            "denominator": (
                "prod.growth.subscription",
                "status = 'active'",
                "COUNT(*)",
            ),
        },
    },
    {
        "file": "monthly_active_users.yaml",
        "metric_id": "monthly_active_users",
        "display_name": "Monthly Active Users",
        "owner": "product_analytics",
        "definition": "Distinct active users with at least one qualifying session in a month.",
        "synonyms": ["MAU", "active users monthly"],
        "grain": "monthly",
        "unit": "count",
        "direction": "higher_is_better",
        "related_metrics": ["weekly_active_users", "trial_to_paid_conversion_rate"],
        "caveats": [
            "Bot traffic and internal QA traffic must be filtered before executive reporting."
        ],
        "verified_query_ids": ["vq-mau-postgres", "vq-mau-bigquery"],
        "calculation": {
            "numerator": (
                "prod.product.user_activity_daily",
                "activity_flag = TRUE",
                "COUNT(DISTINCT user_id)",
            )
        },
    },
    {
        "file": "lifetime_value.yaml",
        "metric_id": "lifetime_value",
        "display_name": "Lifetime Value",
        "owner": "finance_team",
        "definition": (
            "Average net revenue retained per customer across the measured lifetime window."
        ),
        "synonyms": ["LTV", "customer lifetime value"],
        "grain": "monthly",
        "unit": "amount",
        "direction": "higher_is_better",
        "related_metrics": ["average_revenue_per_user", "customer_acquisition_cost"],
        "caveats": [
            "Gross-margin-adjusted LTV should be used for board packages and pricing reviews."
        ],
        "verified_query_ids": ["vq-ltv-postgres", "vq-ltv-bigquery"],
        "calculation": {
            "numerator": (
                "prod.finance.mrr_ledger",
                "customer_status = 'retained'",
                "SUM(net_revenue_amount)",
            ),
            "denominator": (
                "prod.growth.customer",
                "lifecycle_status = 'active'",
                "COUNT(DISTINCT customer_id)",
            ),
        },
    },
    {
        "file": "average_revenue_per_user.yaml",
        "metric_id": "average_revenue_per_user",
        "display_name": "Average Revenue Per User",
        "owner": "finance_team",
        "definition": "Average recognized subscription revenue per active user within a month.",
        "synonyms": ["ARPU", "revenue per user"],
        "grain": "monthly",
        "unit": "amount",
        "direction": "higher_is_better",
        "related_metrics": ["monthly_recurring_revenue", "monthly_active_users"],
        "caveats": [
            (
                "Enterprise contracts may require separate segmentation because seat "
                "bundles distort the mean."
            )
        ],
        "verified_query_ids": ["vq-arpu-postgres", "vq-arpu-bigquery"],
        "calculation": {
            "numerator": (
                "prod.finance.mrr_ledger",
                "revenue_type = 'subscription'",
                "SUM(net_revenue_amount)",
            ),
            "denominator": (
                "prod.growth.subscription",
                "status = 'active'",
                "COUNT(DISTINCT subscription_id)",
            ),
        },
    },
    {
        "file": "net_revenue_retention.yaml",
        "metric_id": "net_revenue_retention",
        "display_name": "Net Revenue Retention",
        "owner": "finance_team",
        "definition": (
            "Percentage of starting recurring revenue retained after expansion and "
            "contraction within a month."
        ),
        "synonyms": ["NRR", "net dollar retention"],
        "grain": "monthly",
        "unit": "percentage",
        "direction": "higher_is_better",
        "related_metrics": ["monthly_recurring_revenue", "monthly_churn_rate"],
        "caveats": [
            "Pause and write-off adjustments are excluded from the certified executive definition."
        ],
        "verified_query_ids": ["vq-nrr-postgres"],
        "calculation": {
            "numerator": (
                "prod.finance.mrr_ledger",
                "movement_type IN ('starting','expansion','contraction')",
                "SUM(net_revenue_amount)",
            ),
            "denominator": (
                "prod.finance.mrr_ledger",
                "movement_type = 'starting'",
                "SUM(net_revenue_amount)",
            ),
        },
    },
    {
        "file": "weekly_active_users.yaml",
        "metric_id": "weekly_active_users",
        "display_name": "Weekly Active Users",
        "owner": "product_analytics",
        "definition": (
            "Distinct active users with at least one qualifying session in a rolling "
            "seven-day window."
        ),
        "synonyms": ["WAU", "weekly active users"],
        "grain": "weekly",
        "unit": "count",
        "direction": "higher_is_better",
        "related_metrics": ["monthly_active_users"],
        "caveats": [
            "Weekend-only products should be compared using trailing four-week seasonality."
        ],
        "verified_query_ids": ["vq-wau-postgres"],
        "calculation": {
            "numerator": (
                "prod.product.user_activity_daily",
                "activity_flag = TRUE",
                "COUNT(DISTINCT user_id)",
            )
        },
    },
    {
        "file": "customer_acquisition_cost.yaml",
        "metric_id": "customer_acquisition_cost",
        "display_name": "Customer Acquisition Cost",
        "owner": "marketing_ops",
        "definition": "Average attributable acquisition spend per closed-won customer in a month.",
        "synonyms": ["CAC", "paid acquisition cost"],
        "grain": "monthly",
        "unit": "amount",
        "direction": "lower_is_better",
        "related_metrics": ["trial_to_paid_conversion_rate", "lifetime_value"],
        "caveats": [
            "Partner-sourced deals are excluded unless spend is recorded in the attribution mart."
        ],
        "verified_query_ids": ["vq-cac-postgres"],
        "calculation": {
            "numerator": (
                "prod.marketing.attribution_touch",
                "attributed_flag = TRUE",
                "SUM(spend_amount)",
            ),
            "denominator": (
                "prod.sales.opportunity",
                "stage = 'closed_won'",
                "COUNT(DISTINCT account_id)",
            ),
        },
    },
    {
        "file": "gross_margin.yaml",
        "metric_id": "gross_margin",
        "display_name": "Gross Margin",
        "owner": "finance_team",
        "definition": (
            "Recognized gross profit divided by recognized revenue within the reporting month."
        ),
        "synonyms": ["gross margin percent", "GM"],
        "grain": "monthly",
        "unit": "percentage",
        "direction": "higher_is_better",
        "related_metrics": ["monthly_recurring_revenue", "lifetime_value"],
        "caveats": [
            "Hosting-cost accrual timing can move the metric by a few basis points near month end."
        ],
        "verified_query_ids": ["vq-gross-margin-postgres"],
        "calculation": {
            "numerator": (
                "prod.finance.invoice_line",
                "invoice_status = 'posted'",
                "SUM(gross_profit_amount)",
            ),
            "denominator": (
                "prod.finance.invoice_line",
                "invoice_status = 'posted'",
                "SUM(recognized_revenue_amount)",
            ),
        },
    },
    {
        "file": "trial_to_paid_conversion_rate.yaml",
        "metric_id": "trial_to_paid_conversion_rate",
        "display_name": "Trial To Paid Conversion Rate",
        "owner": "growth_team",
        "definition": (
            "Rate of trial accounts that convert to a paid subscription in the measurement month."
        ),
        "synonyms": ["trial conversion", "trial to paid"],
        "grain": "monthly",
        "unit": "ratio",
        "direction": "higher_is_better",
        "related_metrics": ["customer_acquisition_cost", "monthly_active_users"],
        "caveats": [
            (
                "Self-serve and sales-assisted motion should be reviewed separately "
                "for funnel diagnostics."
            )
        ],
        "verified_query_ids": ["vq-trial-to-paid-postgres"],
        "calculation": {
            "numerator": (
                "prod.product.trial_funnel_daily",
                "converted_flag = TRUE",
                "COUNT(DISTINCT account_id)",
            ),
            "denominator": (
                "prod.product.trial_funnel_daily",
                "trial_started_flag = TRUE",
                "COUNT(DISTINCT account_id)",
            ),
        },
    },
    {
        "file": "monthly_recurring_revenue.yaml",
        "metric_id": "monthly_recurring_revenue",
        "display_name": "Monthly Recurring Revenue",
        "owner": "finance_team",
        "definition": "Ending monthly recurring subscription revenue for the measurement month.",
        "synonyms": ["MRR", "recurring revenue"],
        "grain": "monthly",
        "unit": "amount",
        "direction": "higher_is_better",
        "related_metrics": ["average_revenue_per_user", "net_revenue_retention"],
        "caveats": [
            "Non-recurring services revenue is excluded from the certified MRR definition."
        ],
        "verified_query_ids": ["vq-mrr-postgres", "vq-mrr-bigquery"],
        "calculation": {
            "numerator": (
                "prod.finance.mrr_ledger",
                "revenue_type = 'subscription'",
                "SUM(mrr_amount)",
            )
        },
    },
]

GLOSSARY: list[tuple[str, str, str, str, list[str], list[str], list[str], str, str]] = [
    (
        "churn.yaml",
        "term.churn",
        "churn",
        "Customer churn measured as cancelled active subscriptions within a month.",
        ["customer churn", "churn rate", "이탈률"],
        ["CCR"],
        ["monthly_churn_rate"],
        "metric",
        "growth_team",
    ),
    (
        "customer_churn.yaml",
        "term.customer_churn",
        "customer churn",
        "Loss of customers or subscriptions over the reporting window.",
        ["subscriber churn"],
        [],
        ["monthly_churn_rate"],
        "metric",
        "growth_team",
    ),
    (
        "logo_churn.yaml",
        "term.logo_churn",
        "logo churn",
        "Count-based churn focused on losing customer accounts instead of revenue.",
        ["account churn"],
        [],
        ["monthly_churn_rate"],
        "metric",
        "growth_team",
    ),
    (
        "revenue_churn.yaml",
        "term.revenue_churn",
        "revenue churn",
        "Recurring revenue lost from downgrades or cancellations before expansion offsets.",
        [],
        [],
        ["net_revenue_retention", "monthly_recurring_revenue"],
        "metric",
        "finance_team",
    ),
    (
        "retention.yaml",
        "term.retention",
        "retention",
        "Portion of customers or revenue retained after churn and downgrade movements.",
        [],
        [],
        ["net_revenue_retention"],
        "metric",
        "growth_team",
    ),
    (
        "mau.yaml",
        "term.mau",
        "MAU",
        "Monthly active users measured from the certified daily activity mart.",
        ["monthly active users"],
        ["MAU"],
        ["monthly_active_users"],
        "metric",
        "product_analytics",
    ),
    (
        "monthly_active_users.yaml",
        "term.monthly_active_users",
        "monthly active users",
        "Distinct users active at least once during the measurement month.",
        ["mau"],
        [],
        ["monthly_active_users"],
        "metric",
        "product_analytics",
    ),
    (
        "active_user.yaml",
        "term.active_user",
        "active user",
        "User meeting the current activity policy for product engagement scorecards.",
        ["engaged user"],
        [],
        ["monthly_active_users", "weekly_active_users"],
        "entity",
        "product_analytics",
    ),
    (
        "wau.yaml",
        "term.wau",
        "WAU",
        "Weekly active users measured on a rolling seven-day basis.",
        ["weekly active users"],
        ["WAU"],
        ["weekly_active_users"],
        "metric",
        "product_analytics",
    ),
    (
        "weekly_active_users.yaml",
        "term.weekly_active_users",
        "weekly active users",
        "Distinct users active at least once within the current rolling week.",
        ["wau"],
        [],
        ["weekly_active_users"],
        "metric",
        "product_analytics",
    ),
    (
        "ltv.yaml",
        "term.ltv",
        "LTV",
        "Lifetime value generated by an average retained customer.",
        ["customer lifetime value"],
        ["LTV"],
        ["lifetime_value"],
        "metric",
        "finance_team",
    ),
    (
        "lifetime_value.yaml",
        "term.lifetime_value",
        "lifetime value",
        "Average net revenue expected from a customer across the retained lifetime window.",
        ["ltv"],
        [],
        ["lifetime_value"],
        "metric",
        "finance_team",
    ),
    (
        "arpu.yaml",
        "term.arpu",
        "ARPU",
        "Average revenue per user for active subscriptions in the month.",
        ["average revenue per user"],
        ["ARPU"],
        ["average_revenue_per_user"],
        "metric",
        "finance_team",
    ),
    (
        "average_revenue_per_user.yaml",
        "term.average_revenue_per_user",
        "average revenue per user",
        "Recognized subscription revenue divided by active users or subscriptions.",
        ["arpu"],
        [],
        ["average_revenue_per_user"],
        "metric",
        "finance_team",
    ),
    (
        "nrr.yaml",
        "term.nrr",
        "NRR",
        "Net revenue retention including expansion and contraction effects.",
        ["net dollar retention"],
        ["NRR"],
        ["net_revenue_retention"],
        "metric",
        "finance_team",
    ),
    (
        "net_revenue_retention.yaml",
        "term.net_revenue_retention",
        "net revenue retention",
        "Share of starting recurring revenue retained after all in-period movements.",
        ["nrr"],
        [],
        ["net_revenue_retention"],
        "metric",
        "finance_team",
    ),
    (
        "mrr.yaml",
        "term.mrr",
        "MRR",
        "Monthly recurring revenue from active subscription contracts.",
        ["monthly recurring revenue"],
        ["MRR"],
        ["monthly_recurring_revenue"],
        "metric",
        "finance_team",
    ),
    (
        "monthly_recurring_revenue.yaml",
        "term.monthly_recurring_revenue",
        "monthly recurring revenue",
        "Certified month-end recurring subscription revenue.",
        ["mrr"],
        [],
        ["monthly_recurring_revenue"],
        "metric",
        "finance_team",
    ),
    (
        "cac.yaml",
        "term.cac",
        "CAC",
        "Customer acquisition cost measured from attributable spend and closed-won deals.",
        ["customer acquisition cost"],
        ["CAC"],
        ["customer_acquisition_cost"],
        "metric",
        "marketing_ops",
    ),
    (
        "customer_acquisition_cost.yaml",
        "term.customer_acquisition_cost",
        "customer acquisition cost",
        "Attributed acquisition spend divided by new paying customers.",
        ["cac"],
        [],
        ["customer_acquisition_cost"],
        "metric",
        "marketing_ops",
    ),
    (
        "gross_margin.yaml",
        "term.gross_margin",
        "gross margin",
        "Recognized gross profit divided by recognized revenue.",
        [],
        [],
        ["gross_margin"],
        "metric",
        "finance_team",
    ),
    (
        "gross_profit.yaml",
        "term.gross_profit",
        "gross profit",
        "Revenue after direct cost of service, used as the numerator for gross margin.",
        [],
        [],
        ["gross_margin"],
        "metric",
        "finance_team",
    ),
    (
        "trial_to_paid_conversion.yaml",
        "term.trial_to_paid_conversion",
        "trial to paid conversion",
        "Share of trial accounts converting to a paid subscription.",
        ["trial conversion"],
        [],
        ["trial_to_paid_conversion_rate"],
        "metric",
        "growth_team",
    ),
    (
        "conversion_rate.yaml",
        "term.conversion_rate",
        "conversion rate",
        "General share of entities progressing from one funnel state to another.",
        [],
        [],
        ["trial_to_paid_conversion_rate"],
        "metric",
        "growth_team",
    ),
    (
        "active_subscription.yaml",
        "term.active_subscription",
        "active subscription",
        "Subscription contract currently in force and billable under the revenue policy.",
        [],
        [],
        ["monthly_recurring_revenue", "monthly_churn_rate"],
        "entity",
        "growth_team",
    ),
    (
        "expansion_revenue.yaml",
        "term.expansion_revenue",
        "expansion revenue",
        "Recurring revenue increase from upsell, cross-sell, or seat growth.",
        [],
        [],
        ["net_revenue_retention"],
        "metric",
        "finance_team",
    ),
    (
        "contraction_revenue.yaml",
        "term.contraction_revenue",
        "contraction revenue",
        "Recurring revenue decrease from downgrades, seat reductions, or discount changes.",
        [],
        [],
        ["net_revenue_retention"],
        "metric",
        "finance_team",
    ),
    (
        "payback_period.yaml",
        "term.payback_period",
        "payback period",
        "Time needed for gross margin dollars to recover customer acquisition cost.",
        [],
        [],
        ["customer_acquisition_cost", "lifetime_value"],
        "other",
        "finance_team",
    ),
    (
        "billing_cycle.yaml",
        "term.billing_cycle",
        "billing cycle",
        "Recurring billing interval such as monthly or annual invoicing.",
        [],
        [],
        ["monthly_recurring_revenue"],
        "dimension",
        "billing_ops",
    ),
    (
        "subscription_plan.yaml",
        "term.subscription_plan",
        "subscription plan",
        "Commercial packaging tier used to price and segment subscriptions.",
        [],
        [],
        ["monthly_recurring_revenue", "average_revenue_per_user"],
        "dimension",
        "billing_ops",
    ),
]

TRUST: list[
    tuple[
        str,
        str,
        str,
        str,
        str,
        str,
        int,
        str,
        list[dict[str, Any]],
    ]
] = [
    (
        "prod.growth.subscription.yaml",
        "prod.growth.subscription",
        "gold",
        "growth_team",
        "Subscription fact table for active, cancelled, and resumed customer lifecycle events.",
        "daily",
        1440,
        "Certified by analytics engineering and used for KPI scorecards.",
        [
            {
                "target_fqtn": "prod.growth.customer",
                "left_keys": ["customer_id"],
                "right_keys": ["customer_id"],
                "join_type": "left",
                "cardinality": "one_to_one",
            }
        ],
    ),
    (
        "prod.growth.customer.yaml",
        "prod.growth.customer",
        "gold",
        "growth_team",
        "Canonical customer dimension with lifecycle status, segment, and region attributes.",
        "daily",
        1440,
        "Certified customer dimension for board and finance metrics.",
        [],
    ),
    (
        "prod.product.user_activity_daily.yaml",
        "prod.product.user_activity_daily",
        "gold",
        "product_analytics",
        "Daily user activity mart with bot-filtered engagement signals.",
        "daily",
        1440,
        "Certified product mart used for MAU and WAU reporting.",
        [],
    ),
    (
        "prod.finance.mrr_ledger.yaml",
        "prod.finance.mrr_ledger",
        "gold",
        "finance_team",
        "Recurring revenue ledger capturing starting, expansion, contraction, and ending balances.",
        "daily",
        1440,
        "Certified finance ledger used for MRR, NRR, ARPU, and LTV.",
        [],
    ),
    (
        "prod.finance.invoice_line.yaml",
        "prod.finance.invoice_line",
        "gold",
        "finance_team",
        "Posted invoice line mart with recognized revenue and gross profit fields.",
        "daily",
        1440,
        "Certified revenue accounting mart for gross margin reporting.",
        [],
    ),
    (
        "prod.marketing.attribution_touch.yaml",
        "prod.marketing.attribution_touch",
        "gold",
        "marketing_ops",
        "Attributed marketing spend mart aligned to campaign and channel taxonomy.",
        "daily",
        1440,
        "Certified acquisition-spend mart reconciled to the budget model.",
        [],
    ),
    (
        "prod.sales.opportunity.yaml",
        "prod.sales.opportunity",
        "gold",
        "revops_team",
        "Closed-won opportunity mart aligned to ARR and new-logo booking policy.",
        "daily",
        1440,
        "Certified CRM opportunity mart for acquisition and conversion metrics.",
        [],
    ),
    (
        "prod.product.trial_funnel_daily.yaml",
        "prod.product.trial_funnel_daily",
        "gold",
        "product_analytics",
        "Daily trial funnel mart covering starts, activations, and paid conversions.",
        "daily",
        1440,
        "Certified funnel mart used for trial-to-paid KPI review.",
        [],
    ),
    (
        "prod.billing.plan_catalog.yaml",
        "prod.billing.plan_catalog",
        "gold",
        "billing_ops",
        "Canonical billing plan dimension with interval, package, and pricing metadata.",
        "weekly",
        10080,
        "Certified plan catalog used by finance and growth segmentation.",
        [],
    ),
    (
        "prod.support.ticket.yaml",
        "prod.support.ticket",
        "gold",
        "support_ops",
        "Support ticket mart with SLA timestamps and queue ownership metadata.",
        "daily",
        1440,
        "Certified support operations mart for service-level diagnostics.",
        [],
    ),
    (
        "staging.growth.subscription_snapshot.yaml",
        "staging.growth.subscription_snapshot",
        "silver",
        "growth_team",
        "Pre-curated subscription snapshot used for investigation before promotion to gold marts.",
        "daily",
        1440,
        "Monitored staging mirror with freshness checks but pending final audit.",
        [],
    ),
    (
        "staging.product.event_stream.yaml",
        "staging.product.event_stream",
        "silver",
        "product_analytics",
        "Sessionized product event staging feed with standard deduplication applied.",
        "hourly",
        180,
        "Trusted for debugging and intermediate rollups, not for executive KPI publication.",
        [],
    ),
    (
        "staging.finance.invoice_raw.yaml",
        "staging.finance.invoice_raw",
        "silver",
        "finance_team",
        "Raw invoice staging feed prior to revenue-recognition adjustments.",
        "daily",
        1440,
        "Monitored finance ingest used for reconciliation before gold transforms.",
        [],
    ),
    (
        "staging.finance.refund_raw.yaml",
        "staging.finance.refund_raw",
        "silver",
        "finance_team",
        "Refund and credit staging feed used to reconcile net revenue movements.",
        "daily",
        1440,
        "Monitored refund feed with basic validation but incomplete lineage.",
        [],
    ),
    (
        "staging.marketing.ad_spend_daily.yaml",
        "staging.marketing.ad_spend_daily",
        "silver",
        "marketing_ops",
        "Daily paid-media spend staging table by platform, campaign, and source.",
        "daily",
        1440,
        "Campaign taxonomy is monitored but not fully certified for board reporting.",
        [],
    ),
    (
        "staging.sales.crm_account.yaml",
        "staging.sales.crm_account",
        "silver",
        "revops_team",
        "CRM account staging table with ownership and lifecycle signals.",
        "daily",
        1440,
        "Operationally useful staging dimension with limited audit coverage.",
        [],
    ),
    (
        "staging.product.session_fact.yaml",
        "staging.product.session_fact",
        "silver",
        "product_analytics",
        "Session-level activity fact used for engagement debugging and ad hoc slicing.",
        "daily",
        1440,
        "Supports investigation workflows but not certified KPI aggregation.",
        [],
    ),
    (
        "staging.billing.exchange_rate_daily.yaml",
        "staging.billing.exchange_rate_daily",
        "silver",
        "billing_ops",
        "Daily foreign-exchange staging table used for currency normalization.",
        "daily",
        1440,
        "Monitored reference data pending treasury audit signoff.",
        [],
    ),
    (
        "staging.support.ticket_event.yaml",
        "staging.support.ticket_event",
        "silver",
        "support_ops",
        "Ticket event stream staging table with queue transitions and response timestamps.",
        "hourly",
        240,
        "Useful for operational triage with partial lineage coverage.",
        [],
    ),
    (
        "staging.revops.pipeline_snapshot.yaml",
        "staging.revops.pipeline_snapshot",
        "silver",
        "revops_team",
        "Pipeline snapshot staging mart for forecast and conversion investigations.",
        "daily",
        1440,
        "Monitored revops staging mart awaiting full semantic certification.",
        [],
    ),
]

VERIFIED_QUERIES: list[dict[str, Any]] = [
    {
        "file": "vq-monthly-churn-postgres.sql",
        "vq_id": "vq-monthly-churn-postgres",
        "metric_id": "monthly_churn_rate",
        "dialect": "postgres",
        "description": "Verified monthly churn query for active subscriptions.",
        "referenced_tables": ["prod.growth.subscription"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": "Dashboard parity confirmed against finance KPI scorecard.",
        "failure_modes": ["Promo cohorts inflate churn when not filtered separately."],
        "tags": ["default", "scorecard"],
        "sql": """WITH month_window AS (
    SELECT DATE '2026-04-01' AS month_start
),
numerator AS (
    SELECT COUNT(*) AS value
    FROM prod.growth.subscription
    WHERE event_type = 'cancel'
      AND event_at >= (SELECT month_start FROM month_window)
      AND event_at < (SELECT month_start + INTERVAL '1 month' FROM month_window)
),
denominator AS (
    SELECT COUNT(*) AS value
    FROM prod.growth.subscription
    WHERE status = 'active'
      AND snapshot_date = DATE '2026-04-30'
)
SELECT 1.0 * numerator.value / NULLIF(denominator.value, 0) AS monthly_churn_rate
FROM numerator
CROSS JOIN denominator;""",
    },
    {
        "file": "vq-monthly-churn-bigquery.sql",
        "vq_id": "vq-monthly-churn-bigquery",
        "metric_id": "monthly_churn_rate",
        "dialect": "bigquery",
        "description": "Verified monthly churn query for the certified BigQuery growth mart.",
        "referenced_tables": ["prod.growth.subscription"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("BigQuery parity confirmed against the growth operating review."),
        "tags": ["growth", "bigquery"],
        "sql": """WITH month_window AS (
  SELECT DATE '2026-04-01' AS month_start
)
SELECT SAFE_DIVIDE(
  SUM(
    CASE
      WHEN event_type = 'cancel'
        AND event_at >= (SELECT month_start FROM month_window)
        AND event_at < DATE_ADD((SELECT month_start FROM month_window), INTERVAL 1 MONTH)
      THEN 1
      ELSE 0
    END
  ),
  SUM(CASE WHEN status = 'active' AND snapshot_date = DATE '2026-04-30' THEN 1 ELSE 0 END)
) AS monthly_churn_rate
FROM `prod.growth.subscription`;""",
    },
    {
        "file": "vq-mau-postgres.sql",
        "vq_id": "vq-mau-postgres",
        "metric_id": "monthly_active_users",
        "dialect": "postgres",
        "description": "Verified MAU query over the certified user activity mart.",
        "referenced_tables": ["prod.product.user_activity_daily"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("Product dashboard parity confirmed by analytics engineering."),
        "tags": ["default", "product"],
        "sql": """SELECT COUNT(DISTINCT user_id) AS monthly_active_users
FROM prod.product.user_activity_daily
WHERE activity_date >= DATE '2026-04-01'
  AND activity_date < DATE '2026-05-01'
  AND activity_flag = TRUE;""",
    },
    {
        "file": "vq-mau-bigquery.sql",
        "vq_id": "vq-mau-bigquery",
        "metric_id": "monthly_active_users",
        "dialect": "bigquery",
        "description": "Verified MAU query for the BigQuery product mart.",
        "referenced_tables": ["prod.product.user_activity_daily"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("BigQuery MAU parity confirmed in the product scorecard review."),
        "tags": ["product", "bigquery"],
        "sql": """SELECT COUNT(DISTINCT user_id) AS monthly_active_users
FROM `prod.product.user_activity_daily`
WHERE activity_date >= DATE '2026-04-01'
  AND activity_date < DATE '2026-05-01'
  AND activity_flag = TRUE;""",
    },
    {
        "file": "vq-ltv-postgres.sql",
        "vq_id": "vq-ltv-postgres",
        "metric_id": "lifetime_value",
        "dialect": "postgres",
        "description": (
            "Verified LTV query using retained-customer revenue from the finance ledger."
        ),
        "referenced_tables": ["prod.finance.mrr_ledger", "prod.growth.customer"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": (
            "Finance review packet parity confirmed for retained-customer LTV."
        ),
        "tags": ["finance", "default"],
        "sql": """SELECT
    SUM(net_revenue_amount) / NULLIF(COUNT(DISTINCT customer_id), 0) AS lifetime_value
FROM prod.finance.mrr_ledger
WHERE customer_status = 'retained'
  AND period_month BETWEEN DATE '2026-01-01' AND DATE '2026-04-01';""",
    },
    {
        "file": "vq-ltv-bigquery.sql",
        "vq_id": "vq-ltv-bigquery",
        "metric_id": "lifetime_value",
        "dialect": "bigquery",
        "description": "Verified LTV query for the BigQuery finance ledger.",
        "referenced_tables": ["prod.finance.mrr_ledger"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": "BigQuery finance packet parity confirmed by FP&A.",
        "tags": ["finance", "bigquery"],
        "sql": """SELECT
    SAFE_DIVIDE(SUM(net_revenue_amount), COUNT(DISTINCT customer_id)) AS lifetime_value
FROM `prod.finance.mrr_ledger`
WHERE customer_status = 'retained'
  AND period_month BETWEEN DATE '2026-01-01' AND DATE '2026-04-01';""",
    },
    {
        "file": "vq-arpu-postgres.sql",
        "vq_id": "vq-arpu-postgres",
        "metric_id": "average_revenue_per_user",
        "dialect": "postgres",
        "description": ("Verified ARPU query over active subscriptions and subscription revenue."),
        "referenced_tables": [
            "prod.finance.mrr_ledger",
            "prod.growth.subscription",
        ],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": "Finance KPI scorecard parity confirmed for ARPU.",
        "tags": ["finance", "default"],
        "sql": """WITH revenue AS (
    SELECT SUM(net_revenue_amount) AS value
    FROM prod.finance.mrr_ledger
    WHERE revenue_type = 'subscription'
      AND period_month = DATE '2026-04-01'
),
subs AS (
    SELECT COUNT(DISTINCT subscription_id) AS value
    FROM prod.growth.subscription
    WHERE status = 'active'
      AND snapshot_date = DATE '2026-04-30'
)
SELECT revenue.value / NULLIF(subs.value, 0) AS average_revenue_per_user
FROM revenue
CROSS JOIN subs;""",
    },
    {
        "file": "vq-arpu-bigquery.sql",
        "vq_id": "vq-arpu-bigquery",
        "metric_id": "average_revenue_per_user",
        "dialect": "bigquery",
        "description": "Verified ARPU query for the BigQuery subscription finance mart.",
        "referenced_tables": [
            "prod.finance.mrr_ledger",
            "prod.growth.subscription",
        ],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("BigQuery ARPU parity confirmed during monthly close review."),
        "tags": ["finance", "bigquery"],
        "sql": """SELECT SAFE_DIVIDE(
  SUM(
    CASE
      WHEN revenue_type = 'subscription' AND period_month = DATE '2026-04-01'
      THEN net_revenue_amount
      ELSE 0
    END
  ),
  COUNT(
    DISTINCT CASE
      WHEN snapshot_date = DATE '2026-04-30' AND status = 'active'
      THEN subscription_id
    END
  )
) AS average_revenue_per_user
FROM `prod.finance.mrr_ledger`
LEFT JOIN `prod.growth.subscription` USING (customer_id);""",
    },
    {
        "file": "vq-nrr-postgres.sql",
        "vq_id": "vq-nrr-postgres",
        "metric_id": "net_revenue_retention",
        "dialect": "postgres",
        "description": "Verified NRR query using the certified recurring revenue ledger.",
        "referenced_tables": ["prod.finance.mrr_ledger"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("Board NRR packet parity confirmed by finance systems."),
        "tags": ["finance", "board"],
        "sql": """WITH starting_mrr AS (
    SELECT SUM(net_revenue_amount) AS value
    FROM prod.finance.mrr_ledger
    WHERE movement_type = 'starting'
      AND period_month = DATE '2026-04-01'
),
ending_mrr AS (
    SELECT SUM(net_revenue_amount) AS value
    FROM prod.finance.mrr_ledger
    WHERE movement_type IN ('starting', 'expansion', 'contraction')
      AND period_month = DATE '2026-04-01'
)
SELECT 100.0 * ending_mrr.value / NULLIF(starting_mrr.value, 0) AS net_revenue_retention
FROM starting_mrr
CROSS JOIN ending_mrr;""",
    },
    {
        "file": "vq-wau-postgres.sql",
        "vq_id": "vq-wau-postgres",
        "metric_id": "weekly_active_users",
        "dialect": "postgres",
        "description": "Verified WAU query over the certified user activity mart.",
        "referenced_tables": ["prod.product.user_activity_daily"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("WAU parity confirmed in the product weekly operations review."),
        "tags": ["product", "weekly"],
        "sql": """SELECT COUNT(DISTINCT user_id) AS weekly_active_users
FROM prod.product.user_activity_daily
WHERE activity_date >= DATE '2026-04-24'
  AND activity_date < DATE '2026-05-01'
  AND activity_flag = TRUE;""",
    },
    {
        "file": "vq-cac-postgres.sql",
        "vq_id": "vq-cac-postgres",
        "metric_id": "customer_acquisition_cost",
        "dialect": "postgres",
        "description": ("Verified CAC query over attributed spend and closed-won accounts."),
        "referenced_tables": [
            "prod.marketing.attribution_touch",
            "prod.sales.opportunity",
        ],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": (
            "CAC review parity confirmed by marketing operations and finance."
        ),
        "tags": ["marketing", "finance"],
        "sql": """WITH spend AS (
    SELECT SUM(spend_amount) AS value
    FROM prod.marketing.attribution_touch
    WHERE attributed_flag = TRUE
      AND spend_date >= DATE '2026-04-01'
      AND spend_date < DATE '2026-05-01'
),
wins AS (
    SELECT COUNT(DISTINCT account_id) AS value
    FROM prod.sales.opportunity
    WHERE stage = 'closed_won'
      AND close_date >= DATE '2026-04-01'
      AND close_date < DATE '2026-05-01'
)
SELECT spend.value / NULLIF(wins.value, 0) AS customer_acquisition_cost
FROM spend
CROSS JOIN wins;""",
    },
    {
        "file": "vq-gross-margin-postgres.sql",
        "vq_id": "vq-gross-margin-postgres",
        "metric_id": "gross_margin",
        "dialect": "postgres",
        "description": "Verified gross-margin query using posted invoice lines.",
        "referenced_tables": ["prod.finance.invoice_line"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("Gross-margin packet parity confirmed during monthly close."),
        "tags": ["finance", "margin"],
        "sql": """SELECT
    100.0 * SUM(gross_profit_amount) / NULLIF(SUM(recognized_revenue_amount), 0)
    AS gross_margin
FROM prod.finance.invoice_line
WHERE invoice_status = 'posted'
  AND revenue_month = DATE '2026-04-01';""",
    },
    {
        "file": "vq-trial-to-paid-postgres.sql",
        "vq_id": "vq-trial-to-paid-postgres",
        "metric_id": "trial_to_paid_conversion_rate",
        "dialect": "postgres",
        "description": ("Verified trial-to-paid conversion query from the certified funnel mart."),
        "referenced_tables": ["prod.product.trial_funnel_daily"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("Growth funnel review parity confirmed for trial conversion."),
        "tags": ["growth", "funnel"],
        "sql": """SELECT 1.0 * COUNT(DISTINCT CASE WHEN converted_flag = TRUE THEN account_id END)
    / NULLIF(COUNT(DISTINCT CASE WHEN trial_started_flag = TRUE THEN account_id END), 0)
    AS trial_to_paid_conversion_rate
FROM prod.product.trial_funnel_daily
WHERE snapshot_month = DATE '2026-04-01';""",
    },
    {
        "file": "vq-mrr-postgres.sql",
        "vq_id": "vq-mrr-postgres",
        "metric_id": "monthly_recurring_revenue",
        "dialect": "postgres",
        "description": "Verified MRR query from the certified recurring revenue ledger.",
        "referenced_tables": ["prod.finance.mrr_ledger"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": ("Finance close packet parity confirmed for month-end MRR."),
        "tags": ["finance", "default"],
        "sql": """SELECT SUM(mrr_amount) AS monthly_recurring_revenue
FROM prod.finance.mrr_ledger
WHERE revenue_type = 'subscription'
  AND period_month = DATE '2026-04-01';""",
    },
    {
        "file": "vq-mrr-bigquery.sql",
        "vq_id": "vq-mrr-bigquery",
        "metric_id": "monthly_recurring_revenue",
        "dialect": "bigquery",
        "description": "Verified MRR query for the BigQuery finance ledger.",
        "referenced_tables": ["prod.finance.mrr_ledger"],
        "verified_by": "reviewer@corp.example",
        "last_verified": "2026-04-15",
        "verification_evidence": (
            "BigQuery month-end MRR parity confirmed during finance reconciliation."
        ),
        "tags": ["finance", "bigquery"],
        "sql": """SELECT SUM(mrr_amount) AS monthly_recurring_revenue
FROM `prod.finance.mrr_ledger`
WHERE revenue_type = 'subscription'
  AND period_month = DATE '2026-04-01';""",
    },
]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _dump_metric(metric: dict[str, Any]) -> str:
    lines = [
        f"metric_id: {metric['metric_id']}",
        f"display_name: {metric['display_name']}",
        f"owner: {metric['owner']}",
        f'definition: "{metric["definition"]}"',
    ]
    synonyms = metric.get("synonyms", [])
    if synonyms:
        lines.append("synonyms:")
        lines.extend(f"  - {item}" for item in synonyms)
    lines.extend(
        [
            f"grain: {metric['grain']}",
            f"unit: {metric['unit']}",
            f"direction: {metric['direction']}",
        ]
    )
    related_metrics = metric.get("related_metrics", [])
    if related_metrics:
        lines.append("related_metrics:")
        lines.extend(f"  - {item}" for item in related_metrics)
    caveats = metric.get("caveats", [])
    if caveats:
        lines.append("caveats:")
        lines.extend(f"  - {item}" for item in caveats)
    verified_query_ids = metric.get("verified_query_ids", [])
    if verified_query_ids:
        lines.append("verified_query_ids:")
        lines.extend(f"  - {item}" for item in verified_query_ids)
    lines.append("calculation:")
    calculation = metric["calculation"]
    numerator = calculation["numerator"]
    lines.extend(
        [
            "  numerator:",
            f"    source: {numerator[0]}",
            f"    filter: {numerator[1]}",
            f"    aggregation: {numerator[2]}",
        ]
    )
    denominator = calculation.get("denominator")
    if denominator is not None:
        lines.extend(
            [
                "  denominator:",
                f"    source: {denominator[0]}",
                f"    filter: {denominator[1]}",
                f"    aggregation: {denominator[2]}",
            ]
        )
    return "\n".join(lines)


def _dump_glossary(
    item: tuple[str, str, str, str, list[str], list[str], list[str], str, str],
) -> tuple[str, str]:
    (
        filename,
        term_id,
        canonical_form,
        definition,
        synonyms,
        abbreviations,
        linked_metric_ids,
        category,
        owner,
    ) = item
    lines = [
        f"term_id: {term_id}",
        f"canonical_form: {canonical_form}",
        f'definition: "{definition}"',
    ]
    if synonyms:
        lines.append("synonyms:")
        lines.extend(f"  - {value}" for value in synonyms)
    if abbreviations:
        lines.append("abbreviations:")
        lines.extend(f"  - {value}" for value in abbreviations)
    if linked_metric_ids:
        lines.append("linked_metric_ids:")
        lines.extend(f"  - {value}" for value in linked_metric_ids)
    lines.extend([f"category: {category}", f"owner: {owner}"])
    return filename, "\n".join(lines)


def _dump_trust(
    item: tuple[str, str, str, str, str, str, int, str, list[dict[str, Any]]],
) -> tuple[str, str]:
    filename, fqtn, grade, owner, description, cadence, staleness, rationale, joins = item
    lines = [
        f"fqtn: {fqtn}",
        f"grade: {grade}",
        f"owner: {owner}",
        f'description: "{description}"',
        "refresh:",
        f"  cadence: {cadence}",
        f"  max_staleness_minutes: {staleness}",
    ]
    if joins:
        lines.append("approved_joins:")
        for join in joins:
            lines.extend(
                [
                    f"  - target_fqtn: {join['target_fqtn']}",
                    "    left_keys:",
                    *[f"      - {value}" for value in join["left_keys"]],
                    "    right_keys:",
                    *[f"      - {value}" for value in join["right_keys"]],
                    f"    join_type: {join['join_type']}",
                    f"    cardinality: {join['cardinality']}",
                ]
            )
    lines.extend([f'grade_rationale: "{rationale}"', "last_audited: 2026-04-15"])
    return filename, "\n".join(lines)


def _dump_verified_query(item: dict[str, Any]) -> tuple[str, str]:
    lines = [
        "---",
        f"vq_id: {item['vq_id']}",
        f"metric_id: {item['metric_id']}",
        f"dialect: {item['dialect']}",
        f"description: {item['description']}",
        "referenced_tables:",
        *[f"  - {table}" for table in item["referenced_tables"]],
        f"verified_by: {item['verified_by']}",
        f"last_verified: {item['last_verified']}",
        f"verification_evidence: {item['verification_evidence']}",
    ]
    failure_modes = item.get("failure_modes", [])
    if failure_modes:
        lines.append("failure_modes:")
        lines.extend(f"  - {value}" for value in failure_modes)
    tags = item.get("tags", [])
    if tags:
        lines.append("tags:")
        lines.extend(f"  - {value}" for value in tags)
    lines.extend(["---", item["sql"]])
    return str(item["file"]), "\n".join(lines)


def _write_pack_yaml(version: str, checksum: str | None = None) -> None:
    lines = [
        "pack_id: domain_pack_enterprise",
        'display_name: "Domain Pack Enterprise"',
        "owner: semantic_platform_team",
        f"version: {version}",
        "requires_semantic_layer_schema_version: 6",
    ]
    if checksum is not None:
        lines.append(f'checksum: "{checksum}"')
    _write_text(PACK_DIR / "pack.yaml", "\n".join(lines))


def main() -> int:
    metrics_dir = PACK_DIR / "metrics"
    glossary_dir = PACK_DIR / "glossary"
    trust_dir = PACK_DIR / "trust"
    verified_dir = PACK_DIR / "verified_queries"

    for metric in METRICS:
        _write_text(metrics_dir / str(metric["file"]), _dump_metric(metric))
    for glossary_item in GLOSSARY:
        filename, payload = _dump_glossary(glossary_item)
        _write_text(glossary_dir / filename, payload)
    for trust_item in TRUST:
        filename, payload = _dump_trust(trust_item)
        _write_text(trust_dir / filename, payload)
    for query in VERIFIED_QUERIES:
        filename, payload = _dump_verified_query(query)
        _write_text(verified_dir / filename, payload)

    _write_pack_yaml("1.1.0")
    checksum = YamlMetricLoader().compute_pack_checksum(PACK_DIR)
    _write_pack_yaml("1.1.0", checksum=checksum)
    print(
        "[refresh_domain_pack_enterprise] ok "
        f"metrics={len(METRICS)} "
        f"glossary={len(GLOSSARY)} "
        f"trust={len(TRUST)} "
        f"verified_queries={len(VERIFIED_QUERIES)} "
        f"checksum={checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
