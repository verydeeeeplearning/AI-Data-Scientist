---
name: retrain-vs-rollback
description: Operational decision guide for retraining, rollback, or watchful waiting
category: best_practice
tags: [operations, remediation, retrain, rollback, monitoring]
version: "1.0.0"
author: builtin
token_estimate: 500
related_skills: [evaluation, reporting]
---

# Retrain vs Rollback

## Decision Tree
- If performance dropped by more than 10%, rollback first and investigate.
- If PSI is above 0.2, recommend retraining and open an urgent alert.
- If PSI is between 0.1 and 0.2 with a meaningful metric drop, retrain on fresh data.
- If movement is within noise bands, keep normal monitoring and gather more evidence.

## Evidence to Record
- Reference metric and latest metric.
- Drift score and top drifting features.
- Known upstream schema or data-quality changes.
- Business impact and operator follow-up.

## Guardrails
- Treat retraining as a recommendation unless a policy explicitly enables full automation.
- Always preserve the last known-good model before swapping artifacts.
