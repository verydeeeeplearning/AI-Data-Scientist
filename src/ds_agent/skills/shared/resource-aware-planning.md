---
name: resource-aware-planning
description: Choose the right execution strategy before touching large datasets
category: best_practice
tags: [resources, planning, sampling, chunking, distributed]
version: "1.0.0"
author: builtin
token_estimate: 430
related_skills: [data-profiling]
---

# Resource-Aware Planning

- Check dataset size, row count, available memory, and CPU before full processing.
- Prototype on a representative sample when memory pressure is high.
- Switch to chunked or distributed execution when the full dataset does not fit comfortably.
- Preserve the exact sampling rule so prototype and production runs stay comparable.
