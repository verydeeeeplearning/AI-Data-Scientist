# A03 — Contract & Schema Auditor

**Tier**: 1  
**Duration**: 453 sec  
**Status**: fail  
**Code SHA**: unavailable (`.git` metadata absent in workspace)  
**Code Snapshot ID**: `fd5e256bf0e1f349087e1e28c78adf187a87dc848e67373315aef274b7bd4a6e`  
**Dependencies**: `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md`

## 1. Scope

- `src/ds_agent/tools/*.py` 전체 `@tool` 정의 AST 스캔 + import/registry/schema 감사
- `src/ds_agent/agent/factory.py` 기준 hook registry 30개 시그니처 감사
- `src/ds_agent/api/ws_handler.py` `_METHOD_MAP` 80개 RPC 메서드 감사
- `src/ds_agent/config`, `src/ds_agent/application/dtos`, `src/ds_agent/domain/*`, `src/ds_agent/api/routes` 내 Pydantic 모델 감사

## 2. Methodology

1. `.tmp/qa_A03/a03_contract_audit.py`로 정적 매트릭스 생성
2. Tool 계약 검증:
   - AST 기준 `@tool` 정의 86개 수집
   - 모듈 import 성공 여부 확인
   - 등록된 tool schema를 `jsonschema`로 검증
   - handler 시그니처와 schema properties/required 일치 여부 확인
3. Hook 계약 검증:
   - `build_hook_registry()`로 등록된 30 hook 수집
   - `ToolHook` base lifecycle signature와 override 호환성 확인
4. WebSocket 계약 검증:
   - `_METHOD_MAP` 80개 키 전수 수집
   - handler async 여부 및 `(self, params)` 시그니처 확인
5. Pydantic 계약 검증:
   - 대상 패키지 BaseModel 156개 수집
   - `model_json_schema()` 생성 및 schema 자체 유효성 확인
6. 테스트 교차검증:
   - `pytest tests/unit/infrastructure/test_cli_main.py::TestImportTools::test_import_tools_no_crash tests/unit/infrastructure/test_telegram_runner.py::TestTelegramImportTools::test_import_tools_does_not_crash tests/unit/infrastructure/test_tool_registry.py`
   - `pytest tests/integration/test_all_tools_registered.py tests/integration/test_registry_with_tools.py tests/e2e/test_ws_e2e.py tests/unit/infrastructure/test_config.py tests/unit/domain`
   - `pytest tests/unit/infrastructure/test_agent_session_registry.py`

## 3. Results Matrix

| Area | Count | Pass | Fail | Notes |
|------|------:|-----:|-----:|------|
| Tool contracts | 86 | 75 | 11 | `learning_tools.py`, `portfolio_tools.py` import 실패 |
| Hook signatures | 30 | 30 | 0 | duplicate name 없음 |
| WS RPC methods | 80 | 80 | 0 | `_METHOD_MAP` 계약 정상 |
| Pydantic models | 156 | 156 | 0 | schema generation / validation 정상 |
| Pytest import suite | 12 | 11 | 1 | CLI tool import 실패 재현 |
| Pytest contract suite | 273 | 271 | 2 | E2E stub signature drift |
| Pytest agent session registry | 14 | 14 | 0 | `authority_mode` 전달 계약 정상 |

**Tier 1 gate verdict**: `fail`

근거:

- tool contract fail 11건이 존재함
- 관련 pytest suite 2개가 red 상태임

## 4. Failures and Anomalies

### F1. Bare `@tool` usage로 tool import 자체가 깨짐

재현 위치:

- `src/ds_agent/tools/learning_tools.py:42`
- `src/ds_agent/tools/learning_tools.py:108`
- `src/ds_agent/tools/learning_tools.py:169`
- `src/ds_agent/tools/learning_tools.py:200`
- `src/ds_agent/tools/learning_tools.py:225`
- `src/ds_agent/tools/learning_tools.py:251`
- `src/ds_agent/tools/portfolio_tools.py:38`
- `src/ds_agent/tools/portfolio_tools.py:69`
- `src/ds_agent/tools/portfolio_tools.py:139`
- `src/ds_agent/tools/portfolio_tools.py:196`
- `src/ds_agent/tools/portfolio_tools.py:240`

