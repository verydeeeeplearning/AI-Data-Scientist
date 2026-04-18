---
vq_id: vq-wau-postgres
metric_id: weekly_active_users
dialect: postgres
description: Verified WAU query over the certified user activity mart.
referenced_tables:
  - prod.product.user_activity_daily
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: WAU parity confirmed in the product weekly operations review.
tags:
  - product
  - weekly
---
SELECT COUNT(DISTINCT user_id) AS weekly_active_users
FROM prod.product.user_activity_daily
WHERE activity_date >= DATE '2026-04-24'
  AND activity_date < DATE '2026-05-01'
  AND activity_flag = TRUE;
