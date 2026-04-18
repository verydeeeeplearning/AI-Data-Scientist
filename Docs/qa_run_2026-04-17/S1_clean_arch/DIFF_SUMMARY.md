# S1 Clean Architecture - DIFF_SUMMARY

**Stream**: S1 (clean_arch)
**Completed by**: Resume agent (original S1 interrupted after 86 tool uses by Anthropic API 500 error)
**Scope constraints**: No new code modifications beyond what the original S1 had already written. Resume agent only verified and recorded evidence.

## Files Changed by S1 (pre-interruption, confirmed-present)

### Application layer - services (import inversion, existing files)
| File | Change summary |
|---|---|
| `src/ds_agent/application/services/lineage_capture_service.py` | Replaced `from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore` with `from ds_agent.application.ports.lineage_store_port import LineageStorePort`. Service now depends only on the port; concrete adapter is wired at factory.py. Added module-level `get_lineage_service()` / `set_lineage_service()` accessors for composition-root-based wiring. |
| `src/ds_agent/application/services/reproducibility_exporter.py` | Replaced `from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine` with `from ds_agent.application.ports.notebook_engine_port import NotebookEnginePort`. Constructor accepts a `NotebookEnginePort` instance injected by the caller. |
| `src/ds_agent/application/services/scheduler_service.py` | Replaced `from ds_agent.infrastructure.cron_runner import CronRunner` with `from ds_agent.application.ports.cron_runner_port import CronRunnerPort`. Concrete `CronRunner` is injected at factory.py. |

### Application layer - ports (new files)
| File | Change summary |
|---|---|
| `src/ds_agent/application/ports/lineage_store_port.py` | New Protocol `LineageStorePort` (structural) with the methods consumed by `LineageCaptureService`. |
| `src/ds_agent/application/ports/notebook_engine_port.py` | New Protocol `NotebookEnginePort` exposing `build(markdown_blocks, code_blocks)` used by `ReproducibilityExporter`. |
| `src/ds_agent/application/ports/cron_runner_port.py` | New Protocol `CronRunnerPort` for scheduling callbacks; implemented by the concrete `CronRunner` in infrastructure. |

### Composition root (existing file, wiring lines added)
| File | Change summary |
|---|---|
| `src/ds_agent/agent/factory.py` | At `build_agent()` / initialization block (around lines 352-377): imports `SchedulerService`, `set_scheduler_service`, `CronRunner`, `LineageCaptureService`, `set_lineage_service`, `SqliteLineageStore`; constructs `SchedulerService(store=policy_store, cron_runner=CronRunner())` and `LineageCaptureService(SqliteLineageStore())`, then publishes them via the module-level `set_*` accessors. This is the single composition-root location where the application layer is wired to infrastructure adapters. |

### Contracts & CI guards
| File | Change summary |
|---|---|
| `.importlinter` | Added contract `[importlinter:contract:application_independence_from_infrastructure]` (forbidden: `ds_agent.application -> ds_agent.infrastructure`). |
| `scripts/check_import_contracts.py` | Added second `ImportContract` named `application_no_infrastructure` with `source_modules=("ds_agent.application",)` and `forbidden_modules=("ds_agent.infrastructure",)`. |
| `tests/unit/architecture/test_application_infrastructure_boundary.py` | New test file with (1) `test_application_layer_has_no_infrastructure_imports` AST-scanning the entire `src/ds_agent/application/` tree and (2) `test_previously_flagged_services_are_clean` parameterized for the 3 originally flagged services. |

## ReproducibilityExporter wiring status

**Status: DEFERRED WIRING — not currently instantiated at composition root.**

- `grep -rn ReproducibilityExporter src/` returns only the class definition in
  `src/ds_agent/application/services/reproducibility_exporter.py:13`. The class
  is not constructed anywhere in `src/` today.
- The only existing instantiation lives in tests:
  `tests/unit/application/test_reproducibility.py:31` and `:53` —
  `ReproducibilityExporter(log, NotebookEngine())` — which already passes the
  concrete `NotebookEngine` where a `NotebookEnginePort` is expected (Protocol
  = structural subtyping, so this is correct with zero further changes).
- Because no composition-root site constructs this exporter yet, there is
  nothing to wire. Per Resume scope constraints ("스코프 밖 리팩터 금지" /
  "새 코드 수정 금지 unless 기존 배선 지점이 있고 타입 mismatch가 난 경우"),
  the Resume agent did **not** add a new construction site.
- When a CLI tool, API route, or hook eventually instantiates
  `ReproducibilityExporter`, the injector must construct and pass
  `NotebookEngine()` (from `ds_agent.infrastructure.artifact.notebook_engine`)
  as the second argument.

## Minor fixes made by Resume agent

**None.** The Resume agent made no code modifications. It only executed
verification commands and wrote evidence documents.
