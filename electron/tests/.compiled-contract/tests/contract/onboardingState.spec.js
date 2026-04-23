"use strict";
/**
 * Contract test for the application/onboarding/onboardingState module.
 *
 * Verifies that the pure state-machine helpers extracted from
 * OnboardingWizard preserve the existing wire contract (finalize payload
 * shape, autonomy mode mapping, advance/back rules).
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const onboardingState_1 = require("../../src/renderer/application/onboarding/onboardingState");
const results = [];
function test(name, fn) {
    try {
        fn();
        results.push({ name, ok: true });
    }
    catch (error) {
        results.push({ name, ok: false, error });
    }
}
test('initial state defaults to use_case step', () => {
    const state = (0, onboardingState_1.buildInitialOnboardingState)({ defaultDataChoice: 'sample' });
    strict_1.default.equal(state.step, 'use_case');
    strict_1.default.equal(state.dataChoiceId, 'sample');
    strict_1.default.equal(state.useCaseId, null);
    strict_1.default.equal(state.deliverables.length, 0);
});
test('isOnboardingPrimaryStepId guards string union', () => {
    strict_1.default.equal((0, onboardingState_1.isOnboardingPrimaryStepId)('use_case'), true);
    strict_1.default.equal((0, onboardingState_1.isOnboardingPrimaryStepId)('confirm'), true);
    strict_1.default.equal((0, onboardingState_1.isOnboardingPrimaryStepId)('not-a-step'), false);
});
test('deriveUseCaseDefaults returns curated deliverables per use case', () => {
    strict_1.default.deepEqual((0, onboardingState_1.deriveUseCaseDefaults)('reporting'), {
        deliverables: ['report', 'presentation'],
        mode: 'controlled',
    });
    strict_1.default.deepEqual((0, onboardingState_1.deriveUseCaseDefaults)('sql_exploration'), {
        deliverables: ['report'],
        mode: 'fast',
    });
    strict_1.default.deepEqual((0, onboardingState_1.deriveUseCaseDefaults)('weekly_kpi_triage'), {
        deliverables: ['report', 'presentation'],
        mode: 'fast',
    });
    strict_1.default.deepEqual((0, onboardingState_1.deriveUseCaseDefaults)('ab_test_analysis'), {
        deliverables: ['report', 'presentation'],
        mode: 'controlled',
    });
});
test('autonomy <-> execution mode mapping is bijective', () => {
    for (const mode of ['fast', 'balanced', 'controlled']) {
        const exec = (0, onboardingState_1.mapAutonomyModeToExecutionMode)(mode);
        const back = (0, onboardingState_1.mapExecutionModeToAutonomyMode)(exec);
        strict_1.default.equal(back, mode);
    }
});
test('autonomy mode maps to quality preset', () => {
    strict_1.default.equal((0, onboardingState_1.mapAutonomyModeToQualityPreset)('fast'), 'fast');
    strict_1.default.equal((0, onboardingState_1.mapAutonomyModeToQualityPreset)('balanced'), 'balanced');
    strict_1.default.equal((0, onboardingState_1.mapAutonomyModeToQualityPreset)('controlled'), 'best_quality');
});
test('next/previous step traversal honors fixed order', () => {
    strict_1.default.equal((0, onboardingState_1.nextOnboardingStep)('use_case'), 'data');
    strict_1.default.equal((0, onboardingState_1.nextOnboardingStep)('confirm'), null);
    strict_1.default.equal((0, onboardingState_1.previousOnboardingStep)('use_case'), null);
    strict_1.default.equal((0, onboardingState_1.previousOnboardingStep)('mode'), 'deliverables');
    strict_1.default.equal(onboardingState_1.ONBOARDING_PRIMARY_STEP_ORDER.length, 6);
});
test('canAdvanceOnboardingStep enforces selection invariants', () => {
    const empty = (0, onboardingState_1.buildInitialOnboardingState)({ defaultDataChoice: 'upload' });
    strict_1.default.equal((0, onboardingState_1.canAdvanceOnboardingStep)(empty), false, 'use_case requires a selection');
    const withUseCase = (0, onboardingState_1.applyUseCaseSelection)(empty, 'data_analysis');
    strict_1.default.equal((0, onboardingState_1.canAdvanceOnboardingStep)({ ...withUseCase, step: 'deliverables' }), true);
    const cleared = { ...withUseCase, step: 'deliverables', deliverables: [] };
    strict_1.default.equal((0, onboardingState_1.canAdvanceOnboardingStep)(cleared), false, 'deliverables empty must block');
    strict_1.default.equal((0, onboardingState_1.canAdvanceOnboardingStep)({ ...withUseCase, step: 'model', modelId: null }), false, 'model step requires a chosen model');
    strict_1.default.equal((0, onboardingState_1.canAdvanceOnboardingStep)({ ...withUseCase, step: 'model', modelId: 'gpt-4o' }), true);
});
test('toggleDeliverable adds and removes deliverables idempotently', () => {
    const base = (0, onboardingState_1.applyUseCaseSelection)((0, onboardingState_1.buildInitialOnboardingState)({ defaultDataChoice: 'upload' }), 'general');
    const added = (0, onboardingState_1.toggleDeliverable)(base, 'notebook');
    strict_1.default.ok(added.deliverables.includes('notebook'));
    const removed = (0, onboardingState_1.toggleDeliverable)(added, 'notebook');
    strict_1.default.ok(!removed.deliverables.includes('notebook'));
});
test('buildOnboardingFinalizePayload emits the documented wire contract', () => {
    const payload = (0, onboardingState_1.buildOnboardingFinalizePayload)({
        sessionId: 'sess-1',
        useCaseId: 'data_analysis',
        starterPrompt: 'Profile this dataset',
        dataChoiceId: 'sample',
        deliverables: ['chart_summary'],
        autonomyMode: 'balanced',
        modelId: 'claude-opus-4-7',
    });
    strict_1.default.equal(payload.sessionId, 'sess-1');
    strict_1.default.equal(payload.useCaseId, 'data_analysis');
    strict_1.default.deepEqual(payload.responses.step3_deliverables, ['chart_summary']);
    strict_1.default.equal(payload.responses.step5_model, 'claude-opus-4-7');
    strict_1.default.equal(payload.responses.step6_confirmed, true);
    strict_1.default.equal(payload.responses.step2_data.sampleId, 'builtin:data_analysis');
});
test('buildOnboardingFinalizePayload preserves new onboarding use case ids', () => {
    const payload = (0, onboardingState_1.buildOnboardingFinalizePayload)({
        useCaseId: 'ab_test_analysis',
        starterPrompt: 'Validate this experiment and prepare a ship-or-hold readout.',
        dataChoiceId: 'sample',
        deliverables: ['report', 'presentation'],
        autonomyMode: 'controlled',
        modelId: 'gpt-5.4',
    });
    strict_1.default.equal(payload.useCaseId, 'ab_test_analysis');
    strict_1.default.equal(payload.responses.step1_useCase, 'ab_test_analysis');
    strict_1.default.equal(payload.responses.step2_data.sampleId, 'builtin:ab_test_analysis');
    strict_1.default.deepEqual(payload.responses.step3_deliverables, ['report', 'presentation']);
});
const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
    console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
    if (!entry.ok) {
        console.log('       ', entry.error);
    }
}
console.log(`\nonboardingState.spec — ${results.length - failed.length}/${results.length} passed`);
if (failed.length > 0) {
    process.exitCode = 1;
}
