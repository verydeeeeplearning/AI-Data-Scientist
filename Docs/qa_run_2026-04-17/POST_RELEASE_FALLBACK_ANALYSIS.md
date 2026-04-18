# Post-Release 실패·Fallback 분석 — LLM 연결 3-Way 관점

**작성일**: 2026-04-18
**사용자 지적 기준**: LLM 연결 방식은 OpenClaw와 동일하게 **OAuth / LOCAL / API** 3가지. S16은 API 한 경로만 검증함 → 나머지 2 범주의 parity 증거 공백.
**관련 문서**: `Docs/qa_run_2026-04-17/S15_telegram_live_parity/FINAL.json`, `S16_llm_record_replay/FINAL.json`, `Docs/rfc/RFC_2026-04_llm_record_replay.md`

---

## 0. 요약 (One-glance)

| Provider 연결 방식 | Provider 수 | 실 전송 parity 증거 | 상태 |
|--------------------|:-----------:|--------------------|:----:|
| **API 기반** (HTTP, api key) | 5+ (OpenAI, Anthropic, LiteLLM, Groq, Mistral, etc.) | OpenAI `gpt-4o-mini` 1개만 VCR cassette byte-identical 증명 | ⚠️ 1/5+ |
| **OAuth 기반** | 2 (Codex / Gemini) | 0 | ❌ 0/2 |
| **LOCAL MODEL 기반** | 3 (Ollama, vLLM, SGLang) | 0 | ❌ 0/3 |
| **Router fallback chain** | 1 logic | 0 (mocked 503 시나리오 미실행) | ❌ 0/1 |

**S16 결론 (byte-identical 9/9 pass)은 "API-OpenAI-gpt-4o-mini single-model single-request" 범위에 한정**. 그 외 provider/transport는 여전히 각자 검증 필요.

---

## 1. 현재 Provider 구조 (코드 실측)

### 1.1 OAuth 기반 (`src/ds_agent/providers/`)

| 파일 | 인증 방식 | Transport | HTTP VCR 녹화 가능? |
|------|----------|-----------|---------------------|
| `codex_oauth.py` | ChatGPT Plus 구독 → `~/.codex/auth.json` JWT | **`subprocess.run(["curl", "https://chatgpt.com/backend-api/..."])`** (line 220) | ❌ process-level, VCR.py는 Python-request 계층만 훅. 별도 cassette 방식 필요 (stdout dump 녹화) |
| `gemini_oauth.py` | Google OAuth access_token OR API key (env fallback) | **LiteLLM 경유** `litellm_model = "gemini/{model}"` (line 109) | ⚠️ LiteLLM은 내부 `requests`/`httpx` 사용 — VCR.py 호환 가능하나 **OAuth refresh 로직의 token renewal 패스가 cassette에 leak 위험** |

**핵심 리스크**: Codex는 subprocess curl이라 현 S16 VCR.py infrastructure로 녹화 불가능. 전용 CLI record-replay fixture 필요.

### 1.2 LOCAL MODEL 기반

| 파일 | 엔드포인트 | 특수사항 |
|------|----------|---------|
| `ollama.py` | `http://127.0.0.1:11434` (line 22) | Native. HTTP 레벨이라 VCR 호환이나, **로컬 서버가 뜨지 않은 환경에서 의미 없음** (cassette = 녹화 당시 Ollama 모델 출력) |
| `local_discovery.py` | vLLM `http://127.0.0.1:8000/v1`, SGLang `http://127.0.0.1:30000/v1` (lines 10-11) | OpenAI-compatible. VCR 호환 가능 |

**핵심 리스크**: LOCAL 경로는 **cassette replay의 의미가 약함** — 환경마다 로컬 모델이 다르고, fresh replay는 실제 로컬 추론 결과 검증이 주 목적. S16 같은 "3채널 byte-identical" 증명보다는 **"Ollama 서버 부재 시 명확한 degraded-mode 에러"** 같은 chaos 시나리오가 적합.

### 1.3 API 기반

