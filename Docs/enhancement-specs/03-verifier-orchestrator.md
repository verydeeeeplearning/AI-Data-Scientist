# 03 — Verifier Orchestrator 상세 스펙

> Source: `Docs/ds-agent-enhancement-roadmap.md` §3 (lines 293–413)
> Target: `src/ds_agent/agent/verifier_orchestrator.py`, `src/ds_agent/tools/verifiers/*`, `src/ds_agent/domain/entities/review_verdict.py`, `src/ds_agent/agent/confidence_scorer.py`
> Status: Completed — Phase 0-4 core/tooling landed, LLM-judge-capable narrative/runtime bootstrap + TaskContract DoD integration landed, CLI/Telegram/Electron verifier surfaces + shadow comparison wiring landed. Model-specific judge optimization + initial golden prompt regression landed, Phase 1 full statistical/data fixture matrix is now in place, wider E2E/UI contract coverage has landed, nightly real-judge coverage has landed, and shadow diff-review operations have now landed (2026-04-16)
> Owner: DS Agent Core
> Current status override (2026-04-16): Completed. Shadow diff-review operations are now implemented across tool/CLI/Telegram/API/Electron surfaces, so the planned Verifier Orchestrator scope for this spec is closed.
> Current verification override (2026-04-16): `pytest --basetemp .tmp/pytest_shadow_ops tests/unit/presentation/test_shadow_comparison_presenters.py tests/integration/test_run_verifier_tool.py tests/unit/infrastructure/test_verdict_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/unit/infrastructure/test_task_contract_telegram.py` passed with `25 passed`; `ruff check`, `python -m mypy src/ds_agent/presentation/shadow_comparison_presenters.py src/ds_agent/tools/verifier_tool.py src/ds_agent/cli/verdict_cli.py src/ds_agent/cli/commands.py src/ds_agent/api/routes/task_contracts.py`, Electron `npm run typecheck`, and `npm run test:contract:verifier` passed. Broader `telegram_runner.py` mypy debt remains pre-existing.
> Current implementation override (2026-04-16): Added shadow comparison detail presenters, persisted shadow comparison retrieval/list tools, Task Contract shadow-comparison HTTP routes, CLI `shadow-active` / `shadow-show`, Telegram `/verdict shadow`, Electron IPC/preload/task-contract hook support, and QualityPanel mismatch previews backed by renderer contract tests.
> Latest note (2026-04-16): Nightly real-judge coverage landed with `tests/integration/infrastructure/test_llm_judge_nightly.py` plus a `nightly` pytest marker. The real-provider matrix is gated by `DS_AGENT_RUN_NIGHTLY_REAL_JUDGE=1`, validates OpenAI/Anthropic provider-specific kwargs, and keeps default PR/local runs skipped when provider secrets are absent.
> Verification note (2026-04-16): `pytest --basetemp .tmp/pytest_real_judge_nightly tests/integration/infrastructure/test_llm_judge_nightly.py` yielded `4 skipped` in the default env, and `ruff check` plus targeted `mypy --disable-error-code import-untyped` passed for the new nightly assets.

---

## 구현 진행 기록 (2026-04-16)

- **Phase 0 완료**: `src/ds_agent/domain/entities/review_verdict.py`를 확장해 `CheckResult`, `LayerResult`, `Issue`, `ActionHint`, `ConfidenceBand`, 확장형 `ReviewVerdict`를 도입했다.
- **기존 경로 호환 유지**: legacy `category/result/summary` 기반 `ReviewVerdict` 입력과 기존 TaskContract 저장 흐름은 그대로 유지되며, richer verdict payload를 함께 담을 수 있게 했다.
- **Domain boundary 추가**: `src/ds_agent/domain/dtos/verifier_context.py`에 `VerifierContext`, `VerifierConfig`, `EvidenceRef`를 추가했고, `src/ds_agent/domain/interfaces/verifier_ports.py`에 check/layer/repository/scorer port를 추가했다.
- **TaskContract 연동 보강**: `src/ds_agent/application/dtos/task_contract.py`, `src/ds_agent/application/services/task_contract_usecases.py`가 layered verdict, blocking issue, confidence, action hint, metadata를 수용하도록 확장되었다.
- **Confidence scorer 선행 구현**: `src/ds_agent/agent/confidence_scorer.py`에 layer weight, blocker penalty, legacy fallback, deterministic rationale 생성 로직을 구현했다.
- **Phase 1 core 구현**: `src/ds_agent/infrastructure/verifiers/common.py`, `src/ds_agent/infrastructure/verifiers/statistical.py`, `src/ds_agent/infrastructure/verifiers/data.py`를 추가해 Statistical 10-check, Data 6-check 레이어 어댑터와 공통 aggregation helper를 구현했다.
- **기존 로직 재사용**: Data drift는 기존 `DriftAnalyzer`를 재사용하고, leakage/join 류는 existing harness 관점에 맞게 deterministic check로 재구성했다.
- **Phase 1 테스트 추가**: `tests/unit/infrastructure/verifiers/test_statistical.py`, `tests/unit/infrastructure/verifiers/test_data.py`를 추가해 핵심 pass/warn/fail/skipped 시나리오와 statistical weight aggregation을 고정했다.
- **Phase 1 fixture matrix 확장**: `tests/unit/infrastructure/verifiers/test_statistical.py`, `tests/unit/infrastructure/verifiers/test_data.py`에 leakage / temporal split / baseline / overfitting, schema / freshness / join / referential integrity의 pass-warn-fail matrix를 parameterized로 추가해 threshold 경계 회귀를 넓혔다.
- **Leakage warn/fail 경계 수정**: `src/ds_agent/infrastructure/verifiers/statistical.py`에서 `data_leakage_detection`이 `feature_a~warn` 같은 경고급 상관 신호까지 즉시 fail로 올리던 문제를 수정해, fail-level leakage와 warn-level suspicious correlation을 분리 판정하도록 보정했다.
- **Phase 1 full fixture matrix 완성**: `tests/unit/infrastructure/verifiers/test_statistical.py`, `tests/unit/infrastructure/verifiers/test_data.py`에 subgroup / power / class imbalance / multicollinearity / multiple testing / effect size, null spike / distribution drift의 pass-warn-fail matrix를 추가해 statistical 10-check + data 6-check 전부에 대한 3-case threshold regression을 채웠다. distribution drift는 fake analyzer 기반 threshold fixture로 안정화했다.
- **Phase 2 core 구현**: `src/ds_agent/infrastructure/verifiers/policy.py`, `src/ds_agent/application/services/verifier_orchestrator.py`, `src/ds_agent/infrastructure/persistence/verdict_repo.py`를 추가해 Policy 6-check, async timeout-aware orchestrator, SQLite verdict persistence를 구현했다.
- **Phase 3 bootstrap 구현**: `src/ds_agent/infrastructure/verifiers/narrative.py`에 claim/evidence, causal language, metric citation, recommendation feasibility 기반의 lightweight heuristic narrative verifier를 추가했고, 이번 단계에서 `LLMJudgePort` 기반 scaffold를 연결했다.
- **Phase 4 bootstrap 구현**: `src/ds_agent/infrastructure/verifier_container.py`, `src/ds_agent/tools/verifier_tool.py`를 추가해 `run_verifier`, `get_review_verdict` tool entry를 열었고 `agent/factory.py` tool import list에 연결했다.
- **TaskContract DoD gate 연결**: `src/ds_agent/domain/entities/task_contract.py`, `src/ds_agent/domain/services/task_contract_state_machine.py`에 verifier-aware Definition of Done(`min_result`, `min_confidence_grade`, `require_no_blocking_issues`)를 추가했고, close validator가 최신 orchestrator verdict를 기준으로 완료 가능 여부를 판단하도록 바꿨다.
- **run_verifier → contract persistence 연결**: `src/ds_agent/tools/verifier_tool.py`가 기존 TaskContract를 찾으면 verifier repo에 저장한 verdict와 동일한 `verdict_id`로 contract store에도 review verdict를 기록하도록 확장했다. ad hoc verifier 실행 경로는 fallback contract를 유지한다.
- **Prompt/Presenter surface 보강**: `src/ds_agent/agent/prompt_sections.py`, `src/ds_agent/presentation/task_contract_presenters.py`가 verifier gate와 최신 confidence/blocking issue snapshot을 노출하도록 확장되었다.
- **Phase 3 judge scaffold 구현**: `src/ds_agent/domain/interfaces/verifier_ports.py`에 `LLMJudgePort`를 추가했고, `src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py`에 provider-backed `LLMNarrativeJudge`를 구현했다. judge는 strict JSON payload만 받아 `CheckResult`로 정규화하며, fenced JSON/inline JSON 모두 파싱한다.
- **Narrative safe fallback 연결**: `src/ds_agent/infrastructure/verifiers/narrative.py`가 judge 결과를 우선 사용하되 judge가 실패하거나 일부 check만 돌려줘도 heuristic result로 안전하게 복구하도록 병합 로직과 metadata(`judge_mode`)를 추가했다.
- **Judge structured-output 최적화**: `src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py`, `src/ds_agent/providers/openai_provider.py`를 확장해 provider/model별 prompt profile(`openai_json`, `anthropic_json`, `generic_json`)과 chat kwargs를 분기했다. OpenAI 계열 judge는 JSON mode(`response_format={"type":"json_object"}`)와 reasoning 모델의 low reasoning effort를 사용하고, Anthropic 계열 judge는 `thinking=False`로 JSON 안정성을 우선한다. verdict evidence에는 `judge_prompt_profile`, `judge_prompt_version`도 기록한다.
- **Golden prompt regression set 추가**: `tests/fixtures/verifier_judge/openai_prompt_messages.json`, `tests/fixtures/verifier_judge/anthropic_prompt_messages.json`과 `tests/unit/infrastructure/verifiers/test_llm_judge_adapter.py` snapshot test를 추가해 provider별 prompt drift를 회귀로 고정했다.
- **Runtime wiring 연결**: `src/ds_agent/infrastructure/verifier_container.py`, `src/ds_agent/agent/factory.py`가 active `LLMProvider`를 narrative judge에 주입하도록 확장되었다. 이제 실제 agent runtime에서 `run_verifier`는 provider-backed narrative judge container를 공유한다.
- **Surface wiring 구현**: `src/ds_agent/presentation/verdict_presenters.py`, `src/ds_agent/cli/verdict_cli.py`, `src/ds_agent/gateway/telegram_runner.py`, `electron/src/renderer/components/workflow/QualityPanel.tsx`를 확장해 latest verifier snapshot을 CLI `verdict`, Telegram `/verdict`, Electron QualityPanel에서 공통 포맷으로 노출한다.
- **Shadow-mode comparison wiring 구현**: `src/ds_agent/domain/entities/shadow_comparison.py`, `src/ds_agent/application/services/verifier_shadow_comparator.py`, `src/ds_agent/infrastructure/persistence/shadow_comparison_repo.py`, `src/ds_agent/runtime/verifier_shadow_runtime.py`를 추가했고, `src/ds_agent/application/services/verifier_orchestrator.py`, `src/ds_agent/tools/verifier_tool.py`, `src/ds_agent/agent/core.py`, `electron/src/renderer/components/workflow/QualityPanel.tsx`를 확장해 legacy hook/runtime signal과 verifier verdict의 diff를 저장하고 UI snapshot에 shadow match rate를 노출한다.
- **Wider E2E/UI contract coverage 구현**: `src/ds_agent/application/services/verifier_orchestrator.py`가 narrative layer의 `judge_mode`/judge metadata를 verdict metadata로 승격하도록 보강했고, `tests/unit/infrastructure/test_task_contract_api_routes.py`에 `run_verifier -> TaskContract persistence -> /api/task-contracts/active` 통합 경로를 추가했다. Electron 쪽은 `electron/src/renderer/components/workflow/qualityPanelModel.ts`로 QualityPanel selection/summary 계산을 pure helper로 분리하고 `electron/tests/contract/verifier-quality-panel.spec.ts` plain-node contract test를 추가해 renderer verdict surface 규약을 고정했다.
- **추가 테스트**:
  `pytest tests/unit/infrastructure/verifiers/test_policy.py tests/unit/application/test_verifier_orchestrator.py tests/integration/infrastructure/test_verdict_repo.py` → `9 passed`
  `pytest tests/unit/infrastructure/verifiers/test_narrative.py tests/integration/test_run_verifier_tool.py ...` → `14 passed`
  `ruff check src/ds_agent/infrastructure/verifiers/policy.py src/ds_agent/application/services/verifier_orchestrator.py src/ds_agent/infrastructure/persistence/verdict_repo.py src/ds_agent/infrastructure/verifiers/narrative.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/tools/verifier_tool.py ...` 통과
