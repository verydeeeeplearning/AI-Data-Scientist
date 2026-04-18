---
vq_id: vq-monthly-churn-postgres
metric_id: monthly_churn_rate
dialect: postgres
description: Verified monthly churn query for active subscriptions.
referenced_tables:
  - prod.growth.subscription
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Dashboard parity confirmed against finance KPI scorecard.
failure_modes:
  - Promo cohorts inflate churn when not filtered separately.
tags:
  - default
  - scorecard
---
WITH month_window AS (
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
CROSS JOIN denominator;
