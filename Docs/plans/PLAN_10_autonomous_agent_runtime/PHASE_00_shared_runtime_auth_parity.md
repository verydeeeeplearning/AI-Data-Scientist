# Phase 00: Shared Runtime Context + Auth Parity

**Priority**: P0  
**Estimated**: 3~4일  
**Milestone**: A

---

## 0. 구현 상태

**Status**: In Progress  
**Last Updated**: 2026-04-12

이번 구현 패스에서 완료된 항목:

- [x] `src/ds_agent/runtime/provider_factory.py` 추가
- [x] `AgentSessionRegistry`가 공통 provider factory를 사용하도록 변경
- [x] `TelegramGatewayRunner`가 config API key + shared token store를 함께 사용하도록 변경
- [x] CLI가 config + shared token store를 사용해 provider를 생성하도록 변경
- [x] `provider.authStatus`가 Gemini/Codex auth profile store를 반영하도록 변경
- [x] Phase 00 targeted tests 추가 및 통과

이번 패스에서 아직 남은 항목:

- [ ] Electron Gemini OAuth bootstrap 제약 문서화 또는 임시 설정 경로 제공
- [ ] 필요 시 broader credential matrix를 Phase 00 범위에서 추가 확장

검증 결과:

- `pytest` targeted: `92 passed`
- `ruff check`: passed
- `ruff format --check`: passed
- `mypy`: 현재 이 세션에서는 명령/모듈이 없어 미검증

---

## 1. 목표

Electron, Telegram, CLI가 동일한 provider/auth 해석 경로를 사용하게 만든다.

이 phase가 먼저 필요한 이유는, 현재 surface마다 credential resolution 방식이 다르기 때문에 "같은 agent를 여러 surface에서 통제한다"는 운영 가정이 아직 성립하지 않기 때문이다.

---

## 2. 해결할 문제

현재 상태:

- Electron은 `api_keys + token_store` 기반으로 가장 안정적으로 동작한다.
- Telegram은 환경변수 및 파일 fallback에 기대는 경향이 크다.
- CLI는 설정 또는 OAuth bootstrap은 일부 가능하지만 런타임 provider 주입 경로가 일관되지 않다.
- Gemini는 surface별 OAuth token store 연결이 불완전하다.

결과적으로 동일 계정/모델/토큰 상태를 여러 surface에서 일관되게 재사용하지 못한다.

---

## 3. 범위

포함:

- 공통 provider 생성 helper 도입
- Electron/Telegram/CLI provider 생성 경로 통합
- Codex/Gemini auth 상태 조회 정합성 개선
- config 기반 API key와 token store 동시 지원

제외:

- 새로운 provider 추가
- provider별 재시도 정책 고도화
- UI 수준의 계정 관리 기능 확장

---

## 4. 구현 작업

1. `runtime/provider_factory.py`를 도입해 provider 생성 책임을 단일화한다.
2. CLI 경로가 `config.provider.api_keys`와 `AuthProfileStore`를 함께 전달하도록 수정한다.
3. Telegram 경로도 동일한 factory를 사용하도록 수정한다.
4. WebSocket/Electron에서 노출하는 `provider.authStatus`가 실제 token store 상태를 반영하도록 보정한다.
5. Gemini OAuth bootstrap 제약을 문서화하고, 필요한 경우 명시적 설정 경로를 추가한다.
6. surface별 credential matrix 테스트를 먼저 작성해 회귀를 막는다.

---

## 5. 예상 수정 파일

신규:

- `src/ds_agent/runtime/provider_factory.py`

수정:

- `src/ds_agent/api/agent_session_registry.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/cli/main.py`
- 필요 시 `src/ds_agent/providers/gemini_oauth.py`

---

## 6. 테스트 계획

- `tests/unit/runtime/test_provider_factory.py`
- `tests/unit/infrastructure/test_cli_main.py` 확장
- `tests/unit/infrastructure/test_telegram_runner.py` 확장
- Codex/Gemini credential matrix 테스트
- `provider.authStatus` 회귀 테스트

핵심 시나리오:

- 동일한 token store를 Electron/CLI/Telegram이 공통 사용
- config API key만 있는 경우 모든 surface가 동일하게 provider 생성
- Gemini OAuth가 token store 기반으로 surface 간 동일하게 인식

---

## 7. 완료 기준

- Codex/Gemini credential resolution이 Electron/Telegram/CLI에서 대칭적으로 동작한다.
- config 기반 API key가 CLI/Telegram에서도 실제 런타임 provider 생성에 사용된다.
- token store 기반 Gemini OAuth가 CLI/Telegram에서도 사용된다.
- 기존 Electron 인증 경로가 회귀하지 않는다.

---

## 8. 구현 메모

- 이 단계에서는 runtime autonomy를 건드리지 않는다.
- 목적은 "공유 runtime"의 전제인 auth parity를 먼저 확보하는 것이다.
- 이후 모든 phase는 이 공통 provider factory 위에서만 provider를 생성하도록 규칙화해야 한다.
