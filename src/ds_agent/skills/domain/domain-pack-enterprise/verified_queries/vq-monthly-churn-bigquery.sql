---
vq_id: vq-monthly-churn-bigquery
metric_id: monthly_churn_rate
dialect: bigquery
description: Verified monthly churn query for the certified BigQuery growth mart.
referenced_tables:
  - prod.growth.subscription
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: BigQuery parity confirmed against the growth operating review.
tags:
  - growth
  - bigquery
---
WITH month_window AS (
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
FROM `prod.growth.subscription`;
