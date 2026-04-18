---
vq_id: vq-cac-postgres
metric_id: customer_acquisition_cost
dialect: postgres
description: Verified CAC query over attributed spend and closed-won accounts.
referenced_tables:
  - prod.marketing.attribution_touch
  - prod.sales.opportunity
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: CAC review parity confirmed by marketing operations and finance.
tags:
  - marketing
  - finance
---
WITH spend AS (
    SELECT SUM(spend_amount) AS value
    FROM prod.marketing.attribution_touch
    WHERE attributed_flag = TRUE
      AND spend_date >= DATE '2026-04-01'
      AND spend_date < DATE '2026-05-01'
),
wins AS (
    SELECT COUNT(DISTINCT account_id) AS value
    FROM prod.sales.opportunity
    WHERE stage = 'closed_won'
      AND close_date >= DATE '2026-04-01'
      AND close_date < DATE '2026-05-01'
)
SELECT spend.value / NULLIF(wins.value, 0) AS customer_acquisition_cost
FROM spend
CROSS JOIN wins;
