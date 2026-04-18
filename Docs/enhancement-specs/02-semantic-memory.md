# Enhancement Spec 02 — Enterprise Semantic Memory

본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §2 "Enterprise Semantic Memory — 조직 의미론 grounding" 항목을 구현 착수 가능한 수준으로 상세화한 설계 명세다. 기존 `domain_kb` (자유 형식 insight 저장소) 를 **조직이 공인한 의미론적 기억 레이어**로 승격시키기 위한 5개 신규 컴포넌트 (MetricCatalog / BusinessGlossary / DataTrustRegistry / VerifiedQueryStore / OrgContextStore) 도입, `semantic_query` 도구 설계, 외부 metric layer 연동 로드맵, Electron/CLI UX, TDD 기반 구현 순서를 모두 포함한다.

중요한 점은 이것이 정적 사전 구축 프로젝트가 아니라는 것이다. 자율형 Agent 는 계획 전에 semantic memory 를 읽고, 실행 중 semantic policy 를 따르며, 실행 후에는 새 alias / verified query / failure lesson 을 **제안(proposal)** 형태로 write-back 하고, 사람 승인 후 조직 기억으로 승격시켜야 한다.

---

## 문서 업데이트 메모 (2026-04-16)

- semantic memory 를 "정적 catalog" 가 아니라 "agent read/write loop" 로 재정의
- `SemanticProposal` 모델과 proposal queue / approval flow 추가
- `SemanticReadGuardHook`, `SemanticTrustHook`, `SemanticWritebackHook` 등 harness-level 강제 지점 명시
- `TaskContract` / runtime context 기반 metric re-ranking 규칙 추가
- ApprovalInbox / Telegram operator / self-improve / `domain_kb` 공존 전략 반영
- 구현 phase / 테스트 / DoD / 리스크 / open question 을 자율형 agent 관점으로 보강

### 구현 반영 상태 (2026-04-16)

- Phase 1 선행 착수 완료: `src/ds_agent/memory/semantic/` 패키지 생성
- 추가 완료:
  - domain models: `metric.py`, `glossary.py`, `trust.py`, `verified_query.py`, `org_context.py`, `proposal.py`
  - application port: `application/ports.py`
  - package exports / normalizer helper
- 테스트 추가 완료:
  - `tests/unit/domain/test_semantic_metric.py`
  - `tests/unit/domain/test_semantic_glossary.py`
  - `tests/unit/domain/test_semantic_trust.py`
  - `tests/unit/domain/test_semantic_verified_query.py`
  - `tests/unit/domain/test_semantic_org_context.py`
  - `tests/unit/domain/test_semantic_proposal.py`
  - `tests/unit/application/test_semantic_ports.py`
- 검증 결과:
  - `pytest` 대상 15개 테스트 통과
  - `ruff check` 통과
  - `mypy` 는 현재 셸 환경에 설치되어 있지 않아 미실행

---

### Implementation Update (2026-04-16, Session 2)

- Completed Phase 2 persistence layer: SQLite migration v6, FTS/triggers, and six repositories for metric, glossary, trust, verified query, org context, and proposal storage.
- Completed Phase 3 application layer: `resolve_metric.py`, `lookup_term.py`, `find_verified_query.py`, `check_table_trust.py`, `submit_semantic_proposal.py`, `review_semantic_proposal.py`, `apply_semantic_proposal.py`, `record_negative_knowledge.py`, and `src/ds_agent/infrastructure/semantic_memory_container.py`.
- Installed `mypy` in the active environment with `python -m pip install "mypy>=1.10.0"`.
- Hardened implementation details:
  - metric resolution now uses typed `MetricGrain` / literal match-kind boundaries.
  - verified query binding now supports whitespace placeholders such as `{{ start_date }}`.
  - negative-knowledge proposals now include `recorded_at`, so later apply flow passes domain validation.
  - trust repository `bulk_get()` now accepts `Sequence[str]`, matching the application port contract.
- Added tests:
  - unit domain/application coverage for semantic entities, ports, metric resolution, verified query binding, trust decision, proposal submission/review/apply, and negative-knowledge capture.
  - integration coverage for migration v6 and all SQLite semantic repositories.
- Validation status:
  - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/integration/semantic -q` -> `37 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/integration/semantic` -> passed
  - `python -m mypy src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py` -> passed

### Implementation Update (2026-04-16, Session 3)

- Started Phase 4 tool integration with semantic entry tools:
  - `src/ds_agent/tools/semantic_query.py`
  - `src/ds_agent/tools/lookup_term.py`
  - `src/ds_agent/tools/describe_table_trust.py`
  - shared runtime helper `src/ds_agent/tools/_semantic_common.py`
- `semantic_query` now resolves metrics, prefers verified SQL, falls back to metric-synthesized SQL, evaluates trust policy, and returns calendar / negative-knowledge caveats plus a shared `next_action`.
- `lookup_term` exposes glossary retrieval for acronym / business-term grounding.
- `describe_table_trust` exposes table trust grading and execution policy warnings before SQL use.
- Wired tool self-registration into `src/ds_agent/agent/factory.py` and updated registration coverage in `tests/integration/test_all_tools_registered.py` and `tests/integration/test_registry_with_tools.py`.
- Added integration coverage in `tests/integration/tools/test_semantic_query.py` for verified semantic query path, glossary lookup path, and trust-policy path.
- Validation status:
  - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/integration/semantic tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py -q` -> `53 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/factory.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/integration/semantic tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/factory.py` -> passed

### Implementation Update (2026-04-16, Session 4)

- Added `src/ds_agent/agent/semantic_hooks.py` with `SemanticReadGuardHook`.
- Wired `SemanticReadGuardHook` into `build_hook_registry()` ahead of `QueryCostGuardHook`, so metric-like requests that jump straight to `sql_query` now emit a harness warning unless `semantic_query` or `lookup_term` has already grounded the session.
- The read guard also appends a semantic warning banner to the `sql_query` tool result, so the model sees the policy miss and can self-correct on the next step.
- Added hook coverage in `tests/unit/application/test_semantic_hooks.py` and updated runtime wiring expectations in `tests/integration/test_runtime_wiring.py`.
- Validation status:
  - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/integration/semantic tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py -q` -> `71 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/agent/factory.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/integration/semantic tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/agent/factory.py` -> passed

### Implementation Update (2026-04-16, Session 5)

- Continued Phase 4 integration in two remaining areas:
  - prompt-side semantic context summarization via `src/ds_agent/memory/semantic/prompt_hints.py`
  - SQL pre-execution trust escalation via `SemanticTrustHook` in `src/ds_agent/agent/semantic_hooks.py`
- Added `src/ds_agent/infrastructure/semantic_memory_runtime.py` as the shared runtime resolver for the active semantic-memory container and canonical semantic DB path, so tools and hooks point at the same store.
- `_build_memory_hints()` in `src/ds_agent/agent/factory.py` now attempts to append semantic prompt hints alongside legacy `domain_kb` hints and cross-session hints.
- `SemanticTrustHook` now:
  - extracts referenced tables from `sql_query`
  - evaluates semantic trust policy before execution
  - emits caveat warnings for silver-grade usage
  - creates approval-store escalation for confirm/block cases and emits `approval.requested` / `semantic.trust_escalation`
- Added/expanded tests:
  - `tests/unit/application/test_semantic_prompt_hints.py`
  - `tests/unit/application/test_semantic_hooks.py`
  - `tests/unit/application/test_agent_factory.py`
  - `tests/integration/test_sql_integration.py`
  - `tests/integration/test_runtime_wiring.py`
- Validation status after shell recovery:
  - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/unit/application/test_semantic_prompt_hints.py tests/unit/application/test_agent_factory.py tests/integration/semantic tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py -q` -> `86 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/infrastructure/semantic_memory_runtime.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/agent/factory.py tests/unit/application/test_semantic_prompt_hints.py tests/unit/application/test_semantic_hooks.py tests/unit/application/test_agent_factory.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py tests/integration/tools/test_semantic_query.py tests/integration/semantic` -> passed
  - `python -m mypy src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/infrastructure/semantic_memory_runtime.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/agent/factory.py` -> passed

### Implementation Update (2026-04-16, Session 6)

- Continued the remaining Phase 4 write-back path with `SemanticWritebackHook` in `src/ds_agent/agent/semantic_hooks.py`.
- `SemanticWritebackHook` now watches successful `run_verifier` tool results and consumes optional `artifacts.semantic_candidates` payloads from the verifier call.
- The hook currently materializes conservative proposal candidates by:
  - requiring verifier result `pass` or `warn`
  - requiring dashboard parity evidence for `verified_query` candidates (`parity_confirmed`, parity-tagged evidence refs, or parity text in `verification_evidence`)
  - validating proposal payloads against semantic domain models before persistence
  - submitting candidates through `submit_semantic_proposal`
  - emitting `semantic.proposal.created` / `semantic.proposal.deduplicated`
  - injecting `semantic_writeback` / `semantic_writeback_warnings` back into the verifier tool JSON result so the agent can see proposal outcomes immediately
- Registered `SemanticWritebackHook` in `src/ds_agent/agent/factory.py`; runtime hook count is now 29.
- Added test coverage:
  - `tests/unit/application/test_semantic_hooks.py`
  - `tests/integration/semantic/test_semantic_writeback_hook.py`
  - updated `tests/integration/test_runtime_wiring.py`
- Current blocker:
  - shell execution became unstable again during validation. At the time of this update, even trivial commands were timing out, so Session 6 verification is code-complete but command verification is pending.

### Implementation Update (2026-04-16, Session 7)

- Continued Phase 5 runtime/operator integration by wiring semantic proposals into the existing approval bus.
- Extended approval payload/state surfaces so approvals can carry typed semantic metadata:
  - `src/ds_agent/domain/entities/approval.py`
  - `src/ds_agent/runtime/approval_store.py`
  - `src/ds_agent/runtime/approval_payloads.py`
  - `src/ds_agent/api/event_schemas.py`
  - `electron/src/renderer/types/events.ts`
  - `electron/src/renderer/stores/workflowStore.ts`
- Added `src/ds_agent/runtime/semantic_proposal_router.py`:
  - creates approval-bus entries for newly created semantic proposals
  - resolves semantic proposal approvals into review/apply use cases against the canonical semantic DB
- `SemanticWritebackHook` now requests operator review for newly created proposals by:
  - creating `kind="semantic_proposal"` approval requests
  - attaching proposal metadata (`proposalId`, `proposalType`, `targetId`, `risk`, `confidence`, `autoApplyEligible`)
  - emitting `approval.requested` with the enriched payload
- `AppState.resolve_approval()` in `src/ds_agent/api/ws_handler.py` now detects semantic approvals and:
  - maps `approved` to semantic proposal review
  - maps `approved + response=apply` to review + apply
  - maps `rejected` to semantic proposal rejection
  - persists the semantic proposal outcome back into approval metadata
  - records runtime events (`semantic.proposal.reviewed` / `semantic.proposal.applied`)
- Updated Electron operator surface in `electron/src/renderer/components/workflow/ApprovalPanel.tsx` so semantic approvals display proposal type / target / risk instead of only a generic question string.
- Added/expanded tests:
  - `tests/unit/infrastructure/test_approval_bus.py`
  - `tests/unit/application/test_semantic_hooks.py`
  - `tests/integration/runtime/test_semantic_proposal_approval.py`
  - `tests/integration/test_runtime_wiring.py`
