# S22 — Codex OAuth Subprocess Fixture (Phase 5 of LLM OAuth + ML Execution Epic)

**실행일**: 2026-04-18
**스코프**: ChatGPT Plus/Pro 구독 기반 Codex OAuth 경로를 cassette replay로 증명
**근거**: `POST_RELEASE_FALLBACK_ANALYSIS.md` §5.2 + `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 5
**비용**: ChatGPT Plus 세션 3턴 소모 (scenarios codex-P01/P02/P03)

## 3-way LLM 커버리지 관점

| Tier | Provider | Parity 증거 |
|:----:|---------|-------------|
| API | OpenAI `gpt-4o-mini` | S16 VCR.py cassette 9/9 byte-identical |
| **OAuth (Codex)** | **Codex via ChatGPT Plus** | **S22 subprocess fixture 3/3 byte-identical** ✅ NEW |
| OAuth (Gemini) | Gemini CLI subscription | Phase 4 (진행 예정) |
| LOCAL | Ollama / vLLM / SGLang | Phase 후속 |
| Router failover | primary→secondary chain | 후속 |

## 구현

### 신규 파일

- `scripts/parity_harness/record_codex_fixture.py` (258 lines)
  - `CodexOAuthProvider`를 실 `~/.codex/auth.json`으로 구동
  - `subprocess.run` 래핑으로 `chatgpt.com/backend-api/wham/responses` 호출의 raw stdout 캡처
  - 3 scenarios: 간단한 1-턴 프롬프트 (capital of France / JSON return / overfitting 설명)
  - access_token / account_id / refresh_token + 추가 JWT 패턴 sanitize → `<CODEX_ACCESS_TOKEN>` 등 placeholder
  - 응답 텍스트 SHA-256 → manifest에 기록 (replay 검증용 anchor)
- `tests/fixtures/llm_cassettes/codex/codex-P01.json` / `codex-P02.json` / `codex-P03.json` / `manifest.json`
- `tests/integration/providers/test_codex_fixture_replay.py`
  - `subprocess.run`을 scenario별로 monkeypatch → fixture stdout 반환
  - `CodexOAuthProvider.chat()` 실행 → 응답 SHA-256을 manifest와 비교
  - 추가 가드: cmd에 `<CODEX_ACCESS_TOKEN>` placeholder 존재 + raw `Bearer eyJ...` 부재

### 수정

- `scripts/check_cassette_secrets.py`
  - scope 확장: `**/*.json` 포함 (Codex JSON fixture 커버)
  - 신규 패턴: `jwt_eyJ` (3-segment JWT), `codex_chatgpt_account_id` (raw UUID)
  - false-positive 수정: `Bearer <PLACEHOLDER>` (angle-bracket) 허용

## 증거

### 녹화 결과 (Codex Plus 3턴)

```text
[record] codex-P01 -- calling ChatGPT backend...
[ok]     codex-P01: response_sha256=bdff8c417ab50e95...
[record] codex-P02 -- calling ChatGPT backend...
[ok]     codex-P02: response_sha256=4539813cc1223b62...
[record] codex-P03 -- calling ChatGPT backend...
[ok]     codex-P03: response_sha256=a4055bb83c78ea31...
[done] wrote 3 fixtures + manifest
```

모델: `gpt-5.4` (ChatGPT Plus 기본). 사용 토큰:

| Scenario | input | output | 비고 |
|----------|:-----:|:------:|------|
| codex-P01 | 29 | 6 | "Paris." |
| codex-P02 | 27 | 9 | JSON 반환 |
| codex-P03 | 27 | 39 | overfitting 1-sentence |

### Secret scan

```text
$ python scripts/check_cassette_secrets.py
  OK  tests/fixtures/llm_cassettes/scenario_P01.yaml
  OK  tests/fixtures/llm_cassettes/scenario_P02.yaml
  OK  tests/fixtures/llm_cassettes/scenario_P03.yaml
  OK  tests/fixtures/llm_cassettes/codex/codex-P01.json
  OK  tests/fixtures/llm_cassettes/codex/codex-P02.json
  OK  tests/fixtures/llm_cassettes/codex/codex-P03.json
  OK  tests/fixtures/llm_cassettes/codex/manifest.json
  OK  tests/fixtures/llm_cassettes/manifest.json
PASS: 8 cassette(s) scanned, 0 leaks.
```

### Replay 검증

```text
$ uv run pytest tests/integration/providers/test_codex_fixture_replay.py -v
test_codex_replay_byte_identical[codex-P01] PASSED
test_codex_replay_byte_identical[codex-P02] PASSED
test_codex_replay_byte_identical[codex-P03] PASSED
test_manifest_exists_and_nonempty PASSED
test_every_fixture_is_sanitized PASSED
============================== 5 passed in 0.07s ==============================
```

## Quality Gate

- [x] 3 fixture 녹화 완료 (ChatGPT Plus 3턴, $0 직접 비용, 구독 내)
- [x] secret leak 0건 (8 cassette scanned)
- [x] byte-identical replay 3/3 pass
- [x] monkeypatch isolation: replay 테스트에서 network 호출 0건
- [x] 공격 표면 추가 없음 — `test_every_fixture_is_sanitized`로 매 실행 시 재확인

## 보안 고려

- Access token (JWT, 1956 chars) / account_id (UUID) / refresh_token — 모두 sanitized
- Record 스크립트는 creds를 **메모리에만** 유지, 로그/파일/stdout 미기록
- `_Capturer._wrapped`는 `chatgpt.com` URL이 포함된 subprocess만 녹화 (다른 curl 호출은 pass-through)
- replay 테스트는 fake token (`fake-replay-token`)으로 `CodexOAuthProvider` 구동 → 실제로는 subprocess 호출 자체가 monkeypatch되므로 creds 불필요

## Rollback

- Fixture 3건 + manifest 삭제
- `scripts/parity_harness/record_codex_fixture.py` 삭제
- `tests/integration/providers/test_codex_fixture_replay.py` 삭제
- `scripts/check_cassette_secrets.py` 변경 revert (JSON scope + jwt_eyJ/codex_chatgpt_account_id 패턴 + placeholder whitelist)

## 제한사항 / 후속

1. **Scenarios 단순**: S16 (P01/P02/P03)과 달리 DS-agent-특화 프롬프트 아닌 간단 프롬프트 사용. Plus quota 절약 + 응답 결정성 우선. 필요 시 추후 확장.
2. **SSE 스트림 replay**: 현 fixture는 정적 bytes. SSE 이벤트 순서/타이밍은 byte 레벨에서 이미 재현되나, 스트리밍 중간 취소 시나리오는 커버 안 함.
3. **Account-specific 답변**: "Paris.", "{\"x\": 42}" 등 계정 독립적인 응답만 녹화. 사용자 프로필 의존 답변 (memory 등) 미녹화.
4. **Phase 4 (Gemini OAuth CLI)**: 동일 방법론을 Gemini CLI subprocess(`gemini -p`)에 적용 예정. 다만 기존 `gemini_oauth.py`가 LiteLLM HTTP 경유이므로 provider 재설계가 선행됨.
5. **토큰 만료**: `~/.codex/auth.json`의 access_token 만료 시 refresh 로직은 본 스프린트 미커버. Codex CLI가 자체 관리.

## 이전 문서와의 정합성

- `POST_RELEASE_FALLBACK_ANALYSIS.md` §5.2 S22 항목 → closed
- `HANDOFF_NEXT_AGENT.md` §14.2 — "Codex OAuth paused" 해제 예정 (Phase 7에서 갱신)
- `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 5 체크박스 완료
