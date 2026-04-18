# Phase 05: Autonomous Coordinator + Sensor Hub

**Priority**: P1  
**Milestone**: C  
**Status**: Completed  
**Implemented On**: 2026-04-12

---

## 1. Goal

Introduce the first real sensor-driven autonomy layer on top of the existing
`DSAgent.run()` loop.

This phase was meant to move the system from pure user-triggered execution to a
runtime that can wake itself up, observe an event, and decide whether to act.

---

## 2. Implemented

### 2.1 Shared sensor hub

New files:

- `src/ds_agent/runtime/sensor_hub.py`

Implemented:

- `SensorEvent` as the common runtime event record
- `SensorHub` as the shared async queue for wake-up events
- queue backlog tracking for operator/runtime status

### 2.2 First coordinator loop

New files:

- `src/ds_agent/runtime/coordinator.py`

Implemented:

- `AutonomousCoordinator` background loop
- event intake from the shared `SensorHub`
- dispatch throttling via cooldown keys
- first dispatch policy:
  - `file.created`
  - `file.updated`
  - optional `schedule.tick` when explicitly marked dispatchable
- autonomous prompt synthesis while continuing to reuse `DSAgent.run()` as the
  action executor

### 2.3 Three initial sensors

New files:

- `src/ds_agent/runtime/sensors/__init__.py`
- `src/ds_agent/runtime/sensors/user_input.py`
- `src/ds_agent/runtime/sensors/file_watch.py`
- `src/ds_agent/runtime/sensors/schedule.py`

Implemented:

- `UserInputSensor`
  - records foreground input as sensor events for shared runtime observability
- `FileWatchSensor`
  - polls a dedicated autonomous inbox and emits `file.created` / `file.updated`
  - uses `workspace/inbox` to avoid feedback loops from general workspace writes
- `ScheduleSensor`
  - emits low-frequency periodic ticks
  - dispatch is disabled by default to avoid noisy autonomous runs

### 2.4 Background runtime daemon

New files:

- `src/ds_agent/gateway/daemon.py`

Modified files:

- `pyproject.toml`

Implemented:

- `AutonomousDaemon` runtime owner
- `AutonomousCallbacks` for low-noise background run execution
- `ds-agent-daemon` CLI entrypoint
- autonomous runtime startup that wires:
  - sensor hub
  - coordinator
  - inbox file watch sensor
  - schedule sensor

### 2.5 App integration hooks

Modified files:

- `src/ds_agent/config/schema.py`
- `src/ds_agent/api/routes/config.py`
- `src/ds_agent/api/app.py`
- `src/ds_agent/api/ws_handler.py`

Implemented:

- new config flag: `gateway.autonomous_runtime_enabled`
- FastAPI lifespan now starts/stops the background runtime when enabled
- WebSocket `config.set` can start or stop the background runtime without a
  process restart
- workspace changes restart the background runtime so the inbox watch path is
  rebound to the new workspace
- status payload now includes:
  - `autonomousRuntimeEnabled`
  - `autonomousRuntimeRunning`
  - `sensorBacklog`
- foreground WebSocket user input is mirrored into the shared sensor hub

---

## 3. Runtime Behavior

The first autonomous path now works like this:

1. Background runtime is enabled
2. A new file is placed into `workspace/inbox`
3. `FileWatchSensor` emits a `file.created` event
4. `AutonomousCoordinator` receives it
5. The coordinator dispatches an autonomous run through the existing
   `AppState.start_run(...)`
6. `DSAgent.run()` performs the actual reasoning and tool execution

This is the first non-user-triggered execution path in the repo.

---

## 4. Changed Files

New files:

- `src/ds_agent/runtime/sensor_hub.py`
- `src/ds_agent/runtime/coordinator.py`
- `src/ds_agent/runtime/sensors/__init__.py`
- `src/ds_agent/runtime/sensors/user_input.py`
- `src/ds_agent/runtime/sensors/file_watch.py`
- `src/ds_agent/runtime/sensors/schedule.py`
- `src/ds_agent/gateway/daemon.py`
- `tests/unit/infrastructure/test_autonomous_runtime.py`

Modified files:

- `src/ds_agent/config/schema.py`
- `src/ds_agent/api/routes/config.py`
- `src/ds_agent/api/app.py`
- `src/ds_agent/api/ws_handler.py`
- `tests/unit/infrastructure/test_api.py`
- `pyproject.toml`

---

## 5. Verification

Executed:

```bash
python -m pytest tests/unit/infrastructure/test_autonomous_runtime.py \
  tests/unit/infrastructure/test_api.py \
  tests/unit/infrastructure/test_approval_bus.py \
  tests/unit/infrastructure/test_telegram_runner.py \
  tests/integration/test_runtime_wiring.py \
  tests/e2e/test_ws_e2e.py \
  -q -p no:cacheprovider \
  --basetemp="C:\Users\aquap\.codex\memories\pytest_phase05_run2"
```

Result:

- `112 passed`

Additional verification:

- `python -m ruff check ...` passed for the changed Python files
- `python -m ruff format --check ...` passed for the changed Python files
- `mypy` was not executed because the current environment does not have the
  module installed

---

## 6. Notes

Important implementation decisions:

- autonomy is scoped to `workspace/inbox`, not the entire workspace
  - this avoids self-trigger loops from agent-generated artifacts
- the coordinator decides *whether* to run
  - `DSAgent.run()` still performs the real reasoning/action loop
- schedule ticks exist now, but do not dispatch by default
  - this keeps the first coordinator pass conservative

This is the right first step for an autonomous runtime because it adds
observation and wake-up behavior without replacing the existing agent core.

---

## 7. Remaining Gap

Still deferred after this phase:

- richer dispatch policy based on active goals and blocked state
- persisted sensor/event ledger across process restarts
- Telegram process sharing the same in-memory run/task registry
- higher-level planner arbitration across multiple concurrent goals
- startup recovery that resumes unfinished autonomous work automatically

Those belong to the later operator-console and recovery phases.
