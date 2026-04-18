---
vq_id: vq-arpu-postgres
metric_id: average_revenue_per_user
dialect: postgres
description: Verified ARPU query over active subscriptions and subscription revenue.
referenced_tables:
  - prod.finance.mrr_ledger
  - prod.growth.subscription
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Finance KPI scorecard parity confirmed for ARPU.
tags:
  - finance
  - default
---
WITH revenue AS (
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
CROSS JOIN subs;
