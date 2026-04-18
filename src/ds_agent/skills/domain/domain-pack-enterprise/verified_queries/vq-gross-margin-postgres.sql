---
vq_id: vq-gross-margin-postgres
metric_id: gross_margin
dialect: postgres
description: Verified gross-margin query using posted invoice lines.
referenced_tables:
  - prod.finance.invoice_line
verified_by: reviewer@corp.example
last_verified: 2026-04-15
verification_evidence: Gross-margin packet parity confirmed during monthly close.
tags:
  - finance
  - margin
---
SELECT
    100.0 * SUM(gross_profit_amount) / NULLIF(SUM(recognized_revenue_amount), 0)
    AS gross_margin
FROM prod.finance.invoice_line
WHERE invoice_status = 'posted'
  AND revenue_month = DATE '2026-04-01';
