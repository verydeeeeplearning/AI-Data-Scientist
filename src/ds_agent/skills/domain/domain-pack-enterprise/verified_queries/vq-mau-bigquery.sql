---
vq_id: vq-mau-bigquery
metric_id: monthly_active_users
dialect: bigquery
description: Verified MAU query for the BigQuery product mart.
referenced_tables:
  - prod.product.user_activity_daily
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: BigQuery MAU parity confirmed in the product scorecard review.
tags:
  - product
  - bigquery
---
SELECT COUNT(DISTINCT user_id) AS monthly_active_users
FROM `prod.product.user_activity_daily`
WHERE activity_date >= DATE '2026-04-01'
  AND activity_date < DATE '2026-05-01'
  AND activity_flag = TRUE;
