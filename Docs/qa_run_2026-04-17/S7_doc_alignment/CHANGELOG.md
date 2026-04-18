# S7 Doc Alignment — CHANGELOG

**실행일**: 2026-04-18
**스코프**: 5건 spec/plan drift 정정 (D5-1, NOTE-B08-1, B11-D1, B11-D2, B11-D3)
**대상 파일**: `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` 단일
**코드 변경**: 0 (문서 전용 Sprint, 계획서 §2.1 명시 — S7은 code 0, doc만)

## 수정 상세

| ID | 위치 (원본 line) | 이전 문구 (drift) | 수정 후 (실측 code truth) |
|:--:|:---------------:|------------------|--------------------------|
| D5-1 | §5.1-6 (line 249) | ``<ds:review_artifacts>...</ds:review_artifacts>`` | ``<!-- DS_REVIEW_ARTIFACTS {...} -->`` |
| NOTE-B08-1 | §5.4-6 (line 303) | "2명만 승인 → staging / 3명 승인 → production" | "3-of-3 승인 (staging + production 양쪽)" |
| B11-D1 | §5.7-1 (line 355) | `completed/failed/cancelled` terminal | `completed/cancelled/archived` terminal |
| B11-D2 | §5.7-3 (line 357) | `business_weight=0.5, sla_urgency=1.0, age_factor=0.2` | `business_weight=2.0, sla_urgency=3.0, age_factor=0.5` (ordering intent 동일) |
| B11-D3 | §5.7-4 (line 358) | "각 조건의 satisfied 판정 로직" | "Timer만 완전 기능, Approval/DataFreshness/External은 adapter 대기 (v2 maturity gap)" 명시 |

각 수정 문구에 `(updated 2026-04-18, source: S7 <ID>)` annotation 포함 — 감사 추적.

## Quality Gate

- [x] 5건 전수 수정 완료
- [x] diff 전수 계획서에 반영 (단일 파일)
- [x] 문구 교차 참조 self-check:
  - `<ds:review_artifacts>` grep → 0 occurrence 잔존 (수정본만 존재)
  - `2명만 승인` grep → 0 occurrence
  - `completed/failed/cancelled` grep → 0 occurrence (§8.1 milestone 목록에서 P2-15 등은 별개 맥락이므로 해당 없음)
  - `business_weight=0.5` grep → 0 occurrence
- [x] 각 수정에 source annotation 명시

## Rollback

git 없는 저장소이므로 `.tmp/qa_S7/plan_before.md` 백업 유지. 문제 시 해당 4 Edit 역순 재실행 가능 (단일 파일, 5개의 고유 매칭 문자열).

## Notes

- S7 작업 중 §8 Milestone 표에는 `failed`, `cancelled` 등 상태 어휘가 일반 명사로 쓰여 portfolio 스테이트 기술이 아니므로 수정 불요.
- D5-1 수정 후 문서 reflow에서 다른 곳의 `ds:review_artifacts` 참조 없음 확인.
- §1 원칙 테이블(A4)의 "Promotion Gate 3-role"은 이미 정확한 기술이므로 유지.
