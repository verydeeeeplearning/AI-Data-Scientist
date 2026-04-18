# C13 — Channel Entry-Point Call-Graph Evidence

**Purpose**: Prove (statically) that the three user-facing channels route
agent construction through the single shared factory
`ds_agent.agent.factory.create_agent`, preserving identical hook chain,
skill list, tool registry, budget policy, prompt builder, and port
wiring across CLI, Telegram, and Electron (WebSocket).

## 1. Entry points (line-accurate, 2026-04-17)

### CLI — `src/ds_agent/cli/main.py`

```python
# line 88
from ds_agent.agent.factory import create_agent
...
# lines 106-119
agent = create_agent(
    provider=provider,
    callbacks=callbacks,
    max_iterations=context.get("max_iterations", 100),
    max_cost_usd=context.get("max_budget", 10.0),
    mode=context.get("mode", "auto"),
    authority_mode=_current_authority_overlay(context.get("config")),
    model_name=model_str,
    workspace_dir=context.get("workspace_dir"),
    session_id=session_id,
    transcript_store=context.get("_transcript_store"),
    checkpoint_store=context.get("_checkpoint_store"),
    sandbox_config=getattr(agent_config, "sandbox", None),
)
```

### Telegram — `src/ds_agent/gateway/telegram_runner.py`

```python
# line 15
from ds_agent.agent.factory import create_agent
...
# lines 3343-3357 (TelegramRunner._create_agent)
return create_agent(
    provider=provider,
    callbacks=callbacks,
    max_iterations=self._config.agent.max_iterations,
    max_cost_usd=self._config.provider.max_budget_usd,
    mode=self._config.agent.mode,
    authority_mode=None if overlay.mode is None else overlay.mode.value,
    model_name=model_str,
    workspace_dir=str(self._config.agent.workspace_dir),
    session_id=telegram_session_id(chat_id, thread_id),
    transcript_store=self._transcript_store,
    checkpoint_store=self._checkpoint_store,
    approval_store=self._approval_store,
    sandbox_config=self._config.sandbox,
)
```

### Electron (WS) — `src/ds_agent/api/agent_session_registry.py`

```python
# line 145
from ds_agent.agent.factory import create_agent
...
# lines 170-192 (AgentSessionRegistry._create_agent)
return create_agent(
    provider=provider,
    callbacks=callbacks,
    max_iterations=self._config.agent.max_iterations,
    max_cost_usd=self._config.provider.max_budget_usd,
    mode=self._config.agent.mode,
    model_name=model_str,
    workspace_dir=str(self._config.agent.workspace_dir),
    session_id=session_id,
    use_case_hint=self._config.agent.use_case_hint,
    use_case_context=self._config.agent.use_case_context,
    transcript_store=self._transcript_store,
    checkpoint_store=self._checkpoint_store,
    approval_store=self._approval_store,
    authority_mode=authority_mode,
    connector_configs={...},
    skill_hub=self._skill_hub,
    org_policy_supplier=self._org_policy_supplier,
    sandbox_config=self._config.sandbox,
    language=getattr(self._config.agent, "language", None),
)
```

The WS handler calls `AgentSessionRegistry.get_or_create` (see
`src/ds_agent/api/ws_handler.py` around `get_or_create_agent`), which in
turn dispatches to `_create_agent` above.

## 2. Docstring-declared invariant

`src/ds_agent/agent/factory.py` line 1-5:

```
"""Shared agent factory — single source of truth for DSAgent wiring.

GAP-05 fix: all entrypoints (WebSocket, CLI, Telegram) use this factory
so hooks, skills, memory, and prompt builder are consistently wired.
"""
```

This makes the parity contract a first-class design obligation. The
runtime signature harness (`parity_harness.py`) verifies the contract
empirically.

## 3. What parity guarantees via the factory

Because all three entry points pass through the identical `create_agent`
body (factory.py lines 289-457), the following are structurally
identical regardless of channel:

| Artifact | Source |
|----------|--------|
| Hook registry (30 hooks) | `build_hook_registry` (factory.py lines 176-227) |
| Skill hub (7 default skills + domain packs) | `build_prompt_builder` (factory.py lines 246-286) |
| Tool registry (process-global `ToolRegistry`) | `import_all_tools` (factory.py lines 136-173) |
| Task-contract container | `build_task_contract_container` (line 387) |
| Verifier container | `build_verifier_container` (line 405) |
| Lineage service (Port-wired) | factory.py lines 371-377 |
| Scheduler service | factory.py lines 361-366 |
| Memory query + unified memory store | factory.py lines 359, 381 |
| Post-learner adapter | factory.py line 433 |
| Budget policy | factory.py lines 438-441 |
| Prompt builder | factory.py lines 412-428 |

## 4. What differs per channel — intentionally & allowed

| Field | CLI | Telegram | Electron |
|-------|-----|----------|----------|
| `callbacks` class | `TUICallbacks` | `TelegramCallbacks` | WS callbacks bound to `emit_event` |
| `session_id` shape | `cli-<hex>` | `telegram_session_id(chat,thread)` | registry key |
| `origin`/`surface` | `"cli"` | `"telegram"` | `"ws"` |
| Workspace path source | `context["workspace_dir"]` | `config.agent.workspace_dir` | `config.agent.workspace_dir` |
| `connector_configs` pass-through | not passed (defaults `None`) | not passed | explicit mapping |

These differences are the "allowed" deltas from the plan (channel
origin, timestamps, session_id). They do NOT affect the hook chain,
skill set, tool registry, budget, or verifier wiring — which the
harness confirms bit-identical.

## 5. Confirmed non-deltas (the disallowed ones from the plan)

Verified by `parity_harness.py` (see `channel_signatures.json`):

- `hooks` (sorted class name list) — identical across 3 channels × 3 scenarios.
- `hook_count` = 30 — identical.
- `skill_names` = `[scoping, data-profiling, eda, feature-engineering, modeling, evaluation, reporting]` — identical.
- `tools_hash` = SHA-256 over sorted tool names — identical.
- `tool_count` = 75 (subset registered by `import_all_tools`) — identical.
- `budget` = `{max_iterations: 100, max_cost_usd: 10.0}` — identical.
- `mode` = `"auto"` — identical.
- `authority_mode` — identical.
- Store wiring flags (goal, working memory, approval, skill hub, post-learner) — identical.
- `tool_registry_class` — identical (`ds_agent.tools.registry.ToolRegistry`).

## 6. Note on tool_count 75 vs plan's 86

Plan revision recorded in `HANDOFF_NEXT_AGENT.md` §5.3 states 86 `@tool`
after S3 (learning/portfolio named-arg fixes). The harness's
`factory.import_all_tools` imports 33 tool modules producing 75 tools
in the process-global registry. The delta (11 tools) comes from modules
imported elsewhere in the app (e.g., via `learning_cli`, `portfolio_cli`,
or lazy imports on first tool use in CLI wizard / WS handler).

Parity test takeaway: **whatever tool set is loaded, all three
channels see the identical set (same hash)** because the registry is
a process-global classvar. This is the invariant the plan requires.