- **종합 verifier sweep**:
  `pytest tests/unit/domain/test_review_verdict.py tests/unit/domain/test_verifier_ports.py tests/unit/agent/test_confidence_scorer.py tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py tests/unit/infrastructure/verifiers/test_policy.py tests/unit/infrastructure/verifiers/test_narrative.py tests/unit/application/test_verifier_orchestrator.py tests/integration/infrastructure/test_verdict_repo.py tests/integration/test_run_verifier_tool.py` → `37 passed`
  `ruff check` verifier 관련 변경 파일 전체 통과
- **검증 완료**:
  `pytest tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py tests/unit/agent/test_confidence_scorer.py tests/unit/domain/test_review_verdict.py tests/unit/domain/test_verifier_ports.py` → `23 passed`
  `ruff check src/ds_agent/infrastructure/verifiers/... tests/unit/infrastructure/verifiers/...` 통과
  `python -m compileall src/ds_agent/infrastructure/verifiers` 통과
- **TaskContract 연동 검증**:
  `pytest tests/unit/domain/test_task_contract_entity.py tests/unit/domain/test_task_contract_state_machine.py tests/unit/application/test_task_contract_usecases.py tests/unit/presentation/test_task_contract_presenters.py tests/integration/test_run_verifier_tool.py` → `20 passed`
  `ruff check src/ds_agent/domain/entities/task_contract.py src/ds_agent/domain/services/task_contract_state_machine.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/tools/verifier_tool.py src/ds_agent/presentation/task_contract_presenters.py src/ds_agent/agent/prompt_sections.py ...` 통과
  `python -m mypy src/ds_agent/domain/entities/task_contract.py src/ds_agent/domain/services/task_contract_state_machine.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/tools/verifier_tool.py src/ds_agent/presentation/task_contract_presenters.py src/ds_agent/agent/prompt_sections.py` → `Success: no issues found in 7 source files`
- **LLM judge scaffold 검증**:
  `pytest tests/unit/domain/test_verifier_ports.py tests/unit/infrastructure/verifiers/test_llm_judge_adapter.py tests/unit/infrastructure/verifiers/test_narrative.py tests/unit/application/test_verifier_orchestrator.py tests/integration/test_runtime_wiring.py tests/integration/test_run_verifier_tool.py` → `28 passed`
  `ruff check src/ds_agent/domain/interfaces/verifier_ports.py src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py src/ds_agent/infrastructure/verifiers/narrative.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/agent/factory.py ...` 통과
  `python -m mypy src/ds_agent/domain/interfaces/verifier_ports.py src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py src/ds_agent/infrastructure/verifiers/narrative.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/agent/factory.py` → `Success: no issues found in 6 source files`
- **Surface wiring 검증**:
  `pytest tests/unit/presentation/test_task_contract_presenters.py tests/unit/presentation/test_verdict_presenters.py tests/unit/infrastructure/test_verdict_cli.py tests/unit/infrastructure/test_task_contract_telegram.py` → `10 passed`
  `ruff check src/ds_agent/presentation/verdict_presenters.py src/ds_agent/presentation/task_contract_presenters.py src/ds_agent/cli/verdict_cli.py src/ds_agent/cli/main.py src/ds_agent/cli/commands.py src/ds_agent/gateway/telegram_runner.py tests/unit/presentation/test_verdict_presenters.py tests/unit/infrastructure/test_verdict_cli.py tests/unit/infrastructure/test_task_contract_telegram.py` 통과
  `npm run typecheck` (electron/) 통과
  `python -m mypy src/ds_agent/presentation/verdict_presenters.py src/ds_agent/presentation/task_contract_presenters.py src/ds_agent/cli/verdict_cli.py src/ds_agent/cli/main.py src/ds_agent/cli/commands.py` → `Success: no issues found in 5 source files`
- **Shadow wiring 검증**:
  `pytest --basetemp .tmp/pytest_shadow tests/unit/domain/test_verifier_ports.py tests/unit/application/test_verifier_orchestrator.py tests/unit/application/test_verifier_shadow_comparator.py tests/integration/infrastructure/test_shadow_comparison_repo.py tests/integration/test_run_verifier_tool.py` → `12 passed`
  `ruff check src/ds_agent/domain/entities/_id_patterns.py src/ds_agent/domain/entities/shadow_comparison.py src/ds_agent/domain/interfaces/verifier_ports.py src/ds_agent/application/services/verifier_shadow_comparator.py src/ds_agent/application/services/verifier_orchestrator.py src/ds_agent/infrastructure/persistence/shadow_comparison_repo.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/runtime/verifier_shadow_runtime.py src/ds_agent/tools/verifier_tool.py src/ds_agent/agent/core.py src/ds_agent/presentation/verdict_presenters.py tests/unit/domain/test_verifier_ports.py tests/unit/application/test_verifier_orchestrator.py tests/unit/application/test_verifier_shadow_comparator.py tests/integration/infrastructure/test_shadow_comparison_repo.py tests/integration/test_run_verifier_tool.py` 통과
  `python -m mypy src/ds_agent/domain/entities/shadow_comparison.py src/ds_agent/domain/interfaces/verifier_ports.py src/ds_agent/application/services/verifier_shadow_comparator.py src/ds_agent/application/services/verifier_orchestrator.py src/ds_agent/infrastructure/persistence/shadow_comparison_repo.py src/ds_agent/infrastructure/verifier_container.py src/ds_agent/runtime/verifier_shadow_runtime.py src/ds_agent/tools/verifier_tool.py src/ds_agent/agent/core.py src/ds_agent/presentation/verdict_presenters.py` → `Success: no issues found in 10 source files`
  `npm run typecheck` (electron/) 통과
