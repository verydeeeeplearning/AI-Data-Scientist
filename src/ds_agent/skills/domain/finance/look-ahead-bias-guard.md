---
name: look-ahead-bias-guard
description: Finance-specific leakage checks for future information and label timing
category: best_practice
tags: [finance, leakage, look-ahead, temporal]
version: "1.0.0"
author: builtin
token_estimate: 480
related_skills: [financial-ts-modeling]
---

# Look-Ahead Bias Guard

- Reject features derived from future prices, future labels, or post-event rules.
- Check feature timestamps against label timestamps before training.
- Avoid random splits for market data with temporal dependency.
