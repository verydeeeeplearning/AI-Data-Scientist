---
vq_id: vq-trial-to-paid-postgres
metric_id: trial_to_paid_conversion_rate
dialect: postgres
description: Verified trial-to-paid conversion query from the certified funnel mart.
referenced_tables:
  - prod.product.trial_funnel_daily
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Growth funnel review parity confirmed for trial conversion.
tags:
  - growth
  - funnel
---
SELECT 1.0 * COUNT(DISTINCT CASE WHEN converted_flag = TRUE THEN account_id END)
    / NULLIF(COUNT(DISTINCT CASE WHEN trial_started_flag = TRUE THEN account_id END), 0)
    AS trial_to_paid_conversion_rate
FROM prod.product.trial_funnel_daily
WHERE snapshot_month = DATE '2026-04-01';