- **Judge optimization + golden regression 검증**:
  `pytest --basetemp .tmp/pytest_judge_unit tests/unit/infrastructure/verifiers/test_llm_judge_adapter.py tests/unit/infrastructure/verifiers/test_narrative.py` → `14 passed`
  `pytest --basetemp .tmp/pytest_run_verifier tests/integration/test_run_verifier_tool.py` → `3 passed`
  `pytest --basetemp .tmp/pytest_runtime_wiring_one tests/integration/test_runtime_wiring.py -k provider_backed_verifier_container -vv` → `1 passed`
  `ruff check src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py src/ds_agent/providers/openai_provider.py tests/unit/infrastructure/verifiers/test_llm_judge_adapter.py tests/unit/infrastructure/verifiers/test_narrative.py` 통과
  `python -m mypy src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py src/ds_agent/providers/openai_provider.py` → `Success: no issues found in 2 source files`
- **Phase 1 fixture matrix 검증**:
  `pytest --basetemp .tmp/pytest_verifier_matrix tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py` → `30 passed`
  `pytest --basetemp .tmp/pytest_statistical_regression tests/unit/infrastructure/verifiers/test_statistical.py` → `16 passed`
  `ruff check src/ds_agent/infrastructure/verifiers/statistical.py tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py` 통과
  `python -m mypy --disable-error-code import-untyped src/ds_agent/infrastructure/verifiers/statistical.py` → `Success: no issues found in 1 source file`
- **Phase 1 full fixture matrix 검증**:
  `pytest --basetemp .tmp/pytest_verifier_matrix_full tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py` → `50 passed`
  `ruff check src/ds_agent/infrastructure/verifiers/statistical.py src/ds_agent/infrastructure/verifiers/data.py tests/unit/infrastructure/verifiers/test_statistical.py tests/unit/infrastructure/verifiers/test_data.py` 통과
  `python -m mypy --disable-error-code import-untyped src/ds_agent/infrastructure/verifiers/statistical.py src/ds_agent/infrastructure/verifiers/data.py` → `Success: no issues found in 2 source files`
- **Wider E2E/UI contract coverage 검증**:
  `pytest --basetemp .tmp/pytest_verifier_surface tests/unit/application/test_verifier_orchestrator.py tests/unit/infrastructure/test_task_contract_api_routes.py` → `11 passed`
  `ruff check src/ds_agent/application/services/verifier_orchestrator.py tests/unit/application/test_verifier_orchestrator.py tests/unit/infrastructure/test_task_contract_api_routes.py` 통과
  `python -m mypy src/ds_agent/application/services/verifier_orchestrator.py` → `Success: no issues found in 1 source file`
  `npm run typecheck` (electron/) 통과
  `npm run test:contract:verifier` (electron/) 통과

---

## 1. 배경 및 문제 정의

### 1.1 현재 상태

DS Agent는 LLM-orchestrator 단일 루프(Hermes-style)로 동작한다. Planner는 LLM 자체이며, 별도의 결정적 워크플로우 엔진이 없다. 이 구조의 장점은 유연성이지만, 단점은 **자기 결론을 체계적으로 반박·검증하는 단계가 존재하지 않는다**는 것이다.

현재 `src/ds_agent/agent/hooks/` 디렉터리에는 26개의 훅이 있고, 그중 검증과 관련된 것들은 다음과 같다.

| 훅 | 역할 | 한계 |
|----|------|------|
| `temporal_join_guard_hook` | 시계열 JOIN에서 future leakage 차단 | 단일 케이스(temporal join) 한정 |
| `query_cost_guard_hook` | 쿼리 비용 초과 방지 | 정책 집행만, 결과 품질 검증 아님 |
| `governance_hooks` | PII/권한 정책 적용 | 정책 위반 탐지에 국한 |
| `self_debug_hook` | 런타임 예외 수정 루프 | 기능 오류, 결론 신뢰도 무관 |
| `ds_workflow_hooks` | EDA/모델링 기본 체크리스트 | 체크리스트 리마인드 수준 |

이 훅들은 "특정 위험을 막는 가드" 수준이다. 통합된 **"skeptical review"** — "이 결론은 진짜로 맞는가?"를 묻고 근거를 체계적으로 검증하는 독립 오케스트레이터는 존재하지 않는다.

### 1.2 문제

1. **결론 품질 미검증**: 모델 성능이 좋아 보여도 data leakage, subgroup instability, baseline도 못 넘는 효과크기 등 근본 이슈를 스스로 찾지 않는다.
2. **Narrative 오염**: LLM이 생성하는 리포트가 근거 없는 단정, 과도한 인과 표현, metric 오인용을 포함할 수 있다.
3. **분산된 검증 지식**: 검증 로직이 여러 훅/툴에 파편화되어 있어 커버리지 추적이 불가능하다.
4. **Confidence 태깅 부재**: 결과물에 신뢰도 레이블이 없어 사용자가 "이거 그대로 믿어도 되나?"를 판단할 수 없다.
5. **Definition of Done 연결 부재**: TaskContract의 definition_of_done과 검증 결과가 연결되지 않아 완료 판정이 자의적이다.

### 1.3 본 스펙의 범위

본 스펙은 4-Layer Verifier Orchestrator를 도입한다. 단, 다음 원칙을 유지한다.

- **LLM-orchestrator 훼손 금지**: Verifier는 LLM 대체가 아니라 LLM의 **관찰 도구**다. verdict 해석과 자동 수정 판단은 LLM이 수행한다.
- **State machine 금지**: Verifier는 순수 함수형 검증 어댑터의 집합이다. pass/warn/fail 후 무엇을 할지는 전적으로 LLM이 결정한다.
- **Typed artifact**: 결과는 `ReviewVerdict`(Pydantic)로 구조화되어 도구 로그, SQLite, UI에 동일하게 사용된다.

---

## 2. 핵심 테제

> **"자기 결론을 체계적으로 깨보는 구조가 없으면, 단일 LLM 루프는 반드시 확신 편향(confirmation bias)에 빠진다."**

따라서 DS Agent는 분석 결론을 내기 **직전**에, 독립된 verifier 집합을 호출해 결론의 통계적·데이터적·정책적·서사적 타당성을 병렬 검증한다. Verifier는 LLM을 대체하지 않는다. LLM은 verdict을 **증거(evidence)**로 받아 최종 판단, 자동 수정, 또는 사용자 에스컬레이션을 선택한다.

4개의 레이어가 필요한 이유:

1. **Statistical** — 결론의 통계적 타당성 (leakage, overfit, power, effect size)
2. **Data** — 결론이 서 있는 데이터의 품질 (schema, freshness, drift)
3. **Policy** — 결론을 전달·저장해도 되는가 (PII, cost, side effects)
4. **Narrative** — 결론이 **서술되는 방식**이 증거와 정합하는가 (claim-evidence alignment)

이 네 레이어는 서로 독립적이며 병렬 실행 가능하다. 하나가 fail이어도 다른 레이어는 계속 실행해 LLM에게 전체 그림을 준다.

---

## 3. 4-Layer 아키텍처 전체 다이어그램

```
┌──────────────────────────────────────────────────────────────────┐
│                  VerifierOrchestrator.run(context)                │
│                                                                    │
│  input:  VerifierContext                                           │
│          ├─ task_contract: TaskContract                            │
│          ├─ artifacts: dict[str, Any] (df, model, report, ...)     │
│          ├─ run_log: list[ExecutionEvent]                          │
│          ├─ evidence_refs: list[EvidenceRef]                       │
│          └─ config: VerifierConfig                                 │
│                                                                    │
│      ┌──────────┬──────────┬──────────┬──────────┐                │
│      ▼          ▼          ▼          ▼                           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐                  │
│  │Stat    │ │Data    │ │Policy  │ │Narrative   │   (parallel)     │
│  │Verifier│ │Verifier│ │Verifier│ │Verifier    │                  │
│  │10 checks│ │6 checks│ │6 checks│ │5 checks    │                  │
│  └────┬───┘ └───┬────┘ └───┬────┘ └──────┬─────┘                  │
│       │        │          │             │                          │
│       └────────┴────┬─────┴─────────────┘                          │
│                     ▼                                              │
│              Aggregator                                            │
│       ├─ ReviewVerdict.from_layer_results(...)                     │
│       ├─ ConfidenceScorer.score(verdict)                           │
│       └─ persist(sqlite, artifacts_dir)                            │
│                     ▼                                              │
│  output: ReviewVerdict                                             │
│          ├─ overall: Literal["pass","warn","fail"]                 │
│          ├─ layers: list[LayerResult]                              │
│          ├─ blocking_issues: list[Issue]                           │
│          ├─ confidence: ConfidenceBand                             │
│          └─ recommended_actions: list[ActionHint]                  │
└──────────────────────────────────────────────────────────────────┘
                     │
                     ▼
        LLM(orchestrator)이 verdict를 관찰
        → 자동 수정 / caveat 첨부 / 중단·에스컬레이션 결정
```

