import assert from 'node:assert/strict';

import type {
  ReviewVerdictView,
  ShadowComparisonView,
} from '../../src/renderer/types/taskContract';
import {
  buildQualityPanelVerifierModel,
  pickEffectiveReviewVerdict,
} from '../../src/renderer/components/workflow/qualityPanelModel';

function verdict(
  overrides: Partial<ReviewVerdictView> & Pick<ReviewVerdictView, 'verdict_id' | 'created_at'>
): ReviewVerdictView {
  return {
    verdict_id: overrides.verdict_id,
    task_id: 'TC-2026-001',
    category: overrides.category ?? 'orchestrator',
    result: overrides.result ?? 'warn',
    reviewer: 'verifier',
    summary: 'Review before close',
    evidence_refs: [],
    created_at: overrides.created_at,
    confidence: overrides.confidence ?? {
      score: 0.65,
      grade: 'medium',
      rationale: 'Needs review.',
    },
    blocking_issues: overrides.blocking_issues ?? [
      {
        layer: 'policy',
        severity: 'high',
        message: 'Needs owner sign-off',
        blocking: true,
      },
    ],
    layers: overrides.layers ?? [
      { layer: 'statistical', overall: 'pass', score: 1.0 },
      { layer: 'data', overall: 'warn', score: 0.5 },
      { layer: 'policy', overall: 'fail', score: 0.0 },
      { layer: 'narrative', overall: 'warn', score: 0.55 },
    ],
    metadata: overrides.metadata ?? {},
  };
}

function shadowComparison(): ShadowComparisonView {
  return {
    comparison_id: 'SC-2026001',
    verdict_id: 'RV-2026002',
    task_id: 'TC-2026-001',
    created_at: '2026-04-16T11:05:00Z',
    applicable_count: 2,
    mismatch_count: 1,
    match_rate: 0.5,
    metadata: {},
    items: [
      {
        comparison_key: 'baseline_guard',
        legacy_source: 'baseline_guard_hook',
        verifier_targets: ['baseline_comparison'],
        applicable: true,
        legacy_state: 'clear',
        verifier_state: 'triggered',
        matches: false,
        mismatch_kind: 'verifier_only',
        legacy_evidence: [],
        verifier_evidence: [{ check_id: 'baseline_comparison' }],
        note: 'verifier flagged an issue that the legacy hook missed',
      },
    ],
  };
}

function run(): void {
  const early = verdict({
    verdict_id: 'RV-2026001',
    created_at: '2026-04-16T09:00:00Z',
  });
  const laterNarrative = verdict({
    verdict_id: 'RV-2026003',
    created_at: '2026-04-16T13:00:00Z',
    category: 'narrative',
  });
  const laterOrchestrator = verdict({
    verdict_id: 'RV-2026002',
    created_at: '2026-04-16T11:00:00Z',
    metadata: {
      judge_mode: 'heuristic_only',
      shadow_match_rate: 0.8,
      shadow_mismatch_count: 1,
    },
  });

  const picked = pickEffectiveReviewVerdict([early, laterNarrative, laterOrchestrator]);
  assert.equal(picked?.verdict_id, 'RV-2026002');

  const model = buildQualityPanelVerifierModel(laterOrchestrator, shadowComparison());
  assert.ok(model);
  assert.equal(model?.confidenceGrade, 'medium');
  assert.equal(model?.confidencePercent, 65);
  assert.equal(model?.blockingCount, 1);
  assert.equal(model?.judgeMode, 'heuristic_only');
  assert.equal(model?.shadowMatchRate, 0.8);
  assert.equal(model?.shadowMismatchCount, 1);
  assert.deepEqual(model?.blockingIssues, [
    { scope: 'policy', message: 'Needs owner sign-off' },
  ]);
  assert.deepEqual(model?.shadowMismatchPreview, [
    {
      comparisonKey: 'baseline_guard',
      mismatchKind: 'verifier_only',
      stateSummary: 'clear -> triggered',
      note: 'verifier flagged an issue that the legacy hook missed',
    },
  ]);

  console.log('[contract] PASS verifier quality-panel model');
}

run();
