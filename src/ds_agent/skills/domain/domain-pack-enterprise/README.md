# Domain Pack Enterprise

This built-in semantic pack seeds the current DoD baseline across:

- `metrics/`
- `glossary/`
- `trust/`
- `verified_queries/`

Current seed coverage:

- `10` metrics
- `30` glossary terms
- `20` table-trust records
- `15` verified queries

Use it to validate the semantic pack loader, checksum flow, operator dry-run/apply path,
and downstream semantic-query grounding for core SaaS KPI workflows (`churn`, `MAU`,
`LTV`, `MRR`, `NRR`, `ARPU`, `CAC`).

If the pack assets change, refresh the checksum with:

```bash
python scripts/refresh_domain_pack_enterprise.py
```