각 Layer는 `LayerResult`를 리턴하고, Aggregator는 이를 병합해 최종 `ReviewVerdict`를 만든다. Layer 내부 체크는 독립 실행이며, 하나가 실패해도 다른 체크는 계속된다(부분 실패 허용).

---

## 4. Layer 1: Statistical Verifier

`src/ds_agent/tools/verifiers/statistical.py`

목표: 분석/모델링 결론의 **통계적 타당성**을 점검한다. 10개 체크 각각은 독립된 함수이며 `CheckResult`를 리턴한다.

### 4.1 공통 입출력

```python
# application port
class StatisticalCheck(Protocol):
    name: str
    version: str
    def run(self, ctx: VerifierContext) -> CheckResult: ...

class CheckResult(BaseModel):
    check_id: str
    status: Literal["pass", "warn", "fail", "skipped", "error"]
    score: float           # 0.0 ~ 1.0
    evidence: dict[str, Any]
    message: str
    remediation_hint: str | None = None
    duration_ms: int
```

### 4.2 Check 1 — Data Leakage Detection

- **목적**: train 세트가 val/test 분포와 겹치거나, 미래 정보가 feature에 섞였는지 탐지.
- **입력**: `artifacts["train_df"]`, `artifacts["val_df"]`, `artifacts["test_df"]`, `task_contract.temporal_column` (optional), `artifacts["feature_pipeline"]` (optional).
- **알고리즘**:
  1. 키 컬럼(primary key, temporal key) 교집합 탐지 → 중복률.
  2. target과 각 feature의 Pearson/Spearman correlation, threshold 0.99 이상은 target leakage 후보.
  3. temporal_column 존재 시 train.max(t) ≥ val.min(t) 검사.
  4. 파이프라인에 fit 대상이 train 분리 전에 전체 데이터로 fit 되었는지 정적 분석(hook payload에서 추적).
- **판정 기준**:
  - `fail`: 키 중복 > 0.5%, 또는 target corr ≥ 0.99 feature 존재, 또는 temporal overlap 탐지.
  - `warn`: 키 중복 0.01%~0.5% 또는 target corr 0.9~0.99.
  - `pass`: 그 외.
- **출력 evidence**: `{"duplicate_key_rate":…, "leaky_features":[…], "temporal_overlap_rows":…}`.

### 4.3 Check 2 — Temporal Split Robustness

- **목적**: 시계열 분할이 한 번의 랜덤 커트에 의존해 과적합되지 않았는가.
- **알고리즘**: `artifacts["model"]`에 대해 rolling-origin(최소 3 fold) 재평가. 각 fold의 주요 metric 분산 계산.
- **판정**: `fail` if max-min metric gap > 30% of mean; `warn` if > 15%; else `pass`.
- **Skip 조건**: non-temporal task로 태깅된 경우.

### 4.4 Check 3 — Subgroup Stability

- **목적**: 전체 metric이 좋아도 특정 subgroup에서 극단적으로 나쁜가.
- **알고리즘**: `task_contract.subgroups` 또는 자동 감지된 범주형 컬럼 기준으로 groupby 후 각 그룹의 metric 계산. Coefficient of variation (CV) = std / mean.
- **판정**: `fail` if any subgroup metric < overall * 0.5, 또는 CV > 0.5; `warn` if CV > 0.3; else `pass`.
- **Evidence**: subgroup별 metric 테이블, 최악 subgroup name.

### 4.5 Check 4 — Baseline Comparison

- **목적**: 모델이 naive baseline(mean/median/mode, persistence, random)을 유의하게 상회하는가.
- **알고리즘**: task type에 따라 naive baseline 자동 생성 → 동일 val set 평가 → McNemar/paired bootstrap 유의성 검정.
- **판정**: `fail` if p > 0.05 또는 lift < 1%; `warn` if lift < 5%; else `pass`.

### 4.6 Check 5 — Power Analysis / Sample Size Adequacy

- **목적**: 결론을 뒷받침할 샘플 수가 충분한가.
- **알고리즘**: 관측된 effect size와 원하는 significance level(0.05), power(0.8)에 대해 required N 계산 (statsmodels `tt_ind_solve_power` 등). 실제 N과 비교.
- **판정**: `fail` if actual < required * 0.5; `warn` if actual < required; else `pass`.

### 4.7 Check 6 — Class Imbalance Impact

- **목적**: 클래스 불균형이 metric을 왜곡하는가.
- **알고리즘**: 클래스 비율 계산. 다수 클래스 예측만으로 달성되는 accuracy와 실제 accuracy 비교. PR-AUC, balanced accuracy, MCC 병행 계산.
- **판정**: `fail` if majority-only accuracy가 실제 accuracy의 95% 이상; `warn` if >= 85%; else `pass`.

### 4.8 Check 7 — Multicollinearity

- **목적**: 상관 높은 feature들로 계수 해석이 불안정한가(선형/로지스틱 모델 해석이 보고서에 포함된 경우).
- **알고리즘**: VIF 계산. 상위 N개의 feature에 대해 VIF > 10 개수 집계.
- **판정**: `fail` if VIF > 10 feature 수 ≥ 3; `warn` if ≥ 1; else `pass`.
- **Skip**: tree/boosting/deep 모델이고 보고서에 선형 계수 해석이 없는 경우.

### 4.9 Check 8 — Overfitting Gap

- **목적**: train-val metric gap이 비정상적으로 큰가.
- **알고리즘**: `abs(train_metric - val_metric) / val_metric`.
- **판정**: `fail` if gap > 0.2 (상대), `warn` if > 0.1, else `pass`.

### 4.10 Check 9 — Multiple Testing Correction

- **목적**: 보고서에 유의성 주장(p-value 언급)이 여러 개일 때, 다중비교 보정이 되어 있는가.
- **알고리즘**: narrative에서 p-value 클레임 개수 N 추출 → Bonferroni/Benjamini-Hochberg 보정 후 유의한 주장 개수 비교.
- **판정**: `fail` if 보정 후 유의 주장이 원래의 50% 이하로 줄고 claim 수정이 없음; `warn` if 줄었지만 일부 유지; else `pass`.

### 4.11 Check 10 — Effect Size & Practical Significance

- **목적**: 통계적 유의 ≠ 실무적 유의. 효과크기가 실무 threshold(`task_contract.min_practical_effect`)를 넘는가.
- **알고리즘**: Cohen's d / Cliff's delta / lift / delta metric 계산.
- **판정**: `fail` if effect size < min_practical_effect; `warn` if < 1.5×; else `pass`.

### 4.12 Layer 1 Aggregation

```python
LayerResult(
  layer="statistical",
  overall=worst(status among 10 checks),  # fail > warn > pass
  checks=[CheckResult, ...],
  score=weighted_avg([c.score * weight(c.check_id) for c in checks]),
)
```

가중치: leakage/temporal/baseline은 2.0, 나머지 1.0. Skip/error는 점수 계산 제외.

---

## 5. Layer 2: Data Verifier

`src/ds_agent/tools/verifiers/data.py`

목표: 결론이 기반하는 **데이터 자체의 품질**을 검증.

### 5.1 Check 1 — Schema Contract Validation

- **목적**: `task_contract.data_schema`에 선언된 컬럼/타입/nullable이 실제 데이터와 일치하는가.
- **알고리즘**: contract schema vs observed dtype diff. pandera 스타일 규칙 지원.
- **판정**: `fail` if 필수 컬럼 누락 또는 타입 불일치; `warn` if optional 누락; else `pass`.

### 5.2 Check 2 — Freshness & SLA Compliance

- **목적**: 데이터 latest timestamp가 SLA 이내인가.
- **알고리즘**: `max(temporal_column)`과 `task_contract.sla.max_staleness` 비교.
- **판정**: `fail` if staleness > sla; `warn` if > 0.8 × sla; else `pass`.

### 5.3 Check 3 — Null/Spike Anomaly

- **목적**: 컬럼별 null ratio, outlier spike가 기존 profile 대비 비정상인가.
- **알고리즘**: `artifacts["data_profile"]`(DataContract §)와 비교. 현재 null ratio가 baseline의 2σ를 초과하는 컬럼 목록.
- **판정**: `fail` if 필수 컬럼에서 >2σ; `warn` if optional; else `pass`.

### 5.4 Check 4 — Join Validity & Cardinality

- **목적**: 쿼리 런로그에서 수행된 JOIN들이 cardinality 가정(1:1, 1:N, M:N)을 지키는가.
- **알고리즘**: `run_log`의 JOIN 단계에서 pre/post row count 비교. 예상 cardinality와 다르면 경고.
- **판정**: `fail` if row count가 N배 이상 불어나 설명 안 됨; `warn` if 5~10% 이상 변동; else `pass`.

### 5.5 Check 5 — Distribution Drift

- **목적**: 학습 데이터와 현재 배치의 feature 분포가 유의미하게 다른가.
- **알고리즘**: 각 feature에 대해 PSI(Population Stability Index) 또는 KS 검정. 임계값: PSI > 0.25 = fail, > 0.1 = warn.
- **Skip**: 학습 분포가 artifact로 저장 안 된 경우.

### 5.6 Check 6 — Referential Integrity

