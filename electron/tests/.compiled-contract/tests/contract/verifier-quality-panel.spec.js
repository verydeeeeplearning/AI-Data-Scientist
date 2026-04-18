"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const qualityPanelModel_1 = require("../../src/renderer/components/workflow/qualityPanelModel");
function verdict(overrides) {
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
function shadowComparison() {
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
function run() {
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
    const picked = (0, qualityPanelModel_1.pickEffectiveReviewVerdict)([early, laterNarrative, laterOrchestrator]);
    strict_1.default.equal(picked?.verdict_id, 'RV-2026002');
    const model = (0, qualityPanelModel_1.buildQualityPanelVerifierModel)(laterOrchestrator, shadowComparison());
    strict_1.default.ok(model);
    strict_1.default.equal(model?.confidenceGrade, 'medium');
    strict_1.default.equal(model?.confidencePercent, 65);
    strict_1.default.equal(model?.blockingCount, 1);
    strict_1.default.equal(model?.judgeMode, 'heuristic_only');
    strict_1.default.equal(model?.shadowMatchRate, 0.8);
    strict_1.default.equal(model?.shadowMismatchCount, 1);
    strict_1.default.deepEqual(model?.blockingIssues, [
        { scope: 'policy', message: 'Needs owner sign-off' },
    ]);
    strict_1.default.deepEqual(model?.shadowMismatchPreview, [
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
