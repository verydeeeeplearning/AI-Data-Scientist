---
name: financial-ts-modeling
description: Finance-specific time-series modeling playbook
category: best_practice
tags: [finance, forecasting, walk-forward, regime]
version: "1.0.0"
author: builtin
token_estimate: 650
related_skills: [backtesting, look-ahead-bias-guard]
---

# Financial Time-Series Modeling

- Walk-forward validation is mandatory for financial time-series tasks.
- Check regime changes explicitly and compare performance by market regime.
- Benchmark against naive and risk-adjusted baselines, not just raw return.
- Treat suspiciously strong single-feature performance as a leakage signal.
