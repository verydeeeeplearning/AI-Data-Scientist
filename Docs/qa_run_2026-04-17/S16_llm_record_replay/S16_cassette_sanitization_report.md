# S16 Cassette Secret Sanitization Report

Generated: 2026-04-18
Agent: S16
Scope: `tests/fixtures/llm_cassettes/*.yaml` (3 files, 1 interaction each)

## 1. Policy Reference

`Docs/rfc/RFC_2026-04_llm_record_replay.md` §3.2 — hard constraint: no API key,
no account identifier, no bearer token, no tracking cookie may appear in any
committed cassette file.

Two layers of defense:
1. **VCR.py record-time filter** — `filter_headers` sanitizes request headers,
   `filter_post_data_parameters` sanitizes request body parameters.
2. **Post-record response-header redaction** — the recording script rewrites
   response-side sensitive headers (`openai-organization`, `openai-project`,
   `set-cookie`, `cf-ray`, `x-request-id`) to `REDACTED` since VCR.py does not
   by default filter the response side.
3. **CI hook** — `scripts/check_cassette_secrets.py` regex scan covering
   request + response, rejects any long `sk-...`, `sk-proj-...`, `sk-ant-...`,
   `AIzaSy...`, and `Authorization: Bearer <not-REDACTED>` matches.

## 2. Recording Key Used

- Only supplied via `OPENAI_API_KEY` **environment variable** to the
  `record_llm_cassettes.py` subprocess.
- Never written to disk (no `.env`, no log, no cassette).
- Prefix format `sk-proj-…` — new-format OpenAI project key.
- Single use for this sprint; budget cap $1, actual cost well under $0.01
  (see §4).

## 3. Automated Scan Results

Command: `python scripts/check_cassette_secrets.py`

```
  OK  tests\fixtures\llm_cassettes\scenario_P01.yaml
  OK  tests\fixtures\llm_cassettes\scenario_P02.yaml
  OK  tests\fixtures\llm_cassettes\scenario_P03.yaml

PASS: 3 cassette(s) scanned, 0 leaks.
```

Belt-and-braces grep (shell-level):

| Pattern | Hits | Decision |
|---------|-----:|----------|
| `sk-proj-` or `sk-[A-Za-z0-9_-]{30,}` | 0 | PASS |
| `authorization:\s*bearer\s+(?!REDACTED)` | 0 | PASS |
| Any `Bearer` line | 3 × `Bearer REDACTED` | PASS (sanitized form only) |
| `proj_` or `user-gh` or `__cf_bm` | 0 | PASS |

## 4. Cost Audit (Recording)

From `tests/fixtures/llm_cassettes/manifest.json`:

| Scenario | Cassette | Model | Prompt tokens | Completion tokens | Total tokens |
|---------:|---------|-------|--------------:|------------------:|------------:|
| P-01 | `scenario_P01.yaml` | gpt-4o-mini | 106 | 47 | 153 |
| P-02 | `scenario_P02.yaml` | gpt-4o-mini | 111 | 31 | 142 |
| P-03 | `scenario_P03.yaml` | gpt-4o-mini | 118 | 49 | 167 |
| **sum** | | | **335** | **127** | **462** |

Cost calculation (gpt-4o-mini Apr 2026 pricing: $0.15 / 1M input, $0.60 / 1M output):
- Input: 335 * 0.15 / 1_000_000 = $0.00005025
- Output: 127 * 0.60 / 1_000_000 = $0.0000762
- **Total: $0.00013 (well under $1 cap, under $0.10 target)**

## 5. Response Header Redactions (Per Cassette)

| Cassette | headers_redacted |
|----------|-----------------:|
| `scenario_P01.yaml` | 5 |
| `scenario_P02.yaml` | 5 |
| `scenario_P03.yaml` | 5 |

Headers redacted (per cassette): `openai-organization`, `openai-project`,
`set-cookie`, `cf-ray`, `x-request-id`.

## 6. CI Gate

PR merge is gated by `scripts/check_cassette_secrets.py`:
- Exit 0 → cassettes clean, merge allowed.
- Exit 1 → leak detected, merge blocked. Script prints line numbers and
  pattern names (truncated preview of the match) for remediation.
- Exit 2 → cassette dir missing (non-fatal for PRs that don't touch cassettes).

## 7. Conclusion

**PASS**. 0 secret leakage across 3 cassettes. Defense-in-depth layers
(VCR.py filter + post-record header redaction + grep CI hook) are each
independently working.