- **목적**: 외래키/참조키의 integrity가 유지되는가.
- **알고리즘**: declared FK 컬럼의 값들이 참조 테이블에 존재하는지 샘플 조회.
- **판정**: `fail` if orphan rate > 1%; `warn` if 0.1%~1%; else `pass`.

---

## 6. Layer 3: Policy Verifier

`src/ds_agent/tools/verifiers/policy.py`

목표: 결과물을 **전달·저장·실행해도 되는가**를 검증. 기존 `governance_hooks`와 `query_cost_guard_hook`의 로직을 흡수한다.

### 6.1 Check 1 — PII Exposure

- **알고리즘**: deliverable payload(결과 테이블, narrative, plots metadata)에 대해 PII detector 실행 — regex(이메일, 전화번호, 주민번호)와 ML-lite 분류기(선택). task_contract.pii_policy (mask | drop | allow) 적용 여부 확인.
- **판정**: `fail` if policy 위반 PII detected; `warn` if masked된 PII가 있으나 masked quality 의심; else `pass`.

### 6.2 Check 2 — Access Scope

- **알고리즘**: run_log의 모든 데이터 소스가 `task_contract.allowed_sources`에 포함되는지, caller의 role이 해당 소스 read scope를 가지는지 확인.
- **판정**: scope 위반 있으면 `fail`.

### 6.3 Check 3 — Cost Budget Compliance

- **알고리즘**: run_log의 토큰·쿼리·스토리지 비용 집계 → task_contract.budget 대비 비교.
- **판정**: `fail` if 초과; `warn` if ≥ 80%; else `pass`. (기존 query_cost_guard_hook 흡수, 범위 확대.)

### 6.4 Check 4 — Risky Action Detection

- **알고리즘**: run_log 중 write/delete/truncate/drop 또는 외부 API 호출 중 destructive 패턴 탐지. task_contract.risk_level에 따라 허용 여부 판정.
- **판정**: `fail` if risk_level이 허용치를 초과; `warn` if 근접; else `pass`.

### 6.5 Check 5 — Retention Policy

- **알고리즘**: 생성되는 artifact 각각에 retention label이 있고, storage target의 retention rule과 호환되는가 검사.
- **판정**: `fail` if retention 라벨 누락 또는 위반.

### 6.6 Check 6 — Write Side-effect Preview

- **알고리즘**: write 계획된 대상에 대해 dry-run preview(예: SQL `EXPLAIN`, S3 put simulation) 결과 첨부. Destructive 성향 점수 산출.
- **판정**: `warn` 기본(사람 확인 권장); policy_engine이 명시적으로 auto-approve면 `pass`.

---

## 7. Layer 4: Narrative Verifier

`src/ds_agent/tools/verifiers/narrative.py`

목표: 최종 보고/응답 **텍스트**가 증거와 정합하는가를 LLM 기반으로 판정.

> 이 레이어는 LLM을 판정자(judge)로 사용한다. 단, judge는 구조화된 입력/출력으로 제한되어 행동 자체를 결정하지 않는다(판정값만 리턴).

### 7.1 Check 1 — Claim-Evidence Alignment

- **입력**: narrative text, `evidence_refs` (artifact_id + 발췌).
- **알고리즘**: narrative에서 atomic claim 추출 → 각 claim에 대해 "지원 증거가 evidence_refs에 존재하는가?"를 LLM 판정. unsupported claim 리스트 반환.
- **판정**: `fail` if unsupported rate > 20%; `warn` if 5~20%; else `pass`.

### 7.2 Check 2 — Overstatement / Hedge Detection

- **알고리즘**: "절대", "명확히", "반드시" 등 강한 단정어를 evidence 강도 대비 과도하게 사용했는지 LLM이 판정. 반대로 실제 강한 증거에 대해 과도한 hedge("may", "might")도 탐지.
- **판정**: imbalance 점수 기반.

### 7.3 Check 3 — Causal Language Appropriateness

- **알고리즘**: "원인", "때문에", "유발" 등 인과 표현이 나올 때, 해당 분석이 실험설계(RCT/quasi-experiment)였는지 확인. 관측데이터에서 인과 단정 시 fail.
- **판정**: observational 분석에서 causal claim → `fail`.

### 7.4 Check 4 — Metric Citation Accuracy

- **알고리즘**: narrative에 인용된 수치(0.87, +12.3% 등)가 artifacts의 실제 metric과 일치하는가 정규식 + 값 매칭. 불일치 시 fail.

### 7.5 Check 5 — Recommendation Feasibility

- **알고리즘**: "~를 하라"는 권고가 있을 때, task_contract.scope 및 알려진 제약(budget, access) 내에서 실행 가능한가를 LLM 판정.
- **판정**: infeasible 권고 비율 기반.

### 7.6 LLM Judge 프롬프트 규약

- System prompt: "You are a skeptical reviewer. Return JSON only."
- Schema: `{claims:[{text,supported:bool,rationale}], overstatements:[...], causal_violations:[...]}`.
- Temperature 0, max tokens 제한, 비용 태깅은 Layer 3에서 다시 검증.

---

## 8. ReviewVerdict 스키마 + SQLite 마이그레이션

### 8.1 Pydantic 모델

`src/ds_agent/domain/entities/review_verdict.py`

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field

Status = Literal["pass", "warn", "fail", "skipped", "error"]
ConfidenceGrade = Literal["high", "medium", "low", "insufficient"]

class CheckResult(BaseModel):
    check_id: str
    layer: Literal["statistical", "data", "policy", "narrative"]
    status: Status
    score: float = Field(ge=0.0, le=1.0)
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    remediation_hint: str | None = None
    duration_ms: int = 0
    version: str = "1.0"

class LayerResult(BaseModel):
    layer: Literal["statistical", "data", "policy", "narrative"]
    overall: Status
    score: float = Field(ge=0.0, le=1.0)
    checks: list[CheckResult]
    duration_ms: int = 0
    partial_failure: bool = False

class Issue(BaseModel):
    check_id: str
    severity: Literal["blocker", "major", "minor"]
    message: str
    remediation_hint: str | None = None

class ActionHint(BaseModel):
    action: Literal["auto_retry", "escalate", "attach_caveat", "abort", "rerun_check"]
    target: str | None = None
    reason: str

class ConfidenceBand(BaseModel):
    grade: ConfidenceGrade
    score: float = Field(ge=0.0, le=1.0)
    rationale: str

class ReviewVerdict(BaseModel):
    verdict_id: str
    task_id: str
    run_id: str
    created_at: datetime
    overall: Status
    layers: list[LayerResult]
    blocking_issues: list[Issue] = Field(default_factory=list)
    confidence: ConfidenceBand
    recommended_actions: list[ActionHint] = Field(default_factory=list)
    schema_version: str = "1.0"
```

### 8.2 SQLite Migration v7

`src/ds_agent/infrastructure/persistence/migrations/007_review_verdict.sql`

```sql
CREATE TABLE review_verdicts (
    verdict_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    overall TEXT NOT NULL,
    confidence_grade TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    confidence_rationale TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);
CREATE INDEX idx_verdicts_task ON review_verdicts(task_id);
CREATE INDEX idx_verdicts_run  ON review_verdicts(run_id);

CREATE TABLE review_check_results (
    verdict_id TEXT NOT NULL,
    check_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    status TEXT NOT NULL,
    score REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (verdict_id, check_id),
    FOREIGN KEY (verdict_id) REFERENCES review_verdicts(verdict_id) ON DELETE CASCADE
);
CREATE INDEX idx_checks_layer_status ON review_check_results(layer, status);
```

`payload_json`은 전체 `ReviewVerdict`의 JSON 직렬화이며, 테이블 정규화는 조회 성능만 위한 보조.

---

## 9. Confidence Scoring 공식

`src/ds_agent/agent/confidence_scorer.py`

### 9.1 계산식

```
layer_weights = {
  "statistical": 0.40,
  "data":        0.25,
  "policy":      0.15,
  "narrative":   0.20,
}

layer_score(L) = weighted_mean(check.score for check in L.checks if status != "skipped")

overall_confidence = sum(layer_weights[L] * layer_score(L) for L in layers)