관찰:

- 현재 `src/ds_agent/tools/registry.py`의 `tool()` decorator는 `name`, `description`을 필수 인자로 요구함
- 위 11개 함수는 bare `@tool`을 사용하므로 import 시 `TypeError: tool() missing 1 required positional argument: 'description'` 발생
- `src/ds_agent/cli/main.py:156`의 `_import_tools()`는 `ds_agent.tools.portfolio_tools`, `ds_agent.tools.learning_tools`를 실제로 import 하므로 CLI surface에서 계약 위반이 실사용 경로로 노출됨

재현 증거:

- `pytest_import_tools.log`
- `junit_import_tools.xml`
- `A03_contract_matrix.csv`

영향:

- Tool registry 전수 계약이 깨짐
- 문서 주장치(`76 tools`)와 실제 import 가능한 registry 엔트리(`75`)가 불일치

### F2. WebSocket chat E2E test double이 `authority_mode` 계약을 반영하지 못함

재현 위치:

- `tests/e2e/test_ws_e2e.py:338`
- `tests/e2e/test_ws_e2e.py:378`
- `src/ds_agent/api/agent_session_registry.py:102`

관찰:

- `AgentSessionRegistry._create_agent()`는 현재 keyword-only `authority_mode`를 받음
- E2E test는 `lambda session_id, callbacks, model=None: mock_agent`로 monkeypatch 해서 새 kwarg를 받지 못함
- 결과적으로 `tests/e2e/test_ws_e2e.py::TestChatE2E::{test_chat_send_returns_session_and_done,test_chat_history_after_send}` 2건 실패
- 반면 `tests/unit/infrastructure/test_agent_session_registry.py`는 14/14 green이며 `authority_mode` 전달 계약을 명시적으로 검증함

판정:

- 현재 신호는 **제품 계약 drift라기보다 E2E 테스트 더블 drift**에 가깝다
- 하지만 Tier 1 기준에서는 red test이므로 fail로 기록해야 함

재현 증거:

- `pytest_contract_suite.log`
- `junit_contract_suite.xml`
- `pytest_agent_session_registry.log`
- `junit_agent_session_registry.xml`

### A1. QA plan 수치 드리프트

관찰:

- 계획 문서는 `76 tool schema / 30 hook / 80 WS RPC`를 전제로 함
- 실제 감사 결과는 `86 decorated tool functions / 75 importable registry entries / 30 hooks / 80 WS RPC`

판정:

- `hook`과 `WS RPC` 수치는 문서와 일치
- `tool` 수치는 문서-코드 드리프트가 존재하며, F1 해결 없이는 canonical count를 확정할 수 없음

## 5. Evidence Index

- `Docs/qa_run_2026-04-17/A03_contract_schema/START.json`
- `Docs/qa_run_2026-04-17/A03_contract_schema/A03_contract_matrix.csv`
- `Docs/qa_run_2026-04-17/A03_contract_schema/A03_contract_summary.json`
- `Docs/qa_run_2026-04-17/A03_contract_schema/pytest_import_tools.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema/junit_import_tools.xml`
- `Docs/qa_run_2026-04-17/A03_contract_schema/pytest_contract_suite.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema/junit_contract_suite.xml`
- `Docs/qa_run_2026-04-17/A03_contract_schema/pytest_agent_session_registry.log`
- `Docs/qa_run_2026-04-17/A03_contract_schema/junit_agent_session_registry.xml`

## 6. Recommendations

1. `learning_tools.py`, `portfolio_tools.py`의 11개 bare `@tool` usage를 현재 registry 계약에 맞게 명시형 `@tool(name=..., description=...)`로 수정하거나, decorator가 bare usage를 지원하도록 설계를 일관화해야 함.
2. `tests/e2e/test_ws_e2e.py`의 `_create_agent` monkeypatch lambda를 `authority_mode` kwarg까지 받도록 갱신해야 함.
3. F1 수정 후 canonical tool count를 다시 산출하고 `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md`의 `76 tools` 수치를 동기화해야 함.
4. Release gate 관점에서 현 상태는 Tier 1 hard gate 미통과이므로 Tier 2 진입 금지 상태로 기록해야 함.
