---
vq_id: vq-mrr-bigquery
metric_id: monthly_recurring_revenue
dialect: bigquery
description: Verified MRR query for the BigQuery finance ledger.
referenced_tables:
  - prod.finance.mrr_ledger
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: BigQuery month-end MRR parity confirmed during finance reconciliation.
tags:
  - finance
  - bigquery
---
SELECT SUM(mrr_amount) AS monthly_recurring_revenue
FROM `prod.finance.mrr_ledger`
WHERE revenue_type = 'subscription'
  AND period_month = DATE '2026-04-01';