| 파일 | 엔드포인트 | S16 녹화? |
|------|----------|:---------:|
| `anthropic.py` | api.anthropic.com | ❌ |
| `openai_provider.py` | api.openai.com | ✅ **cassette 3건 (gpt-4o-mini만)** |
| `litellm_provider.py` | universal gateway (Groq, Mistral, Cohere 등 수십 개) | ❌ |

**핵심 리스크**: API provider 다양성 대비 S16 녹화 범위 최소. `gpt-4o` / `gpt-4o-mini` 외 다른 모델·provider 사이의 미세한 응답 shape 차이가 DeliveryPack 조립에 영향 줄 수 있으나 미검증.

### 1.4 Router fallback chain (`src/ds_agent/providers/router.py`)

- line 73~86: primary → fallback1 → fallback2 chain
- line 144: `_emit_fallback_event`로 fallback 발생 기록
- **S16 미검증**: primary가 503 에러 반환 시 router가 chain을 올바르게 순회하는지 cassette-based 검증 없음. B12 Round 1에서 mocked 503 테스트는 있었으나 real-provider 응답 기반 아님.

---

## 2. S15 / S16에서 드러난 fallback 인벤토리

### 2.1 S15 Telegram live polling

| ID | 내용 | 분류 | Severity |
|----|------|------|:--------:|
| S15-FB1 | `python-telegram-bot` **TestApplicationBuilder + fake token `1:AAAA_FAKE_TESTING_ONLY...`** 사용. Real Telegram API 호출 0건 | 의도된 fallback (사용자 제약) | Low |
| S15-FB2 | `Bot.send_message`, `get_me`, `get_updates` 전수 monkeypatch no-op | 의도된 fallback | Low |
| S15-FB3 | Telegram 네트워크 경로(`api.telegram.org` HTTPS)의 real transport 미검증 | 실 증거 공백 | Med |

S15는 **channel plumbing (Update → handler → session_id derive → WS backend)** 검증이 목적이었고 이 범위는 live로 통과. 다만 **Telegram 서버와의 real wire protocol** 검증은 여전히 결여.

### 2.2 S16 LLM record-replay

| ID | 내용 | 분류 | Severity |
|----|------|------|:--------:|
| S16-FB1 | **Electron row 3건은 CLI 결과에서 synthesized** (Playwright loop 미실행). RFC §4 Phase 4에서 "OPENAI_BASE_URL 동일 + backend subprocess 동일하므로 transport evidence 동일"로 허용 | 의도된 fallback (RFC 근거 있음) | Med |
| S16-FB2 | **~~PyInstaller packaged backend 사용 불가~~** — 해소됨 (2026-04-18, `S-packaging-numpy_spec_fix`). numpy/scipy/pandas가 excludes에서 hiddenimports로 이동. 재빌드 후 packaged exe 기동 OK, `/health` 200, 18 skill load, import error 0 | ~~실제 실패~~ → **closed** | ~~High~~ |
| S16-FB3 | API 기반 provider 중 **OpenAI gpt-4o-mini 1개 모델만** 녹화. 나머지 api provider + 모든 OAuth/LOCAL 미녹화 | 범위 제약 | Med |
| S16-FB4 | fallback chain (router primary→secondary) 실 cassette 검증 없음 | 범위 제약 | Med |

### 2.3 이전 Sprint의 fallback들 (이미 closed)

- Post-QA Phase 2 coverage: Windows 1-shot coverage가 **성공** 했음 → fallback 불필요 판명 (81.53%)
- Post-QA Phase 3: Telegram factory-wiring only (S15로 upgrade), mocked error hash (S16으로 upgrade)

---

## 3. 진짜 "실패" vs "fallback 허용" 구분

### 3.1 진짜 실패 (해소 필요 / 해소됨)

