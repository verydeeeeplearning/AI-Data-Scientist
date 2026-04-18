# B06 Failure Repros

**Status**: empty directory — **0 critical failures** across 430 cells.

If any cell in `B06_tools_fuzz.csv` had `outcome=fail`, the harness
(`.tmp/qa_B06/run_fuzz.py`) writes a standalone reproducer here named
`<tool>_<input_type>.py`. Run with:

```bash
python Docs/qa_run_2026-04-17/B06_tools_registry/B06_failures/<file>.py
```

Each repro is self-contained — it imports `ds_agent.agent.factory.import_all_tools`
plus the learning/portfolio modules, then calls `ToolRegistry.dispatch` with the
exact arguments that produced the failure.
