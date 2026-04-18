---
vq_id: vq-mrr-postgres
metric_id: monthly_recurring_revenue
dialect: postgres
description: Verified MRR query from the certified recurring revenue ledger.
referenced_tables:
  - prod.finance.mrr_ledger
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Finance close packet parity confirmed for month-end MRR.
tags:
  - finance
  - default
---
SELECT SUM(mrr_amount) AS monthly_recurring_revenue
FROM prod.finance.mrr_ledger
WHERE revenue_type = 'subscription'
  AND period_month = DATE '2026-04-01';