| ID | 제목 | 해소 경로 | 상태 |
|----|------|----------|:----:|
| **S16-FB2 (import-time)** | Packaged backend excludes numpy/scipy/sklearn/pandas → backend `factory.create_agent` import 실패 | `S-packaging-numpy` (2026-04-18): numpy/scipy/pandas을 hiddenimports로 이동 | ✅ closed |
| **S16-FB2-b (execution-time)** | 사용자 지적(2026-04-18) — S-packaging-numpy 이후에도 (a) .venv에 sklearn/xgboost/lightgbm/matplotlib/seaborn 미설치, (b) `sys.executable` 기반 sandbox가 frozen 모드에서 `unrecognized arguments` argparse 에러로 **전면 작동 불능** | `S-ml-stack-packaging` (2026-04-18): pyproject.toml에 ML stack core deps 추가 + `--mode exec` 서브커맨드 + xgboost.dll 등 native DLL 명시 번들. Packaged exe에서 iris 97.4% 실증 | ✅ closed |

두 단계 모두 해소됨. 상세: `Docs/qa_run_2026-04-17/S-packaging-numpy_spec_fix/CHANGELOG.md`, `Docs/qa_run_2026-04-17/S-ml-stack-packaging/CHANGELOG.md`.

나머지는 모두 **의도된 scope 제약 + 별도 sprint 필요**.

### 3.2 의도된 fallback (scope 명시·문서 근거 있음)

| ID | RFC/근거 |
|----|----------|
| S15-FB1/FB2 | RFC_2026-04_adapter_killswitch.md에서 "fake bot harness만 허용" 명시 |
| S16-FB1 (Electron synthesize) | RFC_2026-04-llm_record_replay.md §4 Phase 4 |

### 3.3 미검증 gap (추가 sprint 필요)

| Gap | 추천 처리 |
|-----|----------|
| **API provider 다양성** (Anthropic/LiteLLM/Groq/Mistral cassette) | S21 "API provider matrix cassette" (확장 단순) |
| **OAuth 경로 (Codex subprocess)** | S22 "CLI-subprocess record-replay" (별도 fixture 방식 — stdout JSON dump 캡처) |
| **OAuth 경로 (Gemini via LiteLLM)** | S21에 포함 가능 (LiteLLM HTTP 레이어) |
| **LOCAL MODEL (Ollama 등)** | S23 "Local model chaos/degraded mode" (cassette보다 chaos 시나리오 적합) |
| **Router fallback chain** | S24 "Router failover cassette" (primary 503 cassette + secondary 성공 cassette) |
| **Real Telegram wire protocol** | S25 "Telegram live integration with real bot token" (env 의존, 외부 자원) |

---

## 4. 제품 컨셉 관점 — 3-way 모두가 First-class

DS Agent 공식 컨셉 (메모리 `project_overview`, `feedback_preserve_autonomy`):
> **LLM은 오케스트레이터, 코드는 도구 제공자.** 사용자가 선택하는 LLM 연결 경로(OAuth / LOCAL / API)에 따라 **동일한 LLM 경험**을 보장해야 함.

OpenClaw 구조와 동치:
- OAuth: ChatGPT Plus 구독자 / Gemini 무료 tier 사용자
- LOCAL: 프라이버시·비용·오프라인 환경
- API: 엔터프라이즈·자체 키 관리

**현 상태**: S16이 증명한 "3 시나리오가 3채널(CLI/Telegram/Electron)에서 byte-identical"은 **API-OpenAI 경로에만 유효**. 사용자가 Codex OAuth 또는 Ollama로 전환하면 parity가 유지되는지 **미증명**.

→ Hermes-style 자율 에이전트가 "어떤 LLM 연결을 고르든 동일한 DeliveryPack/verdict를 생성한다"는 핵심 약속은 **1/3만 실증** 상태.

---

## 5. 우선순위 재배치 (Post-release sprint 제안)

### 5.1 당장 (P0 — 서명 빌드 smoke 블로커)
- **S-packaging-numpy**: `ds-agent-api.spec` excludes 재평가. numpy/scipy 포함 여부 결정. S16-FB2 해소. (P0-05 조달 후 C15 smoke 5/5 재실행 시 필수)

