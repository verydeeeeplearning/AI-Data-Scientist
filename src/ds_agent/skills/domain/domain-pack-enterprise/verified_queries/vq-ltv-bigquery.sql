---
vq_id: vq-ltv-bigquery
metric_id: lifetime_value
dialect: bigquery
description: Verified LTV query for the BigQuery finance ledger.
referenced_tables:
  - prod.finance.mrr_ledger
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: BigQuery finance packet parity confirmed by FP&A.
tags:
  - finance
  - bigquery
---
SELECT
    SAFE_DIVIDE(SUM(net_revenue_amount), COUNT(DISTINCT customer_id)) AS lifetime_value
FROM `prod.finance.mrr_ledger`
WHERE customer_status = 'retained'
  AND period_month BETWEEN DATE '2026-01-01' AND DATE '2026-04-01';