- Validation status:
  - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/unit/application/test_semantic_prompt_hints.py tests/unit/application/test_agent_factory.py tests/unit/infrastructure/test_approval_bus.py tests/integration/semantic tests/integration/runtime/test_semantic_proposal_approval.py tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py -q` -> `94 passed`
  - `ruff check src/ds_agent/domain/entities/approval.py src/ds_agent/runtime/approval_store.py src/ds_agent/runtime/approval_payloads.py src/ds_agent/runtime/semantic_proposal_router.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/api/event_schemas.py src/ds_agent/api/ws_handler.py src/ds_agent/tools/user_interaction.py tests/unit/application/test_semantic_hooks.py tests/unit/infrastructure/test_approval_bus.py tests/integration/semantic/test_semantic_writeback_hook.py tests/integration/runtime/test_semantic_proposal_approval.py tests/integration/test_runtime_wiring.py` -> passed
  - `python -m mypy src/ds_agent/domain/entities/approval.py src/ds_agent/runtime/approval_store.py src/ds_agent/runtime/approval_payloads.py src/ds_agent/runtime/semantic_proposal_router.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/tools/user_interaction.py` -> passed
  - `npm --prefix electron run typecheck` -> passed

### Implementation Update (2026-04-16, Session 8)

- Started the domain-pack ingestion side of Phase 5 with a typed metric-pack loader:
  - `src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py`
  - `scripts/validate_metrics.py`
- `YamlMetricLoader` currently supports:
  - `pack.yaml` loading
  - `requires_semantic_layer_schema_version` validation against schema v6
  - recursive `metrics/*.yaml` / `metrics/*.yml` discovery
  - typed `Metric` validation
  - duplicate `metric_id` rejection across files
- Exported the loader via `src/ds_agent/memory/semantic/infrastructure/__init__.py` so later pack import use cases can reuse the same entrypoint.
- Added tests:
  - `tests/unit/infrastructure/test_yaml_metric_loader.py`
- Validation status:
  - `pytest tests/unit/infrastructure/test_yaml_metric_loader.py -q` -> `3 passed`
  - `ruff check src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py scripts/validate_metrics.py tests/unit/infrastructure/test_yaml_metric_loader.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py` -> passed
  - broader semantic/runtime regression:
    - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/unit/application/test_semantic_prompt_hints.py tests/unit/application/test_agent_factory.py tests/unit/infrastructure/test_approval_bus.py tests/unit/infrastructure/test_yaml_metric_loader.py tests/integration/semantic tests/integration/runtime/test_semantic_proposal_approval.py tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py -q` -> `97 passed`

### Implementation Update (2026-04-16, Session 9)

- Continued Phase 5 pack-ingestion work by turning the loader into an operator-visible import surface.
- Added `LoadSemanticPackUseCase` and DTOs:
  - `src/ds_agent/memory/semantic/application/load_semantic_pack.py`
  - `src/ds_agent/memory/semantic/application/dtos.py`
- `src/ds_agent/infrastructure/semantic_memory_container.py` now wires `load_semantic_pack` so the semantic container can dry-run or apply metric packs against the canonical SQLite store.
- Hardened `YamlMetricLoader` with canonical pack checksums:
  - `checksum: "sha256:..."` in `pack.yaml` is now validated
  - `compute_pack_checksum()` provides the canonical digest for authoring / CI / validation scripts
  - `scripts/validate_metrics.py` now prints the effective checksum alongside schema-version validation
- Added the first built-in semantic pack skill/example under:
  - `src/ds_agent/skills/domain/domain-pack-enterprise/`
  - includes `SKILL.md`, `pack.yaml`, and `metrics/monthly_churn_rate.yaml`
- Added `src/ds_agent/tools/load_semantic_pack.py`:
  - supports `pack_dir` for workspace-local pack imports
  - supports `skill_name` for built-in semantic pack directories such as `domain-pack-enterprise`
  - returns dry-run diffs or applies approved metric updates into semantic memory
- Registered the new tool in the runtime/tool surfaces:
  - `src/ds_agent/agent/factory.py`
  - `src/ds_agent/application/services/execution_router.py`
  - `tests/integration/test_all_tools_registered.py`
  - `tests/integration/test_registry_with_tools.py`
- Added tests:
  - `tests/unit/application/test_load_semantic_pack.py`
  - `tests/unit/infrastructure/test_yaml_metric_loader.py`
  - `tests/integration/semantic/test_load_semantic_pack.py`
  - `tests/integration/skills/test_load_semantic_pack_skill_tool.py`
- Validation status:
  - `pytest tests/unit/infrastructure/test_yaml_metric_loader.py tests/unit/application/test_load_semantic_pack.py tests/integration/semantic/test_load_semantic_pack.py tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py -q` -> `25 passed`
  - broader semantic/runtime regression:
    - `pytest tests/unit/domain/test_semantic_metric.py tests/unit/domain/test_semantic_glossary.py tests/unit/domain/test_semantic_trust.py tests/unit/domain/test_semantic_verified_query.py tests/unit/domain/test_semantic_org_context.py tests/unit/domain/test_semantic_proposal.py tests/unit/application/test_semantic_ports.py tests/unit/application/test_resolve_metric.py tests/unit/application/test_find_verified_query.py tests/unit/application/test_check_table_trust.py tests/unit/application/test_submit_semantic_proposal.py tests/unit/application/test_review_semantic_proposal.py tests/unit/application/test_record_negative_knowledge.py tests/unit/application/test_apply_semantic_proposal.py tests/unit/application/test_semantic_hooks.py tests/unit/application/test_semantic_prompt_hints.py tests/unit/application/test_agent_factory.py tests/unit/application/test_load_semantic_pack.py tests/unit/infrastructure/test_approval_bus.py tests/unit/infrastructure/test_yaml_metric_loader.py tests/integration/semantic tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/integration/runtime/test_semantic_proposal_approval.py tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py -q` -> `106 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/infrastructure/semantic_memory_runtime.py src/ds_agent/tools/_semantic_common.py src/ds_agent/tools/lookup_term.py src/ds_agent/tools/describe_table_trust.py src/ds_agent/tools/semantic_query.py src/ds_agent/tools/load_semantic_pack.py src/ds_agent/agent/semantic_hooks.py src/ds_agent/agent/factory.py src/ds_agent/application/services/execution_router.py scripts/validate_metrics.py tests/unit/application/test_load_semantic_pack.py tests/unit/infrastructure/test_yaml_metric_loader.py tests/integration/semantic tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/integration/tools/test_semantic_query.py tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/integration/test_runtime_wiring.py tests/integration/test_sql_integration.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py src/ds_agent/memory/semantic/application/load_semantic_pack.py src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/tools/load_semantic_pack.py` -> passed
    - `python scripts/validate_metrics.py src/ds_agent/skills/domain/domain-pack-enterprise` -> passed

### Implementation Update (2026-04-16, Session 10)

- Confirmed the plan scope already includes the next requested work:
  - pack schema expansion from metric-only into `metrics/`, `glossary/`, `trust/`, `verified_queries/`
  - CLI `semantic` surface and semantic pack load/apply flow
  - RPC surface for semantic lookup / trust / verified query / pack load
- Expanded semantic pack ingestion beyond metric-only:
  - `src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py`
  - `src/ds_agent/memory/semantic/application/load_semantic_pack.py`
  - `src/ds_agent/memory/semantic/application/dtos.py`
  - `src/ds_agent/memory/semantic/infrastructure/pack_paths.py`
  - loader now validates and loads glossary terms, table trust records, and verified queries in addition to metrics
  - pack reference validation now checks:
    - glossary `linked_metric_ids`
    - metric `verified_query_ids`
    - verified query `metric_id`
- Opened the CLI surface for semantic-memory operator workflows:
  - `src/ds_agent/cli/semantic_cli.py`
  - `src/ds_agent/cli/main.py`
  - added `ds-agent semantic lookup`, `trust`, `verified-query`, `load-pack`
  - `load-pack` supports both workspace `--pack-dir` and built-in `--skill-name`
- Opened the WebSocket RPC surface for semantic-memory operator/runtime workflows:
  - `src/ds_agent/api/ws_handler.py`
  - added:
    - `semantic.lookupMetric`
    - `semantic.getTrust`
    - `semantic.getVerifiedQuery`
    - `semantic.loadPack`
  - `AppState` now lazily builds and caches the semantic container, and refreshes it when `agent.workspace_dir` changes
- Expanded the built-in example pack from metric-only into a full semantic pack:
  - `src/ds_agent/skills/domain/domain-pack-enterprise/pack.yaml`
  - `src/ds_agent/skills/domain/domain-pack-enterprise/README.md`
  - `src/ds_agent/skills/domain/domain-pack-enterprise/glossary/churn.yaml`
  - `src/ds_agent/skills/domain/domain-pack-enterprise/trust/prod.growth.subscription.yaml`
  - `src/ds_agent/skills/domain/domain-pack-enterprise/verified_queries/vq-monthly-churn-postgres.sql`
  - recomputed canonical checksum after the new artifact set landed
- Added/updated tests:
  - `tests/unit/infrastructure/test_yaml_metric_loader.py`
  - `tests/unit/application/test_load_semantic_pack.py`
  - `tests/integration/semantic/test_load_semantic_pack.py`
  - `tests/integration/skills/test_load_semantic_pack_skill_tool.py`
  - `tests/unit/infrastructure/test_semantic_cli.py`
  - `tests/unit/infrastructure/test_cli_main.py`
  - `tests/unit/infrastructure/test_api.py`
- Validation status:
  - `pytest tests/unit/infrastructure/test_yaml_metric_loader.py tests/unit/application/test_load_semantic_pack.py tests/integration/semantic/test_load_semantic_pack.py tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py -q` -> `43 passed`
  - `pytest tests/unit/infrastructure/test_yaml_metric_loader.py tests/unit/application/test_load_semantic_pack.py tests/integration/semantic/test_load_semantic_pack.py tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py tests/unit/infrastructure/test_api.py -k semantic -q` -> `16 passed`
  - `ruff check src/ds_agent/memory/semantic src/ds_agent/memory/semantic/infrastructure/pack_paths.py src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/main.py src/ds_agent/tools/load_semantic_pack.py src/ds_agent/infrastructure/semantic_memory_container.py scripts/validate_metrics.py src/ds_agent/api/ws_handler.py tests/unit/infrastructure/test_yaml_metric_loader.py tests/unit/application/test_load_semantic_pack.py tests/integration/semantic/test_load_semantic_pack.py tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py src/ds_agent/memory/semantic/infrastructure/pack_paths.py src/ds_agent/memory/semantic/application/load_semantic_pack.py src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/tools/load_semantic_pack.py` -> passed
  - `python scripts/validate_metrics.py src/ds_agent/skills/domain/domain-pack-enterprise` -> passed

### Implementation Update (2026-04-16, Session 11)

- Continued the CLI/operator surface track by opening semantic proposal review commands in the existing `ds-agent semantic` namespace.
- Added `src/ds_agent/cli/semantic_proposal_cli.py`:
  - `ds-agent semantic proposal list`
  - `ds-agent semantic proposal show`
  - `ds-agent semantic proposal approve`
  - `ds-agent semantic proposal reject`
  - `ds-agent semantic proposal apply`
- `src/ds_agent/cli/semantic_cli.py` now routes `proposal ...` subcommands into the dedicated proposal CLI helper.
- The CLI proposal surface reuses the same approval-bus semantics as Electron / WebSocket:
  - pending semantic approvals resolve through `JsonApprovalStore`
  - approval decisions fan into semantic review/apply logic
  - proposal outcomes are written back into approval metadata as `semanticProposalOutcome`
- Proposal CLI intentionally points at the runtime semantic DB path via `resolve_semantic_db_path(...)`, because autonomous semantic writeback currently persists proposals into the runtime-scoped semantic store.
- Added coverage in:
  - `tests/unit/infrastructure/test_semantic_cli.py`
    - pending proposal list rendering
    - reject flow
    - approve -> apply flow with glossary materialization
  - existing semantic approval round-trip coverage remained green:
    - `tests/integration/runtime/test_semantic_proposal_approval.py`
- Validation status:
  - `pytest tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py tests/integration/runtime/test_semantic_proposal_approval.py -q` -> `33 passed`
  - `ruff check src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py src/ds_agent/runtime/semantic_proposal_router.py` -> passed
  - `python -m mypy src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py src/ds_agent/runtime/semantic_proposal_router.py` -> passed

### Implementation Update (2026-04-16, Session 12)

- Closed the semantic DB path split between runtime proposal flows and CLI/RPC lookup flows.
- Added shared path resolution in:
  - `src/ds_agent/infrastructure/semantic_memory_paths.py`
- The new resolver now uses:
  - canonical runtime semantic DB path first
  - workspace legacy fallback (`<workspace>/semantic/semantic_memory.db`)
  - older Decision OS fallback (`<workspace>/data/memory/semantic/semantic_memory.db`)
  - canonical runtime path when no prior DB exists
- Wired the shared resolver into:
  - `src/ds_agent/infrastructure/semantic_memory_container.py`
  - `src/ds_agent/infrastructure/semantic_memory_runtime.py`
  - `src/ds_agent/infrastructure/decision_os_container.py`
- Result:
  - `ds-agent semantic lookup|trust|verified-query|load-pack`
  - `ds-agent semantic proposal ...`
  - WebSocket semantic RPC methods
  - Decision OS semantic metric-direction reads
  now resolve through the same semantic DB path policy instead of splitting workspace-vs-runtime storage.
- Added regression coverage:
  - `tests/unit/infrastructure/test_semantic_memory_paths.py`
  - `tests/unit/infrastructure/test_semantic_cli.py`
    - explicit runtime semantic DB seed is now visible to default CLI lookup flow
  - `tests/unit/infrastructure/test_api.py`
    - explicit runtime semantic DB seed is now visible to `semantic.lookupMetric`
- Validation status:
  - `pytest tests/unit/infrastructure/test_semantic_memory_paths.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py -k semantic -q` -> `15 passed`
  - `ruff check src/ds_agent/infrastructure/semantic_memory_paths.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/infrastructure/semantic_memory_runtime.py src/ds_agent/infrastructure/decision_os_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py tests/unit/infrastructure/test_semantic_memory_paths.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/infrastructure/semantic_memory_paths.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/infrastructure/semantic_memory_runtime.py src/ds_agent/infrastructure/decision_os_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py` -> passed

### Implementation Update (2026-04-16, Session 13)

- Extended the CLI semantic proposal surface from single-item review into operator-friendly filtered and batch review flows.
- Updated `src/ds_agent/cli/semantic_proposal_cli.py`:
  - list filters now support:
    - `--approval-status` / legacy `--status`
    - `--proposal-status`
    - `--proposal-type`
    - `--risk`
    - `--session-id`
    - `--limit`
  - added batch commands:
    - `ds-agent semantic proposal approve-many`
    - `ds-agent semantic proposal reject-many`
    - `ds-agent semantic proposal apply-many`
  - batch commands reuse the same approval-bus / proposal-review path as single approve/reject/apply commands
  - list and batch views now include filter summaries in the rendered table title so operators can see the active inbox slice they are acting on
- Test fixture coverage expanded in `tests/unit/infrastructure/test_semantic_cli.py`:
  - filtered list by proposal type + risk
  - filtered `approve-many`
  - filtered `apply-many`
  - existing single reject / approve+apply flows remain green
- Validation status:
  - `pytest tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_cli_main.py tests/unit/infrastructure/test_semantic_memory_paths.py tests/unit/infrastructure/test_api.py -k semantic -q` -> `19 passed`
  - `ruff check src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_semantic_memory_paths.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/semantic_proposal_cli.py src/ds_agent/infrastructure/semantic_memory_paths.py` -> passed

### Implementation Update (2026-04-16, Session 14)

- Started Phase 6 external semantic adapter work with a reusable sync use case:
  - added `src/ds_agent/memory/semantic/application/sync_semantic_source.py`
  - added sync DTOs to `src/ds_agent/memory/semantic/application/dtos.py`
  - `SyncSemanticSourceUseCase` now:
    - fetches metrics / table trust / verified queries from one `ExternalSemanticSource`
    - applies optional namespace prefixes to external metric / verified-query IDs
    - enforces `SemanticSyncPolicy` merge behavior (`overwrite`, `allowed_grades`)
    - skips verified-query imports when the referenced metric is missing
    - supports dry-run vs apply result reporting with per-artifact diffs
- Added the first external adapters under `src/ds_agent/memory/semantic/infrastructure/adapters/`:
  - `postgres_schema_adapter.py`
    - reuses the existing warehouse connector stack
    - imports Postgres schema metadata as default `silver` `TableTrust`
    - maps warehouse columns into semantic `ColumnTrust` and infers low-risk PII columns by name
  - `dbt_metricflow_adapter.py`
    - fetches GraphQL metric payloads from a dbt Semantic Layer / MetricFlow endpoint
    - maps dbt metric metadata into semantic `Metric` records with owner / grain / unit / caveat heuristics
- Wired the new sync path into the semantic composition/runtime surfaces:
  - `src/ds_agent/infrastructure/semantic_memory_container.py` now exposes `sync_semantic_source`
  - `src/ds_agent/cli/semantic_cli.py` now supports:
    - `ds-agent semantic sync postgres --connector ...`
    - `ds-agent semantic sync dbt --endpoint ...`
  - `src/ds_agent/cli/main.py` now passes loaded config into the semantic CLI so connector-backed sync can reuse saved connector definitions
  - `src/ds_agent/api/ws_handler.py` now exposes `semantic.syncSource`
- Added validation coverage for Phase 6 paths:
  - `tests/unit/application/test_sync_semantic_source.py`
  - `tests/unit/infrastructure/test_postgres_schema_adapter.py`
  - `tests/unit/infrastructure/test_dbt_metricflow_adapter.py`
  - `tests/integration/application/test_sync_semantic_source.py`
  - extended `tests/unit/infrastructure/test_semantic_cli.py`
  - extended `tests/unit/infrastructure/test_api.py`
- Validation status:
  - `pytest tests/unit/application/test_sync_semantic_source.py tests/unit/infrastructure/test_postgres_schema_adapter.py tests/unit/infrastructure/test_dbt_metricflow_adapter.py tests/integration/application/test_sync_semantic_source.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py -k "semantic or sync or dbt or postgres" -q` -> `98 passed`
  - `pytest tests/unit/infrastructure/test_cli_main.py -q` -> `27 passed`
  - `pytest tests/unit/infrastructure/test_api.py -k "semantic_sync_source_postgres or semantic_lookup_metric or semantic_load_pack" -q` -> `4 passed`
  - `ruff check src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/cli/main.py src/ds_agent/api/ws_handler.py tests/unit/application/test_sync_semantic_source.py tests/unit/infrastructure/test_postgres_schema_adapter.py tests/unit/infrastructure/test_dbt_metricflow_adapter.py tests/integration/application/test_sync_semantic_source.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py` -> passed

### Implementation Update (2026-04-16, Session 15)

- Continued Phase 6 P1 adapter expansion by adding warehouse-schema sync support for the remaining connector families:
  - `src/ds_agent/memory/semantic/infrastructure/adapters/warehouse_schema_adapter_base.py`
  - `src/ds_agent/memory/semantic/infrastructure/adapters/bigquery_schema_adapter.py`
  - `src/ds_agent/memory/semantic/infrastructure/adapters/snowflake_schema_adapter.py`
- Refactored `postgres_schema_adapter.py` onto the shared warehouse-schema base so Postgres / BigQuery / Snowflake now share:
  - schema include/exclude filtering
  - silver-grade `TableTrust` auto-seed behavior
  - `ColumnTrust` generation with low-risk PII inference
  - default refresh SLA handling
- Expanded operator surfaces so external sync now supports all implemented warehouse connectors:
  - `ds-agent semantic sync bigquery --connector ...`
  - `ds-agent semantic sync snowflake --connector ...`
  - `semantic.syncSource` RPC now accepts `sourceKind=bigquery|snowflake` in addition to `postgres|dbt`
- Updated adapter exports in `src/ds_agent/memory/semantic/infrastructure/__init__.py` and `src/ds_agent/memory/semantic/infrastructure/adapters/__init__.py`.
- Added validation coverage for the new connector families:
  - `tests/unit/infrastructure/test_bigquery_schema_adapter.py`
  - `tests/unit/infrastructure/test_snowflake_schema_adapter.py`
  - extended `tests/unit/infrastructure/test_semantic_cli.py` with BigQuery sync
  - extended `tests/unit/infrastructure/test_api.py` with Snowflake sync RPC
- Validation status:
  - `pytest tests/unit/infrastructure/test_postgres_schema_adapter.py tests/unit/infrastructure/test_bigquery_schema_adapter.py tests/unit/infrastructure/test_snowflake_schema_adapter.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py -k "semantic_sync_source or schema_adapter or bigquery or snowflake or postgres" -q` -> `13 passed`
  - `pytest tests/unit/infrastructure/test_cli_main.py -q` -> `27 passed`
  - `pytest tests/unit/infrastructure/test_api.py -k "semantic_sync_source_postgres or semantic_sync_source_snowflake" -q` -> `2 passed`
  - `ruff check src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/memory/semantic/infrastructure/__init__.py src/ds_agent/cli/semantic_cli.py src/ds_agent/api/ws_handler.py tests/unit/infrastructure/test_postgres_schema_adapter.py tests/unit/infrastructure/test_bigquery_schema_adapter.py tests/unit/infrastructure/test_snowflake_schema_adapter.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/memory/semantic/infrastructure/__init__.py src/ds_agent/cli/semantic_cli.py` -> passed

### Implementation Update (2026-04-16, Session 16)

- Implemented Phase 6 rollback/snapshot support for reversible semantic mutations:
  - added snapshot schema v7 in `src/ds_agent/memory/semantic/infrastructure/sqlite_base.py`
  - added `SqliteSemanticSnapshotRepository` export + restore logic in `src/ds_agent/memory/semantic/infrastructure/sqlite_snapshot_repo.py`
  - added `ListSemanticSnapshotsUseCase` and `RestoreSemanticSnapshotUseCase`
- Wired snapshots into the semantic container and mutation paths:
  - `LoadSemanticPackUseCase` now creates a pre-apply snapshot and returns `snapshot_id`
  - `SyncSemanticSourceUseCase` now creates a pre-sync snapshot and returns `snapshot_id`
  - `build_semantic_memory_container()` now exposes `snapshots`, `list_semantic_snapshots`, `restore_semantic_snapshot`
- Expanded operator surfaces for snapshot control:
  - CLI: `ds-agent semantic snapshot list`, `ds-agent semantic snapshot restore <snapshot_id>`
  - RPC: `semantic.listSnapshots`, `semantic.restoreSnapshot`
  - `semantic.loadPack` / `semantic.syncSource` payloads now include `snapshot_id` on apply paths
- Fixed a latent SQLite FTS trigger issue uncovered by rollback testing:
  - corrected metric/glossary FTS trigger behavior so delete/update and snapshot restore no longer fail on `SQL logic error`
  - restore flow now clears FTS virtual tables explicitly before base-row replay to avoid rowid collisions
- Added validation coverage for reversible apply / restore:
  - `tests/unit/infrastructure/test_semantic_snapshot_repo.py`
  - extended `tests/unit/application/test_load_semantic_pack.py` with snapshot creation coverage
  - extended `tests/unit/application/test_sync_semantic_source.py` with snapshot creation coverage
  - extended `tests/unit/infrastructure/test_semantic_cli.py` with snapshot list/restore coverage
  - extended `tests/unit/infrastructure/test_api.py` with snapshot RPC coverage
- Validation status:
  - `pytest tests/unit/application/test_load_semantic_pack.py tests/unit/application/test_sync_semantic_source.py tests/unit/infrastructure/test_semantic_snapshot_repo.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py -k "semantic or snapshot" -q` -> `31 passed`
  - `pytest tests/unit/infrastructure/test_cli_main.py -q` -> `27 passed`
  - `ruff check src/ds_agent/memory/semantic/application/load_semantic_pack.py src/ds_agent/memory/semantic/application/list_semantic_snapshots.py src/ds_agent/memory/semantic/application/restore_semantic_snapshot.py src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/infrastructure/sqlite_base.py src/ds_agent/memory/semantic/infrastructure/sqlite_snapshot_repo.py src/ds_agent/memory/semantic/infrastructure/__init__.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/api/ws_handler.py tests/unit/application/test_load_semantic_pack.py tests/unit/application/test_sync_semantic_source.py tests/unit/infrastructure/test_semantic_snapshot_repo.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/application/load_semantic_pack.py src/ds_agent/memory/semantic/application/list_semantic_snapshots.py src/ds_agent/memory/semantic/application/restore_semantic_snapshot.py src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/infrastructure/sqlite_base.py src/ds_agent/memory/semantic/infrastructure/sqlite_snapshot_repo.py src/ds_agent/memory/semantic/infrastructure/__init__.py src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py` -> passed

### Implementation Update (2026-04-16, Session 17)

- Continued Phase 6 higher-order semantic sync expansion with remote semantic adapters and glossary-aware merges:
  - added `src/ds_agent/memory/semantic/infrastructure/adapters/unity_catalog_adapter.py`
  - added `src/ds_agent/memory/semantic/infrastructure/adapters/looker_adapter.py`
  - expanded `SyncSemanticSourceUseCase` so external sync now evaluates and applies `GlossaryTerm` payloads alongside metrics / trust / verified queries
- Extended sync DTO / port contracts for richer external semantic imports:
  - `SyncSemanticSourceResultDTO` now returns `glossary_diffs` and `applied_glossary_term_ids`
  - `ExternalSemanticSource` now includes `fetch_glossary_terms()`
  - glossary-linked metrics are now validated against canonical storage or same-sync imported metrics before apply
- Expanded external adapter behavior:
  - `UnityCatalogAdapter` imports Databricks-style table metadata into `TableTrust`, including:
    - explicit grade/tag parsing when available
    - lineage-based gold/silver/bronze inference
    - column lineage + refresh metadata mapping
  - `LookerAdapter` imports Looker metadata into:
    - `Metric` records for measure fields
    - `GlossaryTerm` records for measure/dimension fields
    - `VerifiedQuery` records for saved Looks with SQL payloads
- Brought CLI / RPC parity up to the new adapter surface:
  - CLI now supports:
    - `ds-agent semantic sync unity-catalog --endpoint ...`
    - `ds-agent semantic sync looker --endpoint ...`
  - `semantic.syncSource` RPC now accepts `sourceKind=unity_catalog|unity-catalog|looker`
  - RPC remote sync now applies the same default namespaces as CLI (`dbt:`, `unity:`, `looker:`) when `idNamespace` is omitted
- Added validation coverage for the new Phase 6 paths:
  - new `tests/unit/infrastructure/test_unity_catalog_adapter.py`
  - new `tests/unit/infrastructure/test_looker_adapter.py`
  - extended `tests/unit/application/test_sync_semantic_source.py`
  - extended `tests/integration/application/test_sync_semantic_source.py`
  - extended `tests/unit/infrastructure/test_semantic_cli.py`
  - extended `tests/unit/infrastructure/test_api.py`
- Validation status:
  - `pytest tests/unit/application/test_sync_semantic_source.py tests/integration/application/test_sync_semantic_source.py tests/unit/infrastructure/test_unity_catalog_adapter.py tests/unit/infrastructure/test_looker_adapter.py tests/unit/infrastructure/test_dbt_metricflow_adapter.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py -k "semantic or sync or looker or unity or dbt" -q` -> `114 passed, 25 deselected`
  - `pytest tests/unit/infrastructure/test_cli_main.py -q` -> `27 passed`
  - `ruff check src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/memory/semantic/application/ports.py src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py src/ds_agent/api/ws_handler.py tests/unit/application/test_sync_semantic_source.py tests/integration/application/test_sync_semantic_source.py tests/unit/infrastructure/test_unity_catalog_adapter.py tests/unit/infrastructure/test_looker_adapter.py tests/unit/infrastructure/test_dbt_metricflow_adapter.py tests/unit/infrastructure/test_semantic_cli.py tests/unit/infrastructure/test_api.py` -> passed
  - `python -m mypy src/ds_agent/memory/semantic/application/dtos.py src/ds_agent/memory/semantic/application/ports.py src/ds_agent/memory/semantic/application/sync_semantic_source.py src/ds_agent/memory/semantic/infrastructure/adapters src/ds_agent/infrastructure/semantic_memory_container.py src/ds_agent/cli/semantic_cli.py` -> passed
  - `src/ds_agent/api/ws_handler.py` remains outside targeted mypy validation because of existing module-wide type debt; semantic RPC behavior was verified via unit tests plus `ruff check`

### Implementation Update (2026-04-16, Session 18)

- Started DoD close-out work by expanding the built-in enterprise semantic seed pack from a single-example pack into a realistic baseline pack:
  - `src/ds_agent/skills/domain/domain-pack-enterprise/metrics/` now contains `10` metrics
  - `src/ds_agent/skills/domain/domain-pack-enterprise/glossary/` now contains `30` glossary terms
  - `src/ds_agent/skills/domain/domain-pack-enterprise/trust/` now contains `20` table-trust definitions
  - `src/ds_agent/skills/domain/domain-pack-enterprise/verified_queries/` now contains `15` verified queries
- The expanded pack now covers the first wave of KPI grounding targets needed by the DoD and E2E plan:
  - `monthly_churn_rate`
  - `monthly_active_users`
  - `lifetime_value`
  - `average_revenue_per_user`
  - `net_revenue_retention`
  - `weekly_active_users`
  - `customer_acquisition_cost`
  - `gross_margin`
  - `trial_to_paid_conversion_rate`
  - `monthly_recurring_revenue`
- Added a deterministic regeneration utility:
  - `scripts/refresh_domain_pack_enterprise.py`
  - rewrites the built-in pack assets and recomputes the canonical `pack.yaml` checksum
  - keeps future pack edits reproducible instead of hand-editing dozens of seed files
- Updated the built-in pack documentation in `src/ds_agent/skills/domain/domain-pack-enterprise/README.md` so the current seed counts and refresh command are visible to operators/developers.
- Added regression coverage to hold the seed baseline in place:
  - `tests/unit/infrastructure/test_yaml_metric_loader.py` now verifies the built-in pack loads with at least `10/30/20/15` artifact counts
  - `tests/integration/skills/test_load_semantic_pack_skill_tool.py` now verifies the built-in `domain-pack-enterprise` skill dry-run returns the same minimum counts through the tool surface
- Validation status:
  - `python scripts/refresh_domain_pack_enterprise.py` -> passed
  - `python scripts/validate_metrics.py src/ds_agent/skills/domain/domain-pack-enterprise` -> `metrics=10 glossary=30 trust=20 verified_queries=15`
  - `pytest tests/unit/infrastructure/test_yaml_metric_loader.py tests/integration/skills/test_load_semantic_pack_skill_tool.py tests/integration/semantic/test_load_semantic_pack.py -q` -> `11 passed`
  - `ruff check scripts/refresh_domain_pack_enterprise.py src/ds_agent/skills/domain/domain-pack-enterprise/README.md tests/unit/infrastructure/test_yaml_metric_loader.py tests/integration/skills/test_load_semantic_pack_skill_tool.py` -> passed
  - `python -m mypy scripts/refresh_domain_pack_enterprise.py src/ds_agent/memory/semantic/infrastructure/yaml_metric_loader.py` -> passed

### Implementation Update (2026-04-16, Session 19)

- Continued DoD close-out work by turning the expanded seed pack into integration-level KPI query coverage:
  - extended `tests/integration/tools/test_semantic_query.py`
  - added built-in-pack loading helper so integration tests exercise the real `domain-pack-enterprise` assets instead of one-off fixtures
- Added verified-path coverage for the three KPI families called out in the DoD:
  - `"이탈률"` -> `monthly_churn_rate` -> `vq-monthly-churn-postgres`
  - `"MAU"` -> `monthly_active_users` -> `vq-mau-postgres`
  - `"LTV"` -> `lifetime_value` -> `vq-ltv-postgres`
- Added trust-policy downgrade coverage on the same verified-query path:
  - bronze downgrade of `prod.product.user_activity_daily` now verifies `semantic_query` returns warnings plus `next_action="ask_user"`
  - untrusted downgrade of the same table now verifies `semantic_query` blocks execution with an explicit warning
- Updated the enterprise seed pack aliases so Korean KPI wording is grounded through canonical semantic memory:
  - `monthly_churn_rate` and `term.churn` now include the alias `"이탈률"`
- Validation status:
  - `pytest tests/integration/tools/test_semantic_query.py -q` -> `8 passed`
  - `ruff check tests/integration/tools/test_semantic_query.py` -> passed
- Note:
  - this closes the integration-test slice for the verified KPI path and bronze/untrusted warnings
  - the DoD items still reference end-to-end scenarios, so Electron/runtime/operator full-path validation remains open

### Implementation Update (2026-04-16, Session 20)

- Landed the first Electron semantic-inspection UX slice for operators and reviewers:
  - added `electron/src/renderer/hooks/useSemanticSource.ts`
  - added `electron/src/renderer/components/semantic/MetricSourcePanel.tsx`
  - wired the experiments tab so semantic source inspection is available directly in the desktop UI
- `MetricSourcePanel` now resolves semantic metadata through the existing WebSocket RPC surface:
  - `semantic.lookupMetric`
  - `semantic.getVerifiedQuery`
  - `semantic.getTrust`
- The panel supports both explicit search and low-friction discovery:
  - manual lookup input for metric id / alias inspection
  - hover / focus / click quick-probe chips for `이탈률`, `MAU`, `LTV`
  - experiment-table metric headers now emit hover / focus / click inspection events into the panel
- The rendered Electron surface now shows the core provenance fields called out in the UX/DoD section:
  - metric owner
  - metric definition
  - verified query id / dialect / verifier
  - trust decision + referenced table grades when trust metadata exists
- Validation status:
  - `npm --prefix electron run typecheck` -> passed
  - `npm --prefix electron run build` -> passed

## 1. 배경 및 문제 정의

### 1.1 기업 현장에서 반복되는 의미론 오류

엔터프라이즈 데이터 분석 요청에서 DS Agent 가 틀리는 주된 원인은 SQL 문법이 아니라 **metric 정의가 조직마다 다르기 때문**이다. 동일한 "이탈률" 이라도 다음과 같이 팀별 정의가 어긋난다.

- Growth 팀: "당월 해지자 수 / 전월 말 활성 구독자 수"
- Finance 팀: "당월 MRR 감소액 / 전월 말 MRR"
- Product 팀: "지난 28일 로그인 0회 유저 수 / 전체 활성 유저 수"

Agent 가 이 맥락을 모른 채 schema introspection 만으로 쿼리를 생성하면 세 팀 중 어느 정의와도 일치하지 않는 숫자를 내놓게 된다. 같은 이유로 테이블 신뢰도 (`prod.subscription` vs `staging.subscription_v2_tmp`), refresh SLA (매일 04:00 UTC vs 비정기), PII 분류, 승인된 join 경로 등 **메타데이터가 의사결정에 필요한데도 Agent 에게는 보이지 않는다**.

### 1.2 현 `domain_kb` 의 한계

현재 `memory/domain_kb.py` 는 자유 텍스트 insight 를 append-only 로 저장한다. 장점은 LLM 친화 포맷이지만 다음 한계가 있다.

1. **Typed schema 부재**: owner, grain, verified_by 같은 구조화 필드 없음 → 프롬프트 주입 시 "어떤 게 공인 정의인지" 알 수 없음.
2. **신뢰도 태깅 없음**: 자유 insight 와 조직 승인 정의가 동일 weight 로 검색됨.
3. **쿼리 패턴 재사용 불가**: verified query SQL 을 재활용하려면 copy-paste 필요.
4. **외부 Semantic Layer 와 단절**: dbt MetricFlow, Looker LookML, Unity Catalog 등과 동기화 경로 없음.
5. **Negative knowledge 부재**: "이 metric 은 이렇게 계산하면 안 된다" 같은 실패 이력을 구조화해 저장할 곳이 없음.

### 1.3 목표

- Metric 정의, 비즈니스 용어, 테이블 신뢰도, 검증된 쿼리 패턴, 조직 컨텍스트를 **typed & versioned artifact** 로 관리.
- Agent 가 SQL 생성 전 반드시 Semantic Layer 를 1차 조회하도록 orchestration 흐름을 유도 (단 state machine 은 여전히 사용하지 않는다 — LLM 의 tool 선택 bias 를 시스템 프롬프트와 도구 설명으로 유도한다).
- TaskContract / Runtime context 를 바탕으로 어떤 metric 정의를 우선할지 re-rank 하여, 같은 용어가 여러 팀에서 다르게 쓰일 때도 현재 업무 맥락에 맞는 정의를 고르게 한다.
- 성공/실패 실행으로부터 semantic candidate 를 자동 생성하고, ApprovalInbox / Telegram operator flow 를 통해 사람 승인 후에만 조직 기억을 갱신한다.
- 외부 Semantic Layer (dbt, Unity Catalog, Looker) 와의 양방향 sync 어댑터 기반 마련.
- Clean Architecture 준수: domain 순수성 유지, infra 에서만 SQLite/외부 API 접근.

---

## 2. 핵심 테제

1. **Metric 은 코드가 아니라 계약이다.** 쿼리보다 먼저 정의가 있어야 하며, 정의의 owner 는 Agent 가 아니라 사람이다.
2. **Semantic Query 는 1차, Raw SQL 은 fallback 이다.** Agent 의 기본 경로는 Metric Catalog 매칭, schema introspection 기반 SQL 은 명시적 경고와 함께만 사용한다.
3. **신뢰도는 등급으로 표현되고 행동을 바꾼다.** Gold / Silver / Bronze / Untrusted 등급은 단순 태그가 아니라 Agent 의 tool 선택 및 사용자 확인 요구 정책을 결정한다.
4. **Negative knowledge 는 positive knowledge 만큼 중요하다.** "과거 이 방식으로 계산해서 틀렸다" 이력이 매번 재주입되어야 같은 실수를 반복하지 않는다.
5. **조직별 semantic pack 은 skill 로 배포된다.** 특정 회사의 metric / 용어 집합은 `skills/domain/domain-pack-<org>` 로 packaging 되어 배포·버전관리된다.
6. **Semantic memory 는 read-only 지식베이스가 아니라 read-write 학습 루프다.** Agent 는 실행 전 읽고, 실행 후에는 proposal 을 남긴다.
7. **자율적 write 는 곧바로 Gold memory 를 오염시키면 안 된다.** Agent 기여분은 항상 pending proposal 로 적재되고, 승인·감사 로그를 거쳐 승격된다.

---

## 3. Semantic Layer 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│  Semantic Memory Layer  (memory/semantic/)                     │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Metric       │  │ Business     │  │ Verified Query       │ │
│  │ Catalog      │  │ Glossary     │  │ Store                │ │
│  │ (YAML+SQLite)│  │ (FTS5)       │  │ (SQL templates)      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │
│         │                 │                     │              │
│         └─────────────────┼─────────────────────┘              │
│                           ▼                                     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Data Trust Registry                                     │   │
│  │  - 테이블/컬럼 등급 (Gold/Silver/Bronze/Untrusted)      │   │
│  │  - Column lineage, refresh SLA, PII tag                 │   │
│  │  - Approved join paths                                   │   │
│  └──────┬──────────────────────────────────────────────────┘   │
│         ▼                                                       │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Organizational Context Store                            │   │
│  │  - Fiscal/campaign/freeze calendar                      │   │
│  │  - Team ownership map                                   │   │
│  │  - Decision log, approved metric per team               │   │
│  │  - Negative knowledge (past failures + reasons)         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                 │
│                          ▲ port interface                       │
└──────────────────────────┼──────────────────────────────────────┘
                           │
       ┌───────────────────┴───────────────────────┐
       │ Application Use Cases                      │
       │  - ResolveMetricUseCase                    │
       │  - LookupTermUseCase                       │
       │  - CheckTableTrustUseCase                  │
       │  - RecordNegativeKnowledgeUseCase          │
       └───────────────────┬───────────────────────┘
                           │
       ┌───────────────────┴───────────────────────┐
       │ Tools (LLM-facing)                         │
       │  - @tool semantic_query                    │
       │  - @tool lookup_term                       │
       │  - @tool describe_table_trust              │
       └───────────────────────────────────────────┘
```

### 3.1 컴포넌트 역할

| 컴포넌트 | 책임 | 주요 질의 |
|----------|------|-----------|
| MetricCatalog | metric 정의·계산식·owner·caveat·verified query 링크 | `resolve("이탈률")` → `MonthlyChurnRate` |
| BusinessGlossary | 용어·동의어·약어·번역 매핑 | `lookup("MAU")` → `{definition, synonyms:["월간 활성 유저"]}` |
| DataTrustRegistry | 테이블/컬럼 신뢰도·lineage·SLA·PII | `trust("prod.subscription")` → `Gold` |
| VerifiedQueryStore | 검증된 SQL 템플릿·파라미터·검증 이력 | `find_by_metric("monthly_churn")` → SQL template |
| OrgContextStore | 캘린더·팀 맵·의사결정·Negative knowledge | `calendar.is_freeze(date)` / `negative.lookup("churn")` |

### 3.2 Layer 간 참조 방향

Metric → VerifiedQuery (1:N), Metric → GlossaryTerm (M:N via synonyms), VerifiedQuery → DataTrust (쿼리 내 사용 테이블의 등급 체크), Metric → OrgContext (이 metric 을 공식 사용하는 팀 매핑). 모든 참조는 domain entity 상 UUID 기반이며 SQLite FK 로 강제된다.

### 3.3 자율형 Agent 통합 루프

Semantic Memory 는 조회 전용 저장소가 아니라, agent loop 와 양방향으로 연결된 운영 레이어다.

```
user/task contract
   -> semantic retrieval
   -> action policy (execute / warn / ask / block)
   -> sql/report execution
   -> verifier / retrospective
   -> semantic proposal queue
   -> human/operator approval
   -> semantic layer update
```

- **Plan 단계**: 사용자 질의와 `TaskContract.required_semantic_metrics`, `allowed_data_domains`, `decision_owner` 를 함께 읽어 metric 후보를 re-rank 한다.
- **Execute 단계**: SQL 계열 tool 호출 전 hook 이 semantic lookup 선행 여부와 table trust 정책을 확인한다.
- **Verify 단계**: verifier / review verdict / dashboard parity 를 근거로 verified query 후보 또는 negative knowledge 후보를 만든다.
- **Learn 단계**: `PostProjectLearner`, runtime event log, self-correction 이벤트를 읽어 glossary alias, verified query, failure lesson proposal 을 적재한다.
- **Approve 단계**: Electron `ApprovalInbox`, Telegram inline action, CLI 명령 중 하나로 proposal 을 승인/반려하며, 승인 전까지는 Gold semantic artifact 가 갱신되지 않는다.

---

## 4. 주요 데이터 모델

### 4.1 MetricCatalog

#### 4.1.1 YAML 파일 포맷 (사람 편집용)

```yaml
# memory/semantic/metrics/monthly_churn_rate.yaml
metric_id: monthly_churn_rate
display_name: "월간 이탈률"
owner: growth_team
owner_contact: "growth-analytics@corp.example"
definition: >
  당월 구독 해지 고객 수를 전월 말 활성 구독 고객 수로 나눈 비율.
  프로모션·환불 케이스 제외. B2B 와 B2C 세그먼트는 분리 계산.
synonyms: ["churn", "이탈률", "해지율", "monthly churn"]
grain: monthly
unit: ratio
direction: lower_is_better
typical_range: [0.02, 0.08]
calculation:
  numerator:
    source: growth.subscription
    filter: "event_type = 'cancel' AND refund_flag = FALSE"
    aggregation: "COUNT(DISTINCT user_id)"
  denominator:
    source: growth.subscription
    filter: "status = 'active' AS OF last_day_of_prev_month"
    aggregation: "COUNT(DISTINCT user_id)"
related_metrics: [retention_30d, ltv, arpu]
approved_by:
  - team: growth_team
    decision_date: 2025-11-02
    decision_id: DL-2025-113
caveats:
  - "프로모션 기간 중 일시적 하락 후 반등 패턴 존재"
  - "B2B/B2C 혼합 시 Simpson's paradox 위험"
  - "신규 가입 후 30일 이내 해지는 trial_cancel 로 별도 처리"
verified_queries:
  - vq_churn_001
  - vq_churn_b2b_only
version: 3
last_reviewed: 2026-03-15
```

#### 4.1.2 Pydantic 도메인 모델

```python
# memory/semantic/domain/metric.py
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class MetricCalculationComponent(BaseModel):
    source: str
    filter: str
    aggregation: str


class MetricCalculation(BaseModel):
    numerator: MetricCalculationComponent
    denominator: MetricCalculationComponent | None = None
    formula: str | None = None


class MetricApproval(BaseModel):
    team: str
    decision_date: date
    decision_id: str


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric_id: str
    display_name: str
    owner: str
    owner_contact: str | None
    definition: str
    synonyms: list[str] = Field(default_factory=list)
    grain: Literal["hourly", "daily", "weekly", "monthly", "quarterly", "yearly"]
    unit: Literal["ratio", "count", "amount", "duration_seconds", "percentage"]
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]
    typical_range: tuple[float, float] | None
    calculation: MetricCalculation
    related_metrics: list[str] = Field(default_factory=list)
    approved_by: list[MetricApproval] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    verified_query_ids: list[str] = Field(default_factory=list)
    version: int = 1
    last_reviewed: date | None = None
```

Entity 는 frozen, 외부 의존성 zero (pydantic 은 core stdlib 대체로 허용). YAML 파싱과 SQLite 직렬화는 infrastructure 에서 수행.

### 4.2 BusinessGlossary

```python
# memory/semantic/domain/glossary.py
class GlossaryTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    term_id: str
    canonical_form: str
    definition: str
    synonyms: list[str] = Field(default_factory=list)
    abbreviations: list[str] = Field(default_factory=list)
    translations: dict[str, str] = Field(default_factory=dict)  # {"en": "MAU", "ko": "월간 활성 유저"}
    linked_metric_ids: list[str] = Field(default_factory=list)
    category: Literal["metric", "entity", "event", "dimension", "other"]
    owner: str | None = None
```

SQLite FTS5 가상테이블을 활용해 term, synonyms, definition 을 동시에 검색. 검색 결과는 rank × category weight (metric > entity > other) 로 정렬.

### 4.3 DataTrustRegistry

```python
# memory/semantic/domain/trust.py
from enum import Enum


class TrustGrade(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    UNTRUSTED = "untrusted"


class RefreshSLA(BaseModel):
    cadence: Literal["realtime", "hourly", "daily", "weekly", "adhoc"]
    max_staleness_minutes: int
    last_refreshed_at: datetime | None


class ColumnTrust(BaseModel):
    column: str
    pii_class: Literal["none", "low", "medium", "high"]
    lineage_upstream: list[str] = Field(default_factory=list)  # ["raw.events.user_id"]
    nullable_ratio: float | None = None
    data_type: str


class TableTrust(BaseModel):
    model_config = ConfigDict(frozen=True)

    fqtn: str  # fully qualified table name: "prod.growth.subscription"
    grade: TrustGrade
    owner: str
    description: str
    refresh: RefreshSLA
    columns: list[ColumnTrust] = Field(default_factory=list)
    approved_joins: list["ApprovedJoin"] = Field(default_factory=list)
    grade_rationale: str
    last_audited: date
```

#### 4.3.1 등급 판정 기준

| 등급 | 필수 조건 | Agent 행동 |
|------|-----------|-----------|
| **Gold** | 공인 source, SLA 정의 + last_refresh 주기 준수, 100% column lineage, owner 명시, PII 분류 완료, audit ≤ 90일 | 자율 사용 가능, 프롬프트 주입 시 grade=Gold 태깅만 |
| **Silver** | 정기 refresh 있으나 lineage 부분 부재 or owner 에스컬레이션 미정 | 사용 가능하되 응답에 caveat 자동 첨부, `schema_introspection` tool 사용 시 `trust=silver` 표시 |
| **Bronze** | 비정기 refresh, 스키마 불안정, 최근 90일 내 audit 없음 | 사용자 확인 필요 (Agent 가 "bronze 등급 테이블을 사용하려 하는데 괜찮습니까?" 식 질의), 결과에 경고 배너 |
| **Untrusted** | 출처 불명, PII 미분류, 접근 정책 미설정, staging/tmp 접두 | 기본적으로 사용 불가. `--allow-untrusted` 플래그 또는 admin role 에서만 허용 |

#### 4.3.2 Approved Join

```python
class ApprovedJoin(BaseModel):
    target_fqtn: str
    left_keys: list[str]
    right_keys: list[str]
    join_type: Literal["inner", "left", "right", "full"]
    cardinality: Literal["one_to_one", "one_to_many", "many_to_many"]
    caveat: str | None
```

SQL 생성 시 approved_joins 에 없는 join 이 나오면 Agent 는 `unverified_join` 경고 태그를 응답에 포함하고 VerifiedQuery 로 승격할지 사용자에게 묻는다.

### 4.4 VerifiedQueryStore

```python
# memory/semantic/domain/verified_query.py
class QueryParameter(BaseModel):
    name: str
    type: Literal["date", "datetime", "int", "float", "string", "array"]
    description: str
    default: str | None = None


class VerifiedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    vq_id: str
    metric_id: str | None  # metric 과 연결된 경우
    dialect: Literal["postgres", "bigquery", "snowflake", "duckdb", "databricks_sql"]
    description: str
    sql_template: str  # jinja2-style {{param}} 허용
    parameters: list[QueryParameter] = Field(default_factory=list)
    referenced_tables: list[str]
    verified_by: str
    last_verified: date
    verification_evidence: str  # ex: "Growth dashboard #47 와 결과 일치 (2026-03-10)"
    failure_modes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
```

검증 이력은 append-only `verified_query_audit` 테이블에 별도 기록 (누가 언제 어떤 기준으로 검증했는지 복원 가능해야 함).

### 4.5 OrgContextStore

```python
# memory/semantic/domain/org_context.py
class CalendarEvent(BaseModel):
    event_id: str
    type: Literal["fiscal_period", "campaign", "freeze", "launch", "holiday"]
    name: str
    start_date: date
    end_date: date
    description: str
    impact_hint: str | None  # ex: "프로모션 기간 — 이탈률 일시적 하락 예상"


class TeamOwnership(BaseModel):
    team: str
    contact: str
    owned_metrics: list[str]
    owned_tables: list[str]
    approver_chain: list[str]


class DecisionLogEntry(BaseModel):
    decision_id: str
    date: date
    summary: str
    context: str
    metrics_used: list[str]
    verified_query_ids: list[str]
    outcome: Literal["approved", "rejected", "deferred"]
    rationale: str


class NegativeKnowledge(BaseModel):
    nk_id: str
    topic: str  # "monthly_churn_rate", "session_duration" 등
    wrong_approach: str
    why_wrong: str
    correct_approach: str
    recorded_at: datetime
    recorded_by: Literal["human", "agent_self_correction", "retrospective"]
    references: list[str] = Field(default_factory=list)  # decision_id or experiment_id
```

Negative knowledge 는 `domain_kb` 에서 failure insight 를 retrospect 할 때 (§5 Agent-Operated QA 스펙과 연계) 자동 생성되고, 사람이 승인한 뒤에만 승격된다.

### 4.6 SemanticProposal (autonomous write-back queue)

```python
# memory/semantic/domain/proposal.py
from typing import Any


class SemanticProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: str
    proposal_type: Literal[
        "metric_alias",
        "glossary_term",
        "verified_query",
        "negative_knowledge",
        "table_trust_patch",
        "metric_review_request",
    ]
    status: Literal["pending", "approved", "rejected", "applied", "expired"]
    source_run_id: str | None = None
    source_session_id: str | None = None
    source_tool_name: str | None = None
    target_id: str | None = None
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    risk: Literal["low", "medium", "high"] = "medium"
    proposed_by: Literal["agent", "human", "adapter_sync"] = "agent"
    auto_apply_eligible: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
```

모든 agent-originated semantic write 는 먼저 `SemanticProposal` 로 적재된다. `approved` 또는 `applied` 상태가 되기 전에는 `MetricCatalog`, `BusinessGlossary`, `VerifiedQueryStore`, `OrgContextStore` 원본 artifact 를 직접 변경하지 않는다. 초기 정책상 auto-apply 는 `metric_alias` / `glossary_term` 같은 low-risk proposal 에만 제한적으로 허용하며, `verified_query`, `table_trust_patch`, `negative_knowledge` 는 항상 사람 승인 경로를 거친다.

---

## 5. Clean Architecture 매핑 표

| Layer | 모듈 | 책임 |
|-------|------|------|
| Domain (`memory/semantic/domain/`) | `metric.py`, `glossary.py`, `trust.py`, `verified_query.py`, `org_context.py` | 순수 entity / value object, pydantic 외 의존성 zero |
| Application (`memory/semantic/application/`) | `resolve_metric.py`, `lookup_term.py`, `check_table_trust.py`, `find_verified_query.py`, `record_negative_knowledge.py`, `ports.py` | Use case + port interface. Repository 는 추상만 정의 |
| Infrastructure (`memory/semantic/infrastructure/`) | `sqlite_metric_repo.py`, `sqlite_glossary_repo.py`, `sqlite_trust_repo.py`, `sqlite_vq_repo.py`, `sqlite_org_repo.py`, `yaml_metric_loader.py`, `fts_search.py`, `migrations/v6_semantic_layer.py` | SQLite 스키마, YAML import/export, FTS5 연동, migration |
| Infra Adapters (external) (`memory/semantic/infrastructure/adapters/`) | `dbt_metricflow_adapter.py`, `unity_catalog_adapter.py`, `looker_adapter.py`, `bigquery_schema_adapter.py`, `snowflake_schema_adapter.py` | 외부 Semantic Layer sync |
| Presentation (tools) (`tools/semantic_query.py`, `tools/lookup_term.py`, `tools/describe_table_trust.py`) | LLM-facing @tool wrappers | DI 컨테이너에서 use case 주입, DTO 변환만 수행 |
| Composition Root (`app/composition.py`) | DI wiring | Port ↔ Adapter 연결. 이 지점에서만 구체 class import 허용 |

**의존성 규칙 강제 검증**: `scripts/check_layer_deps.py` 를 CI 에 추가해 domain → application / infrastructure import 를 금지한다 (AST 기반).

자율형 write-back 을 위해 아래 컴포넌트를 같은 레이어 규칙 아래 추가한다.

- Application: `submit_semantic_proposal.py`, `review_semantic_proposal.py`, `apply_semantic_proposal.py`
- Infrastructure: `sqlite_proposal_repo.py`, `proposal_event_log.py`
- Agent hooks: `agent/semantic_hooks.py` (`SemanticReadGuardHook`, `SemanticTrustHook`, `SemanticWritebackHook`)
- Runtime integration: `runtime/approval_store.py`, `runtime/coordinator.py`, `runtime/runtime_event_log.py`

---

## 6. SQLite 스키마 — Migration v6

기존 migration 체인 끝에 v6 을 추가. 모든 테이블은 `CREATE TABLE IF NOT EXISTS` 와 `CREATE INDEX IF NOT EXISTS` 사용, rollback SQL 동봉.

```sql
-- memory/semantic/infrastructure/migrations/v6_semantic_layer.sql

-- 6.1 Metrics
CREATE TABLE IF NOT EXISTS semantic_metric (
    metric_id        TEXT PRIMARY KEY,
    display_name     TEXT NOT NULL,
    owner            TEXT NOT NULL,
    owner_contact    TEXT,
    definition       TEXT NOT NULL,
    grain            TEXT NOT NULL,
    unit             TEXT NOT NULL,
    direction        TEXT NOT NULL,
    typical_range_lo REAL,
    typical_range_hi REAL,
    calculation_json TEXT NOT NULL,       -- MetricCalculation 직렬화
    caveats_json     TEXT NOT NULL,
    related_json     TEXT NOT NULL,
    approved_json    TEXT NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    last_reviewed    TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_metric_synonym (
    metric_id TEXT NOT NULL,
    synonym   TEXT NOT NULL,
    PRIMARY KEY (metric_id, synonym),
    FOREIGN KEY (metric_id) REFERENCES semantic_metric(metric_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metric_synonym ON semantic_metric_synonym(synonym);

CREATE VIRTUAL TABLE IF NOT EXISTS semantic_metric_fts USING fts5(
    metric_id UNINDEXED,
    display_name,
    definition,
    synonyms,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- 6.2 Glossary
CREATE TABLE IF NOT EXISTS semantic_glossary (
    term_id        TEXT PRIMARY KEY,
    canonical_form TEXT NOT NULL,
    definition     TEXT NOT NULL,
    synonyms_json  TEXT NOT NULL,
    abbrev_json    TEXT NOT NULL,
    translations_json TEXT NOT NULL,
    category       TEXT NOT NULL,
    owner          TEXT,
    linked_metrics_json TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS semantic_glossary_fts USING fts5(
    term_id UNINDEXED,
    canonical_form,
    definition,
    synonyms,
    abbreviations,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- 6.3 Data Trust Registry
CREATE TABLE IF NOT EXISTS semantic_table_trust (
    fqtn            TEXT PRIMARY KEY,
    grade           TEXT NOT NULL CHECK (grade IN ('gold','silver','bronze','untrusted')),
    owner           TEXT NOT NULL,
    description     TEXT NOT NULL,
    refresh_json    TEXT NOT NULL,
    grade_rationale TEXT NOT NULL,
    last_audited    TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trust_grade ON semantic_table_trust(grade);

CREATE TABLE IF NOT EXISTS semantic_column_trust (
    fqtn         TEXT NOT NULL,
    column_name  TEXT NOT NULL,
    pii_class    TEXT NOT NULL,
    lineage_json TEXT NOT NULL,
    nullable_ratio REAL,
    data_type    TEXT NOT NULL,
    PRIMARY KEY (fqtn, column_name),
    FOREIGN KEY (fqtn) REFERENCES semantic_table_trust(fqtn) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS semantic_approved_join (
    left_fqtn    TEXT NOT NULL,
    right_fqtn   TEXT NOT NULL,
    left_keys    TEXT NOT NULL,
    right_keys   TEXT NOT NULL,
    join_type    TEXT NOT NULL,
    cardinality  TEXT NOT NULL,
    caveat       TEXT,
    PRIMARY KEY (left_fqtn, right_fqtn, left_keys, right_keys),
    FOREIGN KEY (left_fqtn)  REFERENCES semantic_table_trust(fqtn) ON DELETE CASCADE,
    FOREIGN KEY (right_fqtn) REFERENCES semantic_table_trust(fqtn) ON DELETE CASCADE
);

-- 6.4 Verified Query Store
CREATE TABLE IF NOT EXISTS semantic_verified_query (
    vq_id                TEXT PRIMARY KEY,
    metric_id            TEXT,
    dialect              TEXT NOT NULL,
    description          TEXT NOT NULL,
    sql_template         TEXT NOT NULL,
    parameters_json      TEXT NOT NULL,
    referenced_tables_json TEXT NOT NULL,
    verified_by          TEXT NOT NULL,
    last_verified        TEXT NOT NULL,
    verification_evidence TEXT NOT NULL,
    failure_modes_json   TEXT NOT NULL,
    tags_json            TEXT NOT NULL,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (metric_id) REFERENCES semantic_metric(metric_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_vq_metric  ON semantic_verified_query(metric_id);
CREATE INDEX IF NOT EXISTS idx_vq_dialect ON semantic_verified_query(dialect);

CREATE TABLE IF NOT EXISTS semantic_verified_query_audit (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    vq_id       TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('create','verify','deprecate','update')),
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    evidence    TEXT,
    FOREIGN KEY (vq_id) REFERENCES semantic_verified_query(vq_id) ON DELETE CASCADE
);

-- 6.5 Organizational Context
CREATE TABLE IF NOT EXISTS semantic_calendar_event (
    event_id     TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    name         TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    description  TEXT NOT NULL,
    impact_hint  TEXT
);
CREATE INDEX IF NOT EXISTS idx_calendar_range ON semantic_calendar_event(start_date, end_date);

CREATE TABLE IF NOT EXISTS semantic_team_ownership (
    team            TEXT PRIMARY KEY,
    contact         TEXT NOT NULL,
    owned_metrics_json TEXT NOT NULL,
    owned_tables_json  TEXT NOT NULL,
    approver_chain_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_decision_log (
    decision_id       TEXT PRIMARY KEY,
    date              TEXT NOT NULL,
    summary           TEXT NOT NULL,
    context           TEXT NOT NULL,
    metrics_used_json TEXT NOT NULL,
    vq_ids_json       TEXT NOT NULL,
    outcome           TEXT NOT NULL,
    rationale         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_negative_knowledge (
    nk_id            TEXT PRIMARY KEY,
    topic            TEXT NOT NULL,
    wrong_approach   TEXT NOT NULL,
    why_wrong        TEXT NOT NULL,
    correct_approach TEXT NOT NULL,
    recorded_at      TEXT NOT NULL DEFAULT (datetime('now')),
    recorded_by      TEXT NOT NULL,
    references_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nk_topic ON semantic_negative_knowledge(topic);

-- 6.6 Triggers: FTS sync
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_insert AFTER INSERT ON semantic_metric
BEGIN
    INSERT INTO semantic_metric_fts(metric_id, display_name, definition, synonyms)
    VALUES (NEW.metric_id, NEW.display_name, NEW.definition,
            (SELECT group_concat(synonym, ' ') FROM semantic_metric_synonym WHERE metric_id = NEW.metric_id));
END;
-- 동일 패턴으로 update / delete trigger, glossary 도 반복
```

**Rollback**: v6 → v5 은 `DROP TABLE` 역순, YAML 원본은 `memory/semantic/metrics/*.yaml` 에 보존되므로 재빌드 가능.

Migration v6 에는 autonomous write-back 을 위한 부가 테이블도 동일 변경셋으로 포함한다.

- `semantic_proposal`: `proposal_id`, `proposal_type`, `status`, `target_id`, `summary`, `payload_json`, `confidence`, `risk`, `source_run_id`, `source_session_id`, `created_at`, `reviewed_by`, `reviewed_at`
- `semantic_proposal_evidence`: `proposal_id`, `evidence_type`, `evidence_ref`, `note`

핵심 원칙은 append-only evidence 와 상태 전이 감사 가능성이다. proposal 이 반려되더라도 evidence 와 decision trace 는 남겨야 이후 false positive 패턴을 조정할 수 있다.

---

## 7. Semantic Query 도구

### 7.1 `@tool semantic_query` 동작 순서

```
INPUT: natural_language_query: str, required_grain: str|None, as_of_date: date|None
  │
  ├─ [1] Parse query → candidate terms (LLM 기반 term extractor 또는 간단 NER)
  │
  ├─ [2] BusinessGlossary.lookup(terms)  → 정규화된 canonical form 확보
  │
  ├─ [3] MetricCatalog.resolve(canonical_forms, grain=required_grain)
  │       matches: list[Metric]  (score = exact + synonym + fuzzy)
  │
  ├─ [3.5] Runtime context re-rank
  │       TaskContract.required_semantic_metrics, allowed_data_domains,
  │       decision_owner team, 최근 승인 proposal, current run goal 반영
  │
  ├─ [4] if matches.is_empty():
  │         → FALLBACK to sql_tools.introspect_and_build()
  │         → attach warning: "공인 metric 정의 부재, 추론 기반 SQL"
  │         → return {kind: "inferred", sql, warnings, reasoning}
  │
  ├─ [5] metric = matches[0]  (다수 매칭 시 사용자 확인 요청)
  │       VerifiedQueryStore.find_by_metric(metric.metric_id, dialect)
  │
  ├─ [6] if verified_query found:
  │         → parameter binding (as_of_date, date range 등)
  │         → DataTrustRegistry.check_all(vq.referenced_tables)
  │         → if any grade < Silver → 경고 또는 차단
  │         → return {kind: "verified", sql, metric, caveats, trust_report}
  │
  ├─ [7] elif metric only (verified query 없음):
  │         → metric.calculation 으로 SQL 합성
  │         → ApprovedJoin 검증
  │         → return {kind: "metric_synthesized", sql, metric, warnings}
  │
  └─ [8] OrgContextStore.calendar.lookup(as_of_date)
         negative_knowledge = OrgContextStore.negative.lookup(metric.metric_id)
         → 결과에 caveat 병합
```

`semantic_query` 는 단순 SQL 생성기가 아니라 실행 정책 생성기다. 반환값에는 "바로 실행해도 되는지", "경고와 함께 실행할지", "사용자 확인이 필요한지" 를 담아 후속 tool / UI / runtime 이 같은 판단을 공유하도록 한다.

### 7.2 `sql_tools` 와의 관계

기존 `tools/sql_tools.py` 는 그대로 유지. 시스템 프롬프트에서 tool 사용 우선순위를 명시:

```
PREFERRED: semantic_query  (조직 공인 metric 사용)
FALLBACK:  sql_tools        (metric 미정의 시, 경고 포함)
```

또한 `sql_tools.run_query` 실행 전 DataTrustRegistry 를 호출해 Gold/Silver/Bronze 중 어느 등급의 테이블이 참조되는지 자동 주석 처리한다. Bronze/Untrusted 가 포함되면 사용자 확인 prompt 를 생성하는 pre-hook 를 둔다.

### 7.3 도구 시그니처

```python
# tools/semantic_query.py
@tool(name="semantic_query",
      description="조직 공인 Metric Catalog 기반 쿼리. 사용자 질문을 metric 정의에 매칭해 검증된 SQL 과 caveat 를 반환한다. metric 매칭 실패 시 자동으로 sql_tools 로 fallback 하되 경고를 붙인다.")
def semantic_query(
    question: str,
    required_grain: Literal["hourly","daily","weekly","monthly","quarterly","yearly"] | None = None,
    as_of_date: str | None = None,  # ISO date
    dialect: Literal["postgres","bigquery","snowflake","duckdb","databricks_sql"] = "postgres",
    allow_untrusted: bool = False,
) -> SemanticQueryResult: ...
```

`SemanticQueryResult` DTO:

```python
class SemanticQueryResult(BaseModel):
    kind: Literal["verified", "metric_synthesized", "inferred"]
    sql: str
    metric: MetricDTO | None
    verified_query_id: str | None
    matched_terms: list[str]
    confidence: float
    trust_report: list[TableTrustDTO]
    caveats: list[str]
    warnings: list[str]   # ex: "bronze 테이블 사용", "metric 미정의 — 추론 기반"
    calendar_hints: list[str]
    negative_knowledge: list[str]
    next_action: Literal["execute", "execute_with_warning", "ask_user", "block"]
    requires_confirmation: bool
    reasoning: str        # LLM 이 사용자에게 보여줄 설명 원재료
```

### 7.4 Hook 기반 강제와 semantic write-back

이 스펙의 핵심은 semantic memory 를 "참조 가능" 수준에 두지 않고, agent loop 가 코드 레벨에서 항상 경유하게 만드는 것이다. Harness engineering 원칙에 따라 문서 규칙보다 hook 이 우선한다.

- `SemanticReadGuardHook` (`agent/semantic_hooks.py`): metric-like 어휘 또는 `TaskContract.required_semantic_metrics` 존재 시, 첫 SQL 계열 tool 호출 전에 `semantic_query` / `lookup_term` 선행 여부 검사. 미충족이면 runtime warning 과 prompt hint 를 삽입한다.
- `SemanticTrustHook`: `sql_tools` / `code_execution` 경유 SQL 실행 전 참조 테이블을 파싱해 `DataTrustRegistry` 를 평가한다. `next_action=="ask_user"` 또는 `"block"` 이면 `approval_store` 로 escalation event 를 생성한다.
- `SemanticWritebackHook`: query 실행 성공 후 사용자 수용, verifier pass/warn, dashboard parity 확인이 모이면 verified query / glossary alias / trust patch candidate 를 `SemanticProposal` 로 적재한다.
- `SemanticRetrospectiveHook`: self-correction, reviewer reject, post-project retrospective 를 읽어 negative knowledge proposal 을 적재한다. 이때 기존 `domain_kb` free-text insight 도 함께 남겨 backwards compatibility 를 유지한다.
- Hook 은 workflow state machine 이 아니다. LLM 의 선택을 완전히 대체하지 않고, tool 선택 편향과 안전 장치를 코드 레벨에서 보강한다.

---

## 8. 외부 연동 로드맵

| Phase | 대상 | 어댑터 | 주요 작업 |
|-------|------|--------|-----------|
| **P0** | Postgres (현행) | `postgres_schema_adapter.py` | 기존 `tools/integration_tools.py` 재사용, `information_schema` → DataTrustRegistry 테이블 자동 registration (기본 등급 Silver, audit 후 승격) |
| **P1** | BigQuery / Snowflake | `bigquery_schema_adapter.py`, `snowflake_schema_adapter.py` | INFORMATION_SCHEMA 수집, refresh SLA 추정 (last_modified_time 주기 분석), SQL dialect 별 VerifiedQuery 생성 지원 |
| **P1** | dbt Semantic Layer | `dbt_metricflow_adapter.py` | MetricFlow GraphQL API → Metric 자동 동기화. `metric_id` 충돌 시 namespace `dbt:` prefix |
| **P2** | Databricks Unity Catalog | `unity_catalog_adapter.py` | Column-level lineage / ABAC tag import, Gold 등급 판정 기준에 Unity lineage 완비성 반영 |
| **P2** | Looker / Tableau | `looker_adapter.py` | LookML model view → BusinessGlossary sync, Looks SQL → VerifiedQuery 로 import (사람 승인 단계 필수) |
| **P3** | Custom YAML | `yaml_metric_loader.py` (이미 P0) | 조직 자체 YAML → MetricCatalog. 변경은 PR 기반, `scripts/validate_metrics.py` 로 pre-commit 검증 |

### 8.1 어댑터 Port 정의

```python
# memory/semantic/application/ports.py
class ExternalSemanticSource(Protocol):
    name: str
    def fetch_metrics(self, since: datetime | None) -> list[Metric]: ...
    def fetch_tables(self, since: datetime | None) -> list[TableTrust]: ...
    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]: ...

class SemanticSyncPolicy(BaseModel):
    source_name: str
    overwrite: bool = False            # False = merge; True = source 우선
    id_namespace: str | None = None    # "dbt:", "looker:" 등
    allowed_grades: list[TrustGrade] = [TrustGrade.GOLD, TrustGrade.SILVER]
```

`SyncSemanticSourceUseCase(source: ExternalSemanticSource, policy: SemanticSyncPolicy)` 가 merge 전략을 결정. 모든 import 는 dry-run 리포트 생성 후 사람 승인 단계 존재.

---

## 9. Prompt 통합

### 9.1 Agent 시스템 프롬프트 확장

```
[Semantic Memory Usage Policy]
1. 사용자 질문에 "metric 스러운 어휘" (이탈률, 전환율, GMV 등) 가 포함되면 반드시 semantic_query 를 먼저 호출한다.
2. semantic_query 결과 kind=="verified" 이면 그 SQL 을 그대로 사용하고 응답에 metric owner, definition, last_verified 를 명시한다.
3. kind=="metric_synthesized" 이면 caveat 를 모두 사용자에게 전달한다.
4. kind=="inferred" 이면 응답 최상단에 다음 경고 배너를 반드시 포함한다:
   "⚠ 이 결과는 공인 Metric 정의가 아닌 스키마 추론에 기반합니다. 숫자 해석 시 주의하세요."
5. DataTrustRegistry 에서 grade=bronze/untrusted 테이블이 포함된 쿼리 결과는 반드시 경고 라벨 포함.
6. NegativeKnowledge 가 반환되면 해당 접근을 우회하거나 사용자에게 확인한다.
```

(실제 이모지/특수문자는 프로젝트 규칙에 맞춰 텍스트로 치환)

### 9.2 프롬프트 컨텍스트 주입 템플릿

`memory/unified_memory.py` 의 `build_context()` 에서 반환되는 컨텍스트에 semantic section 추가:

```
## Semantic Context
- Matched metrics (top 3 by relevance):
  - monthly_churn_rate (owner: growth_team, last_reviewed: 2026-03-15)
    definition: ...
    caveats: [...]
- Glossary:
  - MAU → 월간 활성 유저 (category: metric)
- Data Trust (for tables mentioned in session):
  - prod.growth.subscription → Gold (refresh: daily @04:00 UTC)
  - staging.sub_v2_tmp      → Untrusted (사용 금지)
- Calendar (as_of 2026-Q1):
  - 2026-02-01 ~ 2026-02-14: Spring Promotion Campaign (이탈률 일시 하락 예상)
- Negative knowledge (monthly_churn_rate):
  - "PROMO 고객까지 포함해 계산 → 실제 대비 저평가" (nk-2025-31)
```

context assembly 는 relevance score 기반 top-K + token budget 으로 clip. 규모가 커지면 lazy retrieval (tool 호출 시에만 로드) 로 전환.

### 9.3 TaskContract / RunContext 결합

semantic retrieval 은 세션 바깥의 "전사 공통 정의" 만 보면 부족하다. 현재 업무가 무엇인지까지 포함해야 자율형 Agent 가 올바른 metric 을 고른다.

- `TaskContract.required_semantic_metrics`: 우선 매칭해야 하는 metric shortlist 로 사용
- `TaskContract.allowed_data_domains`: glossary / trust / verified query ranking 에 domain prior 로 반영
- `TaskContract.decision_owner` 및 audience: 동음이의 metric 이 여러 팀에 걸칠 때 owner affinity 로 tie-break
- 현재 run 의 verifier 상태: 최근 fail verdict 가 있던 metric / join path 는 confidence penalty 적용
- 최근 승인된 `SemanticProposal`: 세션 도중 승인된 alias / NK 를 곧바로 retrieval ranking 에 반영

프롬프트에는 semantic facts 뿐 아니라 semantic priority 도 주입한다.

```
## Semantic Priority
- required metrics: monthly_churn_rate, revenue_per_user
- preferred owners: growth_team
- blocked tables: staging.sub_v2_tmp
- recent approved proposals:
  - alias "gross rev" -> revenue_per_user
  - NK: "promo users 포함 churn 계산 금지"
```

---

## 10. UX

### 10.1 Electron MetricSourcePanel

숫자를 표시하는 모든 컴포넌트 (테이블 셀, KPI 카드, 차트 tooltip) 에서 숫자 아래 subtle underline + hover 시 popover 제공:

```
┌──────────────────────────────────────────────┐
│ 월간 이탈률                                   │
│ 4.6%   ↓ 0.3%p WoW                           │
│ ─────                                        │
│ source: metric_catalog:monthly_churn_rate v3 │
│ owner:  growth_team                          │
│ defn:   당월 해지자 수 / 전월 말 활성 ...    │
│ verified_query: vq_churn_001                 │
│ last_verified: 2026-03-15 (이수진)           │
│ trust: prod.growth.subscription [Gold]       │
│ caveats:                                     │
│  • 프로모션 기간 일시 하락                   │
│  • B2B/B2C 분리 권장                         │
│ ▶ Open Metric Spec   ▶ Open Verified SQL    │
└──────────────────────────────────────────────┘
```

추론 기반 (kind=inferred) 인 경우 숫자를 점선 underline + 경고 아이콘 (텍스트 라벨 [inferred]) 로 표시.

컴포넌트 위치: `electron/renderer/components/semantic/MetricSourcePanel.tsx`, tooltip trigger hook `useSemanticSource(metricId)`.

### 10.2 CLI `semantic` 서브커맨드

```
ds semantic lookup "이탈률"
  → matched: monthly_churn_rate (owner: growth_team)
  → synonyms: churn, 해지율, monthly churn
  → related: retention_30d, ltv, arpu
  → verified_queries: vq_churn_001, vq_churn_b2b_only

ds semantic trust prod.growth.subscription
  → grade: Gold
  → refresh: daily @04:00 UTC (last: 2026-04-15 04:02)
  → columns: 23 (all with lineage)
  → approved_joins: 4

ds semantic add-nk --topic monthly_churn_rate \
  --wrong "PROMO 고객 포함해 계산" \
  --why "일시적 하락 효과로 평균 이탈률을 저평가" \
  --correct "promo_flag = FALSE 필터 추가"
```

### 10.3 Verified Query 북마크

Electron 사이드바 `Verified SQL Library` 탭:
- metric 별 grouping
- dialect filter
- 사용 횟수 / 최근 사용 일시 표시
- "Try in playground" 버튼 (DuckDB sandbox 로 실행)
- "Submit for re-verification" 버튼 (verification_audit entry 생성)

---

## 11. Skill: `domain-pack-enterprise`

조직별 semantic pack 을 배포하기 위한 skill. 위치: `skills/domain/domain-pack-enterprise/`.

### 11.1 Skill 구조

```
skills/domain/domain-pack-enterprise/
├── SKILL.md
├── pack.yaml                  # pack metadata
├── metrics/*.yaml             # Metric Catalog
├── glossary/*.yaml            # Business Glossary entries
├── trust/*.yaml               # Data Trust seed
├── verified_queries/*.sql     # .sql + frontmatter for VQ metadata
├── calendar/*.yaml
└── README.md
```

### 11.2 `pack.yaml`

```yaml
pack_id: acme_corp_2026_q2
display_name: "ACME Corp Semantic Pack (2026 Q2)"
owner: data_platform_team
version: 1.3.0
dialect_support: [postgres, bigquery]
requires_semantic_layer_schema_version: 6
checksum: "sha256:..."
```

### 11.3 로드 흐름

1. 사용자가 `ds skills load domain-pack-enterprise --pack acme_corp_2026_q2` 실행.
2. Skill 이 `LoadSemanticPackUseCase` 호출.
3. UseCase 가 pack 무결성 (checksum, schema version) 검증 → dry-run diff 출력 → 사용자 승인 → 트랜잭션으로 SQLite 반영.
4. 실패 시 전체 롤백, 성공 시 `decision_log` 에 load 기록.

### 11.4 버전 업그레이드

새 pack 버전 로드 시 기존 metric 과 충돌 (metric_id 동일, definition 상이) 이 발견되면 per-metric 수동 confirm 모드 (old vs new diff 표시). CI 에서 `scripts/validate_metrics.py` 로 pre-deploy 검증 (YAML 스키마, 참조 무결성, dialect 별 SQL lint).

---

## 12. 구현 Phases (TDD)

총 6 phase, 각 phase RED → GREEN → REFACTOR 사이클 준수. 각 phase 완료 시 Quality Gate 전체 통과 확인.

### Phase 1 — Domain Entities & Repository Ports (3h)

**RED**
- `test/unit/domain/test_metric.py` : Pydantic validation (grain enum, typical_range 순서, version ≥ 1)
- `test/unit/domain/test_glossary.py` : synonyms 정규화
- `test/unit/domain/test_trust.py` : TrustGrade 전이 (untrusted → gold 직행 금지 규칙)
- `test/unit/domain/test_verified_query.py` : 파라미터 placeholder/parameters 일치 검증
- `test/unit/domain/test_org_context.py`
- `test/unit/domain/test_semantic_proposal.py` : proposal_type/status 전이, risk/confidence validation
- `test/unit/application/test_ports.py` : Protocol 구조 (mypy)

**GREEN**: `memory/semantic/domain/*.py`, `memory/semantic/application/ports.py`

**REFACTOR**: dataclass → pydantic v2 일관화, shared value object 추출 (`Identifier`, `FqTableName`).

**Quality Gate**: 단위 테스트 커버리지 ≥ 95% (domain layer), `scripts/check_layer_deps.py` 통과 (domain 외부 import 0).

### Phase 2 — SQLite Migration v6 & Repositories (4h)

**RED**
- `test/integration/infrastructure/test_migration_v6.py` : 마이그레이션 up/down, FK/FTS trigger 동작
- `test/integration/infrastructure/test_sqlite_metric_repo.py` : insert/get/search_by_synonym, FTS 쿼리
- `test/integration/infrastructure/test_sqlite_glossary_repo.py` (FTS5)
- `test/integration/infrastructure/test_sqlite_trust_repo.py`
- `test/integration/infrastructure/test_sqlite_vq_repo.py`
- `test/integration/infrastructure/test_sqlite_org_repo.py`
- `test/integration/infrastructure/test_sqlite_proposal_repo.py` : pending/approved/applied round-trip, evidence append-only

**GREEN**: `memory/semantic/infrastructure/sqlite_*.py`, `sqlite_proposal_repo.py`, migration SQL.

**REFACTOR**: 공통 JSON (de)serialization helper, ConnectionProvider 주입.

**Quality Gate**: 커버리지 ≥ 85% (infra), 10k row 기준 synonym search p95 < 50ms, FTS 쿼리 p95 < 100ms.

### Phase 3 — Use Cases & DI Wiring (3h)

**RED**
- `test/unit/application/test_resolve_metric.py` : exact / synonym / fuzzy / no-match 경로
- `test/unit/application/test_find_verified_query.py` : dialect filter, parameter binding
- `test/unit/application/test_check_table_trust.py` : grade 별 정책 결과 (allow/caveat/confirm/block)
- `test/unit/application/test_record_negative_knowledge.py` : 승인 전 pending 상태
- `test/unit/application/test_submit_semantic_proposal.py` : dedupe, confidence threshold, proposal_type 별 risk 기본값
- `test/unit/application/test_review_semantic_proposal.py` : approve/reject/apply 경로, 감사 메타 기록

**GREEN**: `memory/semantic/application/*.py`, `submit_semantic_proposal.py`, `review_semantic_proposal.py`, `apply_semantic_proposal.py`, `app/composition.py` 에 semantic container factory 추가.

**REFACTOR**: 각 UC 의 입력 DTO 추출, 결과 DTO 통일.

**Quality Gate**: application layer 커버리지 ≥ 90%, mypy strict 통과, composition root 외 infra import 0.

### Phase 4 — `semantic_query` Tool & Prompt 통합 (4h)

**RED**
- `test/integration/tools/test_semantic_query.py`
  - case A: exact metric + verified query → kind="verified"
  - case B: metric 있으나 VQ 없음 → kind="metric_synthesized", approved_joins 검증 통과
  - case C: metric 매칭 실패 → kind="inferred" + warning
  - case D: bronze 테이블 포함 → warning 에 bronze 라벨
  - case E: as_of 가 freeze calendar 에 걸침 → calendar_hints 포함
- `test/integration/prompt/test_semantic_context_injection.py`
- `test/integration/agent/test_semantic_hooks.py`
  - case F: metric 질문인데 `sql_tools` 먼저 고르면 `SemanticReadGuardHook` 이 hint/warning 삽입
  - case G: bronze/untrusted table 실행 전 `SemanticTrustHook` 이 approval event 생성
  - case H: verifier pass + parity 확인 후 `SemanticWritebackHook` 이 verified_query proposal 생성

**GREEN**: `tools/semantic_query.py`, `memory/unified_memory.py` 내 semantic section builder, 시스템 프롬프트 patch, `agent/semantic_hooks.py`, runtime proposal event emission.

**REFACTOR**: fallback 경로 `sql_tools` 와의 중복 제거 (`QueryComposer` 공통화).

**Quality Gate**: 전체 tool 계약 테스트 통과, E2E 테스트 (아래 §13) 1~3 통과, 기존 189 test 회귀 없음.

### Phase 5 — Domain Pack Skill & Proposal Inbox (4h)

**RED**
- `test/integration/skills/test_load_semantic_pack.py` : dry-run diff, checksum 실패, schema version mismatch, conflict 해결
- `test/unit/infrastructure/test_yaml_metric_loader.py` : validation, 동일 metric_id 중복 에러
- `test/integration/runtime/test_semantic_proposal_approval.py` : proposal 생성 → ApprovalInbox 적재 → approve/reject/apply round-trip
- `test/integration/channels/test_semantic_proposal_telegram_actions.py` : Telegram inline approve/reject callback 처리

**GREEN**: `skills/domain/domain-pack-enterprise/`, `memory/semantic/infrastructure/yaml_metric_loader.py`, `scripts/validate_metrics.py`, `runtime/semantic_proposal_router.py`, ApprovalInbox/Telegram action adapter.

**REFACTOR**: loader 와 adapter 의 merge 로직, proposal apply 로직 공통화 (§12 phase 6 과 준비).

**Quality Gate**: 샘플 pack 로드/언로드 reversible, CI pre-commit 에 metric 검증 hook 등록, low-risk proposal approve/reject 가 Electron/Telegram/CLI 중 최소 2개 surface 에서 동작.

### Phase 6 — External Adapters (P0/P1) (4h)

**RED**
- `test/integration/adapters/test_postgres_schema_adapter.py` (testcontainers 또는 sqlite 대체)
- `test/integration/adapters/test_dbt_metricflow_adapter.py` (HTTP mock)
- `test/integration/application/test_sync_semantic_source.py` (merge 정책)

**GREEN**: `memory/semantic/infrastructure/adapters/postgres_schema_adapter.py`, `dbt_metricflow_adapter.py`, `sync_semantic_source.py` UC.

**REFACTOR**: adapter 공통 retry/backoff, auth credential 주입 추상화 (이미 `tools/integration_tools.py` 에 있는 것 재사용).

**Quality Gate**: 샘플 Postgres → Trust Registry auto-seed 시나리오 수동 QA 통과, dbt mock sync 재현 가능, 기존 integration_tools 회귀 없음.

> UX (Electron MetricSourcePanel, CLI `ds semantic`) 는 별도 `Docs/enhancement-specs/XX-semantic-ux.md` 또는 본 phase 완료 후 Follow-up 으로 분리 가능.

---

## 13. 테스트 전략

### 13.1 단위 테스트

- 전 entity pydantic validation 경로.
- Use case 의 경계 조건 (공백, grain 불일치, dialect 미지원).
- `SemanticProposal` lifecycle, dedupe, confidence threshold, review metadata.
- 외부 I/O 는 port mock.

### 13.2 통합 테스트

- SQLite migration v6 up/down 반복 가능성.
- FTS5 검색 정확도 (precision/recall small gold set).
- `semantic_query` 전체 경로 (in-memory sqlite).
- proposal queue → approval apply → semantic artifact 반영 경로.

### 13.3 E2E 시나리오

1. **Verified path**: "지난 분기 월간 이탈률 추이 보여줘" → kind=verified, Gold table, caveat 노출.
2. **Synthesized path**: metric 있으나 VQ 없음 → SQL 합성 + approved_join 검증.
3. **Inferred path**: "새 실험 지표 X 를 알려줘" → fallback SQL + 경고 배너.
4. **Bronze escalation**: bronze 테이블 참조 질의 → 사용자 확인 요청 prompt 생성 확인.
5. **Negative knowledge kick-in**: 과거 실패 접근 반복 시 NK 경고 포함.
6. **Pack reload**: v1.2 → v1.3 로드, 충돌 해결 흐름.
7. **Operator approval loop**: agent 가 proposal 생성 → ApprovalInbox/Telegram 에 노출 → 승인 후 glossary / verified query 반영.

### 13.4 회귀

기존 189 tests full run, 새 semantic 테스트는 별도 marker `@pytest.mark.semantic` 로 선택 실행 가능.

### 13.5 성능

- 10k metric + 50k glossary term + 1k table → `resolve_metric` p95 < 30ms, `semantic_context_injection` < 80ms.
- Negative knowledge lookup (topic index) < 5ms.
- pending proposal lookup / apply p95 < 20ms.

### 13.6 계약 테스트 (외부 어댑터)

dbt MetricFlow / Unity Catalog mock 응답 golden file 저장, schema drift 감지 시 실패.

---

## 14. 의존성 및 통합 지점

### 14.1 기존 `domain_kb` 마이그레이션 경로

1. 읽기 호환: `MetricCatalog.resolve()` 가 결과 없음 + `domain_kb.search()` 에서 관련 insight 가 있으면, "legacy insight" 로 분류해 응답에 포함하되 `source=legacy_domain_kb` 로 태깅.
2. 점진적 승격: `scripts/promote_domain_kb.py` 에서 free-text insight → metric/glossary/NK 후보를 LLM 으로 추출 → 사람 승인 후 Semantic Layer 로 이관. 원본은 그대로 보존 (soft-delete 태깅).
3. 일정: Phase 3 완료 이후 promotion 스크립트 초안, Phase 6 완료 이후 기본 ON.

### 14.2 `tools/integration_tools.py` 확장

- 기존 Postgres 커넥션 재사용해 `semantic/infrastructure/adapters/postgres_schema_adapter.py` 구현.
- BigQuery/Snowflake credential 관리는 `integration_tools` 의 credential provider 인터페이스 확장 (환경변수 + keyring).
- 읽기/쓰기 경로 분리: semantic sync 는 읽기 전용, `sql_tools` 는 기존대로 DDL/DML 권한 분리 유지.

### 14.3 `memory/unified_memory.py`

- `build_context(session_id, user_query)` 확장: semantic section 추가.
- 기존 5계층 (Session/Experiment/Code/Domain/Project) 에 "Semantic" 을 6번째 레이어로 편입. `domain` 계층의 일부 기능 (insight) 은 유지, semantic 은 typed counterpart.

### 14.4 Electron IPC

- 신규 IPC 채널: `semantic:lookup-metric`, `semantic:get-trust`, `semantic:get-verified-query`, `semantic:list-calendar-events`.
- 기존 `run-tool` 채널은 유지, 응답 메타에 `semantic_source` 필드 추가 (null | MetricRef).

### 14.5 CLI

- `ds semantic lookup/trust/vq/calendar/nk add` 서브커맨드 신설 (`cli/commands/semantic.py`).
- 기존 `ds chat` 응답 포맷에 semantic badge 출력 옵션.

### 14.6 Runtime / Operator 승인 흐름

- `runtime/approval_store.py` 를 semantic proposal inbox 의 단일 저장소로 재사용한다. proposal 생성 시 `approval_type="semantic_proposal"` 메타와 함께 저장.
- `runtime/coordinator.py` 는 `semantic.proposal.created`, `semantic.proposal.reviewed`, `semantic.proposal.applied` 이벤트를 발행해 Electron / Telegram / digest surface 가 같은 사건을 공유한다.
- Electron `ApprovalInbox` 는 proposal payload diff, evidence, risk, target artifact 를 렌더링하고 approve/reject/apply 액션을 노출한다.
- Telegram operator flow 는 inline callback (`Approve`, `Reject`, `Open Diff`) 로 동일 action token 을 소비한다.
- 모든 review/apply 는 `runtime_event_log.py` 와 `decision_log` 에 이중 기록해 감사를 남긴다.

### 14.7 `domain_kb` / self-improve 공존 전략

- `self_improve/post_project.py` 는 당장 free-text `domain_kb.store_insight()` 를 유지하되, 같은 outcome 에서 semantic candidate 도 함께 생성하도록 확장한다.
- `runtime/memory_query_service.py` 와 `self_improve/memory_hints.py` 는 approved semantic artifact 를 우선 사용하고, `domain_kb` 는 fallback / legacy memory 로만 취급한다.
- `scripts/promote_domain_kb.py` 는 one-shot migration 이 아니라 지속적 승격 파이프라인이다. 새 retrospectives 에서도 후보가 계속 들어온다.
- 결과적으로 `domain_kb` 는 버리지 않고 compatibility layer 로 남기되, 자율형 Agent 의 주된 의미론 grounding 은 Semantic Memory 가 담당한다.

---

## 15. 성공 기준 (DoD)

- [ ] 최소 10 개 metric (Gold 5, Silver 5), 30 개 glossary term, 20 개 테이블 trust, 15 개 verified query 로 seed pack 제공.
- [ ] "이탈률", "MAU", "LTV" 질의에 대해 kind=verified + metric owner + caveat 이 응답에 포함됨 (E2E 테스트 1 통과).
- [ ] bronze/untrusted 테이블이 포함된 쿼리는 반드시 경고 포함 (E2E 테스트 4 통과).
- [ ] Eval Harness 샘플셋에서 metric-like 질문의 95% 이상이 `sql_tools` 전에 `semantic_query` 를 먼저 호출.
- [ ] 성공 실행 또는 실패 회고에서 semantic candidate 가 발생하면 `SemanticProposal` 이 pending 상태로 적재되고, evidence 가 함께 저장된다.
- [ ] ApprovalInbox 또는 Telegram operator 액션으로 proposal approve/reject/apply 가 가능하고, 적용 후 semantic artifact 와 audit log 가 함께 갱신된다.
- [ ] `scripts/check_layer_deps.py` 가 CI 에서 통과 (domain 의 외부 import 0).
- [ ] 기존 189 tests 회귀 0, 신규 semantic tests ≥ 60개, 전체 커버리지 ≥ 85%.
- [x] Domain pack 로드 reversible (dry-run → apply → rollback) 검증.
- [x] Electron MetricSourcePanel 이 Gold metric 에 대해 hover 시 owner/defn/vq 표기.
- [ ] `domain_kb` 기존 데이터 100% 보존, 승격 스크립트 동작.
- [ ] dbt MetricFlow mock sync 시나리오 통과.
- [ ] 문서화: 본 스펙 + operator guide (`Docs/guides/semantic-pack-authoring.md` — 본 스펙 범위 밖).

---

## 16. 리스크 및 롤백

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| FTS5 빌드 옵션 누락 SQLite 환경 | Low | High | 배포 SQLite 빌드에 FTS5 포함 검증, runtime `sqlite3.enable_load_extension` 체크 후 fallback LIKE 검색 경로 제공 |
| Metric 정의가 조직 내부에서도 합의 안됨 | High | High | Pack 로드를 human-in-the-loop 강제, decision_log 기록, 충돌 시 agent 는 두 정의 모두 presenter |
| 외부 Semantic Layer API 변경 | Med | Med | adapter 계약 테스트 + 버전 고정, sync 실패 시 기존 데이터 유지 (merge 의 overwrite=false 기본) |
| 프롬프트 토큰 폭증 | Med | Med | Semantic context 는 relevance top-K + token budget clipping, lazy tool 경로로 전환 |
| LLM 이 semantic_query 대신 sql_tools 호출 bias | Med | High | 시스템 프롬프트 강화 + sql_tools description 에 "Metric 질문이면 semantic_query 를 먼저 쓸 것" 명시 + orchestrator pre-hook 에서 metric 어휘 감지 시 hint injection (단 state machine 아님, LLM 에게 hint 제공만) |
| domain_kb 마이그레이션 중 insight 소실 | Low | High | soft-delete only, 원본 파일 보존, 승격 기록은 audit log |
| Bronze/Untrusted 차단으로 현장 업무 블록 | Med | Med | `allow_untrusted` flag + admin override, 명시적 감사 로그 |
| Agent proposal spam / false promotion | Med | High | dedupe + confidence threshold + risk 기반 human approval + digest batching |
| 승인 지연으로 semantic memory 가 최신 실행을 반영 못함 | Med | Med | low-risk auto-apply 후보 제한 허용, pending proposal digest, stale proposal expiry/review reminder |

### 롤백 전략

- **Phase 1–3 롤백**: migration v6 down, 코드 revert. Semantic Layer 미사용 상태로 원복. `domain_kb` 는 무변화.
- **Phase 4 롤백**: `semantic_query` tool 등록 해제, 시스템 프롬프트 patch revert. `sql_tools` 단독 경로 복귀.
- **Phase 5 롤백**: pack load transaction 단위 롤백, skill 비활성.
- **Phase 6 롤백**: 어댑터 sync 중단, 마지막 성공 snapshot 으로 복원 (sync 전에 `semantic_snapshot` 테이블 스냅샷 유지).

---

## 17. Open Questions

1. **Metric ID namespace 충돌**: 내부 YAML metric 과 dbt / Looker import metric 이 같은 `metric_id` 를 쓸 때 우선순위 정책. 현재 제안: prefix 강제 (`dbt:`, `looker:`, 내부는 prefix 없음). 이게 UX 혼란이 될 수 있음.
2. **정의 변경 감사**: metric definition 이 바뀌면 과거 dashboard 숫자는 재계산이 필요한가? Re-verify 워크플로 스펙은 §5 QA 스펙과 경계가 어디인가?
3. **Verified Query 자동 parameterization**: 사용자가 inline 쿼리를 verified 로 승격할 때 상수 → 파라미터 추출을 자동화할 수준은?
4. **PII 접근 정책 enforcement 위치**: DataTrustRegistry 에서 PII 분류는 하지만 실제 row filter / column mask 는 DB engine 책임인가 agent 책임인가? 단기적으로 DB, 장기적으로 policy-as-code (OPA/Rego) 검토.
5. **다국어 glossary**: 용어 번역을 단일 term 내부에 dict 로 넣을지, locale 별 독립 entry 로 쪼갤지. 초기 단일 entry 로 가되 scale 되면 분리 가능한 schema 유지.
6. **Negative knowledge 유효기간**: 조직 변화로 과거 실패 이유가 더 이상 유효하지 않을 수 있음. `expires_at` 필드 추가 or 주기적 human review workflow?
7. **Metric 합성 쿼리의 correctness 검증**: verified_query 가 없는 metric 에 대해 자동 합성 SQL 이 실제로 metric 정의를 올바르게 반영하는지 검증하는 2차 체크는 어떻게 할 것인가? dbt test 스타일의 invariant 체크를 metric 에 붙일지 (e.g., typical_range 밖이면 fail) 검토 필요.
8. **Low-risk auto-apply 범위**: glossary alias / metric synonym 까지만 자동 적용할지, Silver trust patch 일부까지 허용할지 정책 경계가 필요하다.
9. **Proposal review ownership**: semantic proposal 승인자는 data platform team 인가, metric owner team 인가, 운영 중에는 두 계층 승인 체계가 필요한가?
10. **실행 근거의 충분성**: verified query proposal 로 승격하려면 dashboard parity 1회면 충분한가, 아니면 repeated success + reviewer verdict 조합이 필요한가?

---

본 스펙은 roadmap §2 의 완전 구현 가이드이며, §1 (Architecture Skeleton), §5 (Agent-Operated QA), §7 (Production Intelligence Layer) 스펙과의 경계는 각 해당 문서에서 기술한다.
