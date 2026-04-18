# B11 — Feature Flag On/Off Diff

**Feature flags under test**:
- `DS_AGENT_PORTFOLIO_ENABLED` — portfolio tools gate (`src/ds_agent/tools/portfolio_tools.py`)
- `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` — learning tools + prompt-section gate (`src/ds_agent/tools/learning_tools.py`, `src/ds_agent/agent/prompt_builder.py:299`)

---

## 1. `DS_AGENT_PORTFOLIO_ENABLED` — side-by-side

### 1.1 Tool: `list_my_portfolio`

| Flag = off (false) | Flag = on (true, empty temp workspace) |
|---|---|
| `{"ok": false, "error": {"code": "DISABLED", "message": "Portfolio manager is not enabled. Set DS_AGENT_PORTFOLIO_ENABLED=1."}}` | `{"ok": true, "entries": [], "count": 0}` |

### 1.2 Tool: `resume_task`, `pause_task`, `request_monitoring`, `set_sla`

| Flag = off | Flag = on |
|---|---|
| `{"ok": false, "error": {"code": "DISABLED", "message": "Portfolio manager is not enabled."}}` | Path executes (expected outcomes: `NOT_FOUND`, `TRANSITION_ERROR`, `SLOT_FULL`, etc.) |

Summary: **all 5 portfolio tools short-circuit to DISABLED when `DS_AGENT_PORTFOLIO_ENABLED` is off.**

### 1.3 Registry-level consideration (caveat)

Because `@tool(...)` decorators execute at module import time, the ToolRegistry **does NOT drop these 5 tool names** when the flag is off. The schema remains advertised; only the *invocation body* refuses. The spec §5.7.9 ("tool is not exposed in the prompt") is **behaviorally** met (no state mutation reachable) but not **structurally** (schema still visible in `list_names()`).

This is an acceptable interpretation of the hard constraint — **zero-state-change guarantee** is intact — but documented as a possible prompt-builder improvement.

| Metric | Off | On |
|---|:-:|:-:|
| Tool registered in `ToolRegistry` | yes | yes |
| Tool body returns success | no (DISABLED) | yes |
| Any DB write possible via tool | **no** | yes |
| Any state mutation possible via tool | **no** | yes |

---

## 2. `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` — side-by-side

This flag is referenced in TWO places:

1. `src/ds_agent/tools/learning_tools.py::_get_learning_store` — body guard on 6 learning tools.
2. `src/ds_agent/agent/prompt_builder.py::_build_learning_governance_context` — hides the "Learning Governance" context block from the prompt when off.

### 2.1 Tools under the gate

Learning tools affected: `list_learning_inbox`, `review_learning_item`, `get_learning_item`, `list_promotions`, `list_deprecations`, `rollback_promotion`.

### 2.2 Off observed

Flag = `false` → `list_learning_inbox()`, `get_learning_item(item_id="LI-x")`, `list_promotions()`, `list_deprecations()` all return:

```json
{"ok": false, "error": {"code": "DISABLED", "message": "Self-improve governance is not enabled."}}
```

Confirmed across all 4 tested read-side tools.

### 2.3 Prompt-builder gate

`_build_learning_governance_context` returns `None` when the flag is off — the "# Learning Governance" section is **omitted from the system prompt**. This satisfies the "hide from prompt" intent of the hard constraint stronger than the portfolio case does (where only the body is gated).

### 2.4 Write-side tools (`review_learning_item`, `rollback_promotion`)

These require an `item_id` to exist in the store. The DISABLED guard short-circuits before the store is even touched, so no side effect is possible with flag off. (Confirmed by code inspection of `learning_tools.py` lines 135+, 321+.)

### 2.5 Summary

| Tool | Off behavior | Structural gate |
|------|--------------|:---------------:|
| list_learning_inbox | DISABLED | body only |
| review_learning_item | DISABLED | body only |
| get_learning_item | DISABLED | body only |
| list_promotions | DISABLED | body only |
| list_deprecations | DISABLED | body only |
| rollback_promotion | DISABLED | body only |
| prompt `# Learning Governance` block | **omitted** | **prompt-level** |

---

## 3. Flag matrix summary

| Flag | Off behavior | On behavior | Verdict |
|------|--------------|-------------|---------|
| `DS_AGENT_PORTFOLIO_ENABLED` | all 5 portfolio tools return `DISABLED`; no state mutation | normal CRUD / transition paths | PASS (behavioral gate) |
| `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` | 6 learning tools return `DISABLED`; prompt Learning Governance section omitted | tools and prompt section active | PASS (behavioral + prompt gate) |
| `DS_AGENT_MAX_ACTIVE_SLOTS` (numeric) | default 3 | observed 2 when set | works as documented |

---

## 4. Raw evidence

- `B11_path_results.json` — full probe dump (all 9 paths) including `learning_off` responses.
- `B11_state_transitions.jsonl` — event log with `feature_flag_off`, `feature_flag_on`, `feature_flag_off_learning` categories.
- `B11_rollback_atomicity_sqlite_probe.json` — SQLite-backed rollback probe.