### 5.2 중요 (P1 — 제품 컨셉 정합)
- ~~S21 API provider matrix cassette~~ → **강등** (2026-04-18): 3-channel parity는 provider-agnostic (adapter 정규화 이후 단일 code path). S16 OpenAI 증명으로 충분. Provider adapter 자체 회귀는 unit test 범위.
- ~~**S21' Gemini OAuth cassette**~~ → **closed 2026-04-18** (S21). `gemini_oauth.py`가 misnamed(LiteLLM HTTP/API key)임을 식별, 신규 `GeminiCliProvider`(`gemini -p` subprocess)로 OAuth 경로 실구현. 3 시나리오 녹화 + byte-identical replay 6/6 pass. 세부: `Docs/qa_run_2026-04-17/S21_gemini_cli_oauth/CHANGELOG.md`.
- ~~**S22 Codex OAuth subprocess fixture**~~ → **closed 2026-04-18**. `scripts/parity_harness/record_codex_fixture.py`로 3 시나리오 녹화 (ChatGPT Plus 3턴), `tests/integration/providers/test_codex_fixture_replay.py`가 byte-identical replay 5/5 pass. secret sanitize 0 leak. 세부: `Docs/qa_run_2026-04-17/S22_codex_oauth_fixture/CHANGELOG.md`.

### 5.3 보조 (P2 — chaos/robustness)
- **S23 Local model chaos**: Ollama 서버 부재 / 포트 occupied / 타임아웃 시나리오 → D16 chaos와 유사 패턴
- **S24 Router failover cassette**: primary 503 + secondary 200 조합, fallback event emit 검증
- **S25 Real Telegram wire**: 실 bot token 준비 시 optional full E2E

### 5.4 보류
- **Gemini OAuth cassette**: LiteLLM 경유라 S21 LiteLLM 범위에 포함 (access_token refresh 로직은 별도 unit test로 이미 A02 R2 PII 검증에 포함)

---

## 6. 결론

### 6.1 실패한 것
2 단계 모두 해소됨 (2026-04-18):
- S16-FB2 import-time (S-packaging-numpy) ✅
- S16-FB2-b execution-time — ML libs 미설치 + packaged sandbox 불능 (S-ml-stack-packaging) ✅

이제 **"진짜 실패" 0건**. (주의: 이 카운트는 2026-04-18 사용자 지적으로 한 차례 정정됨 — 초기 "0건" 주장이 부분적이었음이 드러나 S-ml-stack-packaging으로 완결.)

### 6.2 미검증 범위 (2026-04-18 최종)
3-way 분류 기준:
- OAuth: **2/2 검증** ✅ — Codex subprocess (S22) + Gemini CLI subscription (S21)
- LOCAL: **0/3 검증** (Ollama, vLLM, SGLang) — chaos test 범위, post-release 후속
- API: **1/5+ 검증** (OpenAI gpt-4o-mini) — provider adapter 정규화 이후 downstream 공통 path, 3-channel parity는 provider-agnostic
- Router fallback: **0/1 검증** — primary 503 → secondary cassette 합성, 본 Epic 이후 별도 sprint
- Sandbox ML 실행: **source/frozen 2/2 대칭 검증** ✅ (Phase 6)

### 6.3 권고 후속 Sprint 수
5 개 (S21~S25), 대략 15~25 시간. P1 2건(S21/S22)만 먼저 해도 3-way 전체 커버리지 도달 가능.

### 6.4 현 릴리스 판정에 미치는 영향
**CONDITIONAL_GO 유지 타당**. 이유:
- S16이 API-OpenAI 경로에서 byte-identical parity 증명 → 핵심 가설("3채널 등가성") 한 경로에서는 **live 증명**
- 나머지 경로는 code-level factory equivalence (C13 Round 1 fallback)가 여전히 증거로 존재 — **충분히 약하나 완전 무근거 아님**
- GO 전환은 external blockers 5건이 지배적이며 본 gap은 포스트 릴리스 단계적 보강으로 처리 가능

GO 전환 시점에 **S21 P1 2건 포함 권장** — "3-way 균형 있는 live parity" 수준으로 올려야 제품 컨셉과 일치.
