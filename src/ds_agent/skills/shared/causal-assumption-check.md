---
name: causal-assumption-check
description: Validate core assumptions before claiming causal effects
category: best_practice
tags: [causal, uplift, assumptions, sutva, overlap]
version: "1.0.0"
author: builtin
token_estimate: 520
related_skills: [evaluation, reporting]
---

# Causal Assumption Check

- Verify SUTVA: one unit's treatment should not affect another unit's outcome.
- Check overlap: treated and untreated groups need comparable support.
- Check unconfoundedness or document why the identification strategy compensates for it.
- State remaining threats explicitly in the report.