# 블로킹 이슈 패널티
overall_confidence *= (1 - 0.25 * count_blocker_issues)
overall_confidence = clamp(overall_confidence, 0.0, 1.0)
```

### 9.2 Grade 매핑과 Agent 행동

| Grade | Score | Agent 권장 행동 |
|-------|-------|----------------|
| **high** | 0.80–1.00 | 결과 전달 + next-step 제안. Electron 배지 green. |
| **medium** | 0.50–0.80 | 결과 전달 + caveat 명시 + 리뷰 요청 트리거. 배지 amber. |
| **low** | 0.20–0.50 | 중간 결과만 공유, 에스컬레이션 준비. 배지 orange. |
| **insufficient** | 0.00–0.20 | 결론 중단, 원인 리포트 + 대안 제시. 배지 red. |

### 9.3 Rationale 생성 규칙

`ConfidenceScorer.explain(verdict)`:

1. 최하위 3개 체크를 추출(score 기준).
2. 각 체크에 대해 `f"{check_id}: {message}"` 한 줄 요약.
3. 블로킹 이슈 있으면 앞쪽에 `"blocked by: …"` 접두.
4. 최종 rationale 문자열(한국어) 350자 이내.

LLM 호출 없이 결정적으로 생성 — 재현성 보장. 단, Narrative Layer rationale은 LLM 판정문에서 가져올 수 있음(이미 생성된 텍스트 재사용).

---

## 10. 기존 훅 마이그레이션 표

| 기존 훅 | 대상 Layer/Check | 전략 | 마이그레이션 단계 |
|---------|-----------------|------|------------------|
| `temporal_join_guard_hook` | Statistical C1 (leakage) + Data C4 (join validity) | **흡수 + 확장**. 기존 로직을 두 체크로 분리 재구현. 훅 자체는 deprecation 경고와 함께 1 minor 버전 유지 후 삭제. | Phase 1 |
| `query_cost_guard_hook` | Policy C3 (cost budget) | **흡수**. orchestrator가 실행 중 실시간으로 호출하던 것을 verifier에서 run_log 집계로 대체. 실시간 abort가 필요한 케이스는 훅 유지. | Phase 2 |
| `governance_hooks` | Policy C1/C2/C5 | **연동**. 기존 policy_engine 호출을 verifier adapter 안에서 래핑. 훅은 유지. | Phase 2 |
| `self_debug_hook` | (유지, 독립) | verifier와 별개 — 런타임 예외/traceback 수정용. verdict에 `runtime_errors` 필드로 결과만 전달. | 변경 없음 |
| `ds_workflow_hooks` | Statistical C3/C6/C8, Data C1 | **부분 흡수**. 체크리스트 리마인드 기능은 prompt guidance로 이동, 검증 부분은 verifier로. | Phase 1 |
| 기타 21개 훅 | 해당 없음 | 유지. | — |

**마이그레이션 원칙**:
- 훅을 **먼저 추가로** verifier에서 복제 구현한 뒤 양쪽 결과를 비교(shadow mode) 1주일.
- shadow mode에서 verdict과 훅 결정이 95% 이상 일치하면 훅을 deprecated 처리.
- deprecation 후 1 minor release 동안 경고만 출력하며 로직은 verifier만 사용.
- 그 뒤 훅 삭제.

---

## 11. Clean Architecture 매핑

| Layer | 컴포넌트 | 위치 |
|-------|---------|------|
| **Domain** | `ReviewVerdict`, `LayerResult`, `CheckResult`, `Issue`, `ActionHint`, `ConfidenceBand`, `VerifierContext` (DTO) | `domain/entities/review_verdict.py`, `domain/dtos/verifier_context.py` |
| **Domain Port (interface)** | `StatisticalCheck`, `DataCheck`, `PolicyCheck`, `NarrativeCheck`, `VerdictRepository` | `domain/interfaces/verifier_ports.py` |
| **Application** | `VerifierOrchestratorUseCase`, `ConfidenceScorer`, `VerdictAggregator` | `application/use_cases/verify_result.py` |
| **Infrastructure** | `StatisticalVerifier`, `DataVerifier`, `PolicyVerifier`, `NarrativeVerifier` (adapter), `SqliteVerdictRepository` | `infrastructure/verifiers/*`, `infrastructure/persistence/verdict_repo.py` |
| **Presentation** | Electron QualityPanel 배지, CLI verdict renderer, Telegram 축약 포맷터 | `presentation/renderers/verdict_renderer.py` |

**의존성 검증**:
- `domain/*`는 pydantic 외 외부 의존 없음.
- `application/use_cases/verify_result.py`는 `domain` port만 import, concrete verifier 참조 금지.
- DI는 `infrastructure/config/container.py`에서 port→adapter 바인딩.
- Data가 경계를 넘을 때는 DTO(`VerifierContext`, `ReviewVerdict`)로 전달.

---

## 12. 주요 유스케이스 및 도구

### 12.1 `VerifierOrchestratorUseCase.run(ctx: VerifierContext) -> ReviewVerdict`

의사코드:

```python
class VerifierOrchestratorUseCase:
    def __init__(
        self,
        statistical: StatisticalVerifierPort,
        data: DataVerifierPort,
        policy: PolicyVerifierPort,
        narrative: NarrativeVerifierPort,
        repo: VerdictRepository,
        scorer: ConfidenceScorerPort,
        clock: Clock,
        config: VerifierConfig,
    ): ...

    async def run(self, ctx: VerifierContext) -> ReviewVerdict:
        layers: list[LayerResult] = []
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(self._with_timeout(self.statistical.run(ctx), config.stat_timeout_s))
            t2 = tg.create_task(self._with_timeout(self.data.run(ctx),        config.data_timeout_s))
            t3 = tg.create_task(self._with_timeout(self.policy.run(ctx),      config.policy_timeout_s))
            t4 = tg.create_task(self._with_timeout(self.narrative.run(ctx),   config.narrative_timeout_s))
        for t in (t1, t2, t3, t4):
            layers.append(self._resolve(t))  # exception → LayerResult(overall="error")

        verdict = aggregate(layers, task_id=ctx.task_contract.task_id, run_id=ctx.run_id, now=self.clock.now())
        verdict.confidence = self.scorer.score(verdict)
        verdict.recommended_actions = derive_actions(verdict)
        self.repo.save(verdict)
        return verdict
```

**Timeout 정책**:
- 기본: statistical 60s, data 30s, policy 15s, narrative 45s. config로 override.
- 타임아웃 시 해당 layer는 `overall="error", partial_failure=True`로 기록. 전체 overall은 다른 레이어로 계속 계산.

**부분 실패 처리**:
- 한 체크가 예외 throw → `CheckResult(status="error", score=0.0, message=str(exc))`.
- Layer의 error 체크 비율 > 50%면 `partial_failure=True` 세트. Aggregator가 confidence 점수에서 해당 layer 가중치를 감산.

### 12.2 `@tool run_verifier(scope="all" | "statistical" | "data" | "policy" | "narrative")`

LLM이 호출하는 tool. 엔트리: `src/ds_agent/tools/verifier_tool.py`.

```python
@tool(name="run_verifier")
def run_verifier(scope: str = "all", override_context: dict | None = None) -> ToolResult:
    """
    Execute verifier layers. Returns ReviewVerdict summary (structured).
    """
    ctx = build_verifier_context(session_state, override=override_context)
    verdict = container.verifier_uc.run(ctx)   # sync wrapper
    return ToolResult(
        payload=verdict.model_dump(),
        summary=render_short(verdict),
        artifact_ref=f"verdict:{verdict.verdict_id}",
    )
```

### 12.3 `@tool get_review_verdict(verdict_id: str)`

- 저장된 verdict 조회. Electron/CLI 렌더러가 LLM 경로 외에서도 접근 가능.

### 12.4 재실행/부분 실행

- LLM이 한 레이어만 다시 돌리고 싶을 때 `run_verifier(scope="statistical")`로 호출.
- Aggregator는 기존 verdict의 다른 layer 결과를 유지하며 scope만 덮어쓴 새 verdict_id를 생성(history 보존).

---

## 13. Skeptical Review 프로세스 다이어그램

```
[분석 수렴 시점 — LLM 자체 판단]
           │
           ▼
  LLM이 run_verifier(scope="all") 호출
           │
           ▼
   ┌──────────────────────┐
   │ Verifier Orchestrator │
   │  (4 layers parallel) │
   └──────────┬───────────┘
              │
              ▼
   ReviewVerdict 반환 (tool result)
              │
  ┌───────────┼────────────────────┐
  │           │                    │
  ▼           ▼                    ▼
overall=pass overall=warn      overall=fail
  │           │                    │
  │           │                    ▼
  │           │           LLM은 blocking_issues를 읽음
  │           │                    │
  │           │        ┌───────────┼──────────────┐
  │           │        ▼           ▼              ▼
  │           │   자동 수정      재시도        사용자에게
  │           │   가능 판단?    scope 한정     에스컬레이션
  │           │   (LLM 추론)                    (위험도↑)
  │           │        │
  │           │        └── 수정 후 run_verifier 재호출
  │           ▼
  │   LLM: caveat 문단 추가
  │   + UI: amber 배지
  │   + DeliveryPack에 confidence band 저장
  ▼
 LLM: 결과 요약 + next-step 제안
 + UI: green 배지
 + DeliveryPack 생성
```

**핵심**: 각 분기는 **결정적 자동화가 아니라** LLM의 추론이다. Verifier는 사실을 기록할 뿐이며, LLM이 verdict을 증거로 삼아 다음 행동을 선택한다. 이는 "LLM-orchestrator 보존" 원칙의 구현이다.

---

## 14. UX

### 14.1 Electron — QualityPanel 확장

`frontend/src/components/workflow/QualityPanel.tsx` 확장.

- 상단 요약: 큰 배지(High/Medium/Low/Insufficient) + confidence score(0.xx).
- 4 layer 탭: Statistical / Data / Policy / Narrative. 각 탭에 체크 리스트.
- 각 체크 행: status 아이콘(green/amber/red), 메시지, evidence 토글(JSON tree), remediation_hint.
- Blocking Issues 영역: severity 정렬된 카드, 각 카드에 "Run auto-fix" 버튼 — 클릭 시 LLM에 action hint를 제안만 함(최종 실행은 LLM).
- 배지 색상 매핑: high→#2E7D32, medium→#F9A825, low→#EF6C00, insufficient→#C62828.

### 14.2 CLI — Verdict Summary

명령: `dsa verdict show <verdict_id>` 또는 실행 직후 자동 출력.

```
Verdict: pass  |  Confidence: HIGH (0.87)
  statistical  pass   10/10 checks  (leakage ok, baseline +12%)
  data         warn    5/6 checks  (drift PSI=0.18 on feat_x)
  policy       pass    6/6 checks
  narrative    pass    5/5 checks
Rationale: drift on feat_x slightly above 0.1 but within tolerance.
```

`--verbose` 플래그로 체크별 message + remediation 출력.

### 14.3 Telegram — 축약형

```
[PASS / HIGH 0.87]
S pass D warn(1) P pass N pass
note: drift PSI=0.18 feat_x
```

1.5KB 이내. detail 링크(Electron deep-link) 동봉.

---

## 15. 구현 Phases (TDD)

본 기능은 **Medium (4-5 phases)** 규모.

### Phase 0 — Domain & Port (선행, 2h)

**Status (2026-04-16): 완료**

**RED**
- `tests/unit/domain/test_review_verdict.py`: Pydantic 검증, confidence grade boundary.
- `tests/unit/domain/test_verifier_ports.py`: port contract (Protocol) 스모크.

**GREEN**
- `domain/entities/review_verdict.py`
- `domain/interfaces/verifier_ports.py`
- `domain/dtos/verifier_context.py`

**REFACTOR**
- Pydantic config, model_validator 정리.
- legacy `ReviewVerdict` payload와 TaskContract review 기록 경로를 깨지 않도록 backward-compatible 정규화 추가.

**Quality Gate**: domain import graph에 외부 패키지(Pydantic 제외) 없음을 ruff + 커스텀 import-linter로 검증.

### Phase 1 — Statistical Verifier + Data Verifier 기본(3h)

**Status (2026-04-16): core 구현 + full statistical/data fixture matrix 완료**
- `src/ds_agent/infrastructure/verifiers/statistical.py`: 10개 check + weighted layer aggregation 반영.
- `src/ds_agent/infrastructure/verifiers/data.py`: 6개 check + drift analyzer 연동 반영.
- `src/ds_agent/infrastructure/verifiers/common.py`: DataFrame coercion, safe-run wrapper, layer aggregation helper 추가.
- `tests/unit/infrastructure/verifiers/test_statistical.py`, `tests/unit/infrastructure/verifiers/test_data.py`: representative scenario coverage에 더해 statistical 10-check + data 6-check 전체의 pass-warn-fail matrix 추가.
- `src/ds_agent/infrastructure/verifiers/statistical.py`: leakage warn-level suspicious correlation과 fail-level hard leakage를 분리하도록 판정 경계 수정.
- `tests/unit/infrastructure/verifiers/test_data.py`: distribution drift는 fake analyzer 기반 threshold fixture로 고정해 flaky PSI 회귀를 피했다.
- 완료: diff-review 운영 기준 정리와 wider integration/E2E coverage를 구현했다.

**RED**
- `tests/integration/test_verifier_orchestrator.py` — wider orchestrator parallel/partial-failure integration coverage.
- `tests/e2e/test_verdict_ui_contract.py` — Electron verdict surface contract.

**GREEN**
- `infrastructure/verifiers/statistical.py` — 10 체크.
- `infrastructure/verifiers/data.py` — 6 체크.

**REFACTOR**
- 공통 `BaseCheck` 추출, duration 계측 decorator.

### Phase 2 — Policy Verifier + Orchestrator + Aggregator(3h)

**Status (2026-04-16): core 구현 완료 + TaskContract close-path 연동 완료**
- `src/ds_agent/infrastructure/verifiers/policy.py`: 6개 policy check 구현.
- `src/ds_agent/application/services/verifier_orchestrator.py`: async 병렬 실행, layer timeout/error folding, blocking issue/action derivation 구현.
- `src/ds_agent/infrastructure/persistence/verdict_repo.py`: SQLite verdict persistence 구현.
- `tests/unit/application/test_verifier_orchestrator.py`, `tests/unit/infrastructure/verifiers/test_policy.py`, `tests/integration/infrastructure/test_verdict_repo.py` 추가.
- `src/ds_agent/domain/entities/task_contract.py`, `src/ds_agent/domain/services/task_contract_state_machine.py`에서 verifier confidence / blocking issue 기준을 TaskContract close-path에 연결했다.
- 완료: wider layer fixture matrix.

**RED**
- `tests/integration/test_verifier_orchestrator.py` — 4 layer mock으로 병렬 실행, timeout, 부분실패 3 시나리오.
- `tests/unit/application/test_confidence_scorer.py` — 경계점, blocker penalty.

**GREEN**
- `infrastructure/verifiers/policy.py`
- `application/use_cases/verify_result.py` (VerifierOrchestratorUseCase)
- `agent/confidence_scorer.py`
- `infrastructure/persistence/verdict_repo.py` + migration v7.

**REFACTOR**
- Timeout handling 공통화.

### Phase 3 — Narrative Verifier + LLM Judge(3h)

**Status (2026-04-16): heuristic + LLM judge optimization + golden prompt regression + nightly real-judge coverage 구현**
- `src/ds_agent/infrastructure/verifiers/narrative.py`에 heuristic narrative verifier를 먼저 추가했다.
- `src/ds_agent/domain/interfaces/verifier_ports.py`: `LLMJudgePort` 추가.
- `src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py`: provider-backed `LLMNarrativeJudge` 추가. strict JSON validation, fenced JSON 파싱, compact prompt payload builder 포함.
- `src/ds_agent/infrastructure/verifiers/llm_judge_adapter.py`, `src/ds_agent/providers/openai_provider.py`: provider/model별 prompt profile과 chat kwargs(JSON mode, low reasoning effort, `thinking=False`) 최적화 추가.
- `tests/unit/infrastructure/verifiers/test_narrative.py`, `tests/unit/infrastructure/verifiers/test_llm_judge_adapter.py`: heuristic fallback, judge 우선 병합, invalid JSON reject, provider-specific prompt/kwargs, golden snapshot contract를 고정했다.
- `tests/fixtures/verifier_judge/openai_prompt_messages.json`, `tests/fixtures/verifier_judge/anthropic_prompt_messages.json`: prompt snapshot fixture 추가.
- 완료: wider fixture matrix.

**RED**
- LLM judge를 `LLMJudgePort`로 추상화하고 fake judge로 5 체크 테스트.
- Golden prompt snapshot test.

**GREEN**
- `infrastructure/verifiers/narrative.py`
- `infrastructure/verifiers/llm_judge_adapter.py`

**REFACTOR**
- JSON schema validator 분리.

### Phase 4 — Tool 통합 + UI + Migration(3h)

**Status (2026-04-16): runtime-capable tool + verifier surface + shadow comparison wiring + wider E2E/UI contract coverage + shadow diff-review operations 구현**
- `src/ds_agent/tools/verifier_tool.py`: `run_verifier`, `get_review_verdict` 추가.
- `src/ds_agent/infrastructure/verifier_container.py`: scorer/verifier/repo/orchestrator composition root 추가.
- `src/ds_agent/agent/factory.py`: verifier tool module import wiring + provider-backed verifier container 주입 추가.
- `tests/integration/test_run_verifier_tool.py`: persisted verdict round-trip + existing TaskContract persistence 추가.
- `run_verifier`가 기존 TaskContract를 찾으면 동일 verdict id로 contract review history까지 갱신하도록 연결했다.
- `tests/integration/test_runtime_wiring.py`: create_agent가 provider-backed verifier container를 실제로 주입하는 wiring을 고정했다.
- `src/ds_agent/presentation/verdict_presenters.py`: latest/effective verdict selection, compact snapshot, CLI/Telegram multiline formatter 추가.
- `src/ds_agent/cli/verdict_cli.py`, `src/ds_agent/cli/commands.py`, `src/ds_agent/cli/main.py`: `ds-agent verdict ...` 및 interactive `/verdict` 추가.
- `src/ds_agent/gateway/telegram_runner.py`: `/verdict [verdict_id]` command, help/menu/bot-command surface 추가.
- `electron/src/renderer/components/workflow/QualityPanel.tsx`: latest result/confidence/blockers/judge_mode/layer status 표시 추가.
- `src/ds_agent/domain/entities/shadow_comparison.py`, `src/ds_agent/application/services/verifier_shadow_comparator.py`, `src/ds_agent/infrastructure/persistence/shadow_comparison_repo.py`, `src/ds_agent/runtime/verifier_shadow_runtime.py`: legacy hook/runtime signal vs verifier verdict diff log와 shadow match-rate persistence 추가.
- `src/ds_agent/application/services/verifier_orchestrator.py`, `src/ds_agent/tools/verifier_tool.py`, `src/ds_agent/agent/core.py`: runtime run_log capture, shadow comparison 저장, verdict metadata(`shadow_match_rate`, `shadow_mismatch_count`, `shadow_comparison_id`) 주입 추가.
- `src/ds_agent/application/services/verifier_orchestrator.py`: narrative layer `judge_mode`/judge metadata를 최종 verdict metadata로 승격해 QualityPanel/CLI/TaskContract surface에서 실제 runtime verdict 기준 judge 상태를 읽을 수 있게 했다.
- `tests/unit/infrastructure/test_task_contract_api_routes.py`: `run_verifier -> TaskContract persistence -> /api/task-contracts/active` 계약 테스트를 추가해 Electron/IPC가 소비하는 verdict metadata(`judge_mode`, shadow fields, layer metadata)가 실제 API payload에 남는지 고정했다.
- `electron/src/renderer/components/workflow/qualityPanelModel.ts`, `electron/tests/contract/verifier-quality-panel.spec.ts`, `electron/tsconfig.contract-test.json`, `electron/package.json`: QualityPanel verdict selection/summary 계산을 pure helper로 분리하고 plain-node renderer contract test + dedicated npm script를 추가했다.
- 완료: shadow diff 운영 기준 문서화 및 diff-review operations 구현.

**RED**
- `tests/integration/test_run_verifier_tool.py` — active session/context builder까지 포함한 end-to-end wiring.
- `electron/tests/contract/verifier-quality-panel.spec.ts` — Electron QualityPanel verdict selection/summary contract.

**GREEN**
- `tools/verifier_tool.py`, `get_review_verdict` tool.
- `run_verifier` → SQLite verdict persistence + TaskContract review history 동기화.
- `create_agent` → provider-backed verifier container 공유.
- prompt/task contract presenter에 verifier snapshot 노출.

**REFACTOR**
- Docs(CHANGELOG), deprecation warning 추가.

각 Phase 종료 시 Quality Gate(TDD 준수, ruff, mypy, coverage ≥ 80%, clean-arch 검증) 통과 필수.

---

## 16. 테스트 전략

### 16.1 단위 — 체크별 Fixture

- 각 체크에 대해 `(context, expected_status, expected_evidence_subset)` 3-case (pass/warn/fail) 최소.
- 수치 체크는 parameterized 경계값 테스트: threshold에서 ±epsilon.

### 16.2 통합 — Gold Verdict Dataset

- `tests/fixtures/verdicts/`에 20개 대표 시나리오(clean, leakage, drift, PII leak, overstatement…) 준비.
- 각 시나리오는 `VerifierContext` 직렬화 + 기대 `ReviewVerdict`(핵심 필드만). regression test로 사용.

### 16.3 Mutation Testing

- `mutmut` 또는 `cosmic-ray`로 statistical/data verifier의 판정 로직에 mutation 적용.
- 목표: 판정 로직에서 surviving mutant < 10%.

### 16.4 Property-based

- `hypothesis`로 CheckResult score가 0~1, layer score가 checks score의 weighted mean 범위 내임을 보장.

### 16.5 LLM Judge 테스트

- Narrative Layer에 대해 fake judge + real judge 양쪽.
- Real judge 테스트는 nightly 전용(비용 고려), fake는 PR 기본.

### 16.6 Coverage 목표

| 영역 | 커버리지 |
|------|---------|
| domain/ | 100% |
| application/use_cases/verify_result.py | ≥ 95% |
| infrastructure/verifiers/* | ≥ 90% |
| tools/verifier_tool.py | ≥ 85% |

### 16.7 성능 테스트

- 500MB 데이터, 50개 feature, 100k row 기준 orchestrator end-to-end p95 ≤ 8s.

---

## 17. 의존성 및 통합 지점

### 17.1 내부 모듈

- **TaskContract** (spec 01): `definition_of_done` 필드에 명시된 verifier 기준(예: `require.leakage = pass`, `require.confidence_grade >= medium`)이 충족되면 task 완료로 간주. Orchestrator가 verdict을 TaskContract 검증기에 전달.
- **DataContract** (spec 02): schema/profile이 Data Verifier의 baseline.
- **EvidenceRef / DeliveryPack** (spec 05): verdict_id가 DeliveryPack에 embedded.
- **policy_engine** (spec 06): Policy Verifier의 rule 소스.
- **session_state / artifacts**: run_log, artifacts dict 제공.

### 17.2 외부 의존

- `pydantic>=2.5` (domain)
- `statsmodels`, `scikit-learn`, `scipy` (statistical checks)
- `pandera` 또는 자체 schema validator (data checks)
- LLM SDK(기존 사용 중인 것) — narrative judge
- `asyncio` + `anyio` (optional) — 병렬 실행

### 17.3 이벤트/로그

- Verdict 생성 시 `VerdictCreatedEvent`를 run bus에 emit.
- Electron은 WebSocket으로 subscribe, UI 실시간 업데이트.

### 17.4 기존 훅과의 런타임 공존

- Phase 2~4 동안 shadow mode: 훅 실행 결과와 verdict 판정을 비교해 diff log를 저장. diff rate < 5% 유지가 마이그레이션 기준.

---

## 18. 성공 기준 (Definition of Done)

| 항목 | 목표 |
|------|------|
| Leakage false negative rate | ≤ 5% (gold dataset 기준) |
| Leakage false positive rate | ≤ 10% |
| Drift detection p95 latency | ≤ 2s |
| Orchestrator end-to-end p95 | ≤ 8s (기준 workload) |
| Narrative judge JSON parse success | ≥ 99% |
| Verdict 저장 성공률 | 100% (DB 장애 시 fallback file write) |
| Confidence grade 분포 | 첫 2주 실사용에서 high 40~70%, insufficient < 5% |
| 기존 훅 shadow diff rate | < 5%에 도달 후 deprecation |
| Coverage | 위 §16.6 목표 |
| Ruff/mypy/clean-arch lint | 0 error |

추가: UX — Electron QualityPanel 사용성 테스트(5명 내부 베타)에서 "verdict 이해 가능" 응답 ≥ 80%.

---

## 19. 리스크 및 롤백

| 리스크 | 확률 | 영향 | 완화책 | 롤백 |
|--------|------|------|--------|------|
| Narrative judge LLM 비용 증가 | 높음 | 중 | temperature 0, max tokens 제한, sample 기반 claim 추출(최대 20개), narrative scope 옵션 | narrative layer off flag (`config.narrative.enabled=false`)로 즉시 차단 |
| Verifier 실행이 분석 체감 속도 저하 | 중 | 중 | 병렬화, scope 옵션, 비-차단(background) 실행 모드 | config로 sync→async 전환, auto-run 비활성화 |
| 기존 훅과 판정 충돌 | 중 | 중 | shadow mode 1주일, diff 리뷰 | 훅 유지, verifier는 권고 전용으로 strict 모드만 끔 |
| Statistical 체크가 비정형 분석에 오탐 | 높음 | 중 | task_contract.task_type에 따라 skip 조건 명확화 | skip rule 확장 또는 해당 체크 disable |
| SQLite verdict 테이블 크기 폭증 | 저 | 저 | 90일 보관 후 cold storage export | 회수 스크립트로 truncate |
| Electron UI 과도 정보로 혼란 | 중 | 저 | 기본 접힘, 디테일은 클릭 시 | 구버전 패널 flag |
| Clean Arch 위반(adapter에서 도메인 변형) | 저 | 고 | import-linter CI | PR 차단 |

**전체 롤백**: config flag `verifier.enabled=false` 한 줄로 orchestrator 자체를 off하고, LLM tool 목록에서 `run_verifier` 제거. 기존 훅들은 그대로 동작.

---

## 20. Open Questions

1. **Narrative Layer LLM 모델 선택**: orchestrator와 동일 모델을 써야 self-judge bias가 생길 수 있음. 별도의 cheaper/different 모델을 판정자로 고정할지?
2. **Gold verdict dataset 유지보수**: 체크 로직이 진화하면 gold 기대값도 변해야 함. 자동 업데이트 워크플로우 필요?
3. **Subgroup 자동 감지 규칙**: task_contract에 subgroup이 없을 때 어디까지 자동 추정할지(카디널리티 상한, 민감컬럼 제외 등)?
4. **Drift baseline 공급자**: DataContract에서 baseline을 항상 받을 수 있다고 가정 가능한가? 없을 때 skip vs heuristic?
5. **Auto-fix action의 책임 경계**: LLM이 "이 blocking issue는 내가 고칠 수 있다"고 판단해 자동 수정 루프를 돌 때, 재실행 횟수 상한과 비용 cap은 어디에 두나 — task_contract vs verifier config?
6. **Write side-effect preview**의 실행 비용: dry-run 비용이 실제 write 대비 너무 클 수 있음. sampling 전략?
7. **Confidence grade 분포가 기대와 다르면** (예: 대부분 low): threshold 재조정 주기/거버넌스?
8. **Multi-tenant 환경**에서 정책 규칙 격리: Policy Verifier가 tenant별 rule set을 어떻게 로드할지 (향후 Phase)?
9. **Shadow mode diff 기준 5%**는 경험치. 실측 후 완화/강화?
10. **Narrative Verifier가 결국 LLM self-review가 되는 문제**: second-pass independent judge가 실무적으로 충분히 critical한지, 아니면 human-in-the-loop 최소 1회를 병행해야 하는지?

---

*End of spec 03.*
