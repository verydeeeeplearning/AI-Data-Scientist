---
vq_id: vq-arpu-bigquery
metric_id: average_revenue_per_user
dialect: bigquery
description: Verified ARPU query for the BigQuery subscription finance mart.
referenced_tables:
  - prod.finance.mrr_ledger
  - prod.growth.subscription
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: BigQuery ARPU parity confirmed during monthly close review.
tags:
  - finance
  - bigquery
---
SELECT SAFE_DIVIDE(
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
LEFT JOIN `prod.growth.subscription` USING (customer_id);
