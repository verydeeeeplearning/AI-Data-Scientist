# ml_engineer brief

## model_card: 모델 카드

- 모델 버전: churn_v4.3.1.

_Citations: lineage://dataset/snapshot_2026_04_10_

## serving_config: 서빙 구성

- GPU T4 x1, 레이턴시 p95 < 80ms.

_Citations: lineage://dataset/snapshot_2026_04_10_

## monitoring_setup: 모니터링

- PSI > 0.2 알람, 24시간 지연 감지.

_Citations: lineage://dataset/snapshot_2026_04_10_

## rollback_plan: 롤백 절차

- 이전 블레스드 모델 churn_v4.2.9로 자동 되돌림.

_Citations: lineage://dataset/snapshot_2026_04_10_

## Verifier Flags

- needs_secondary_review
