---
name: domain-pack-enterprise
description: Enterprise semantic metric pack authoring and import workflow
category: best_practice
tags: [semantic-memory, enterprise, metric-pack, governance]
version: "1.0.0"
author: builtin
token_estimate: 420
tools: [skill_view, load_semantic_pack, semantic_query]
---

# Domain Pack Enterprise

- Use this pack when an organization provides canonical KPI definitions that must be loaded into semantic memory before analysis.
- Run `load_semantic_pack` with `skill_name="domain-pack-enterprise"` for a dry run first.
- Review adds, updates, and conflicts before applying the pack.
- After import, use `semantic_query` instead of raw SQL for KPI questions.
