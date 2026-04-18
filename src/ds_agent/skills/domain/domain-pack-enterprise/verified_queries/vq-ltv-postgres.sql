---
vq_id: vq-ltv-postgres
metric_id: lifetime_value
dialect: postgres
description: Verified LTV query using retained-customer revenue from the finance ledger.
referenced_tables:
  - prod.finance.mrr_ledger
  - prod.growth.customer
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Finance review packet parity confirmed for retained-customer LTV.
tags:
  - finance
  - default
---
SELECT
    SUM(net_revenue_amount) / NULLIF(COUNT(DISTINCT customer_id), 0) AS lifetime_value
FROM prod.finance.mrr_ledger
WHERE customer_status = 'retained'
  AND period_month BETWEEN DATE '2026-01-01' AND DATE '2026-04-01';
