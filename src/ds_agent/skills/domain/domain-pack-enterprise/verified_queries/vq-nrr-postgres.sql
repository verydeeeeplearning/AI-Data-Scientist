---
vq_id: vq-nrr-postgres
metric_id: net_revenue_retention
dialect: postgres
description: Verified NRR query using the certified recurring revenue ledger.
referenced_tables:
  - prod.finance.mrr_ledger
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Board NRR packet parity confirmed by finance systems.
tags:
  - finance
  - board
---
WITH starting_mrr AS (
    SELECT SUM(net_revenue_amount) AS value
    FROM prod.finance.mrr_ledger
    WHERE movement_type = 'starting'
      AND period_month = DATE '2026-04-01'
),
ending_mrr AS (
    SELECT SUM(net_revenue_amount) AS value
    FROM prod.finance.mrr_ledger
    WHERE movement_type IN ('starting', 'expansion', 'contraction')
      AND period_month = DATE '2026-04-01'
)
SELECT 100.0 * ending_mrr.value / NULLIF(starting_mrr.value, 0) AS net_revenue_retention
FROM starting_mrr
CROSS JOIN ending_mrr;
