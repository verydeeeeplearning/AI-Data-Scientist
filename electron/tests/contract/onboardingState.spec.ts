/**
 * Contract test for the application/onboarding/onboardingState module.
 *
 * Verifies that the pure state-machine helpers extracted from
 * OnboardingWizard preserve the existing wire contract (finalize payload
 * shape, autonomy mode mapping, advance/back rules).
 */

import assert from 'node:assert/strict';
import {
  applyUseCaseSelection,
  buildInitialOnboardingState,
  buildOnboardingFinalizePayload,
  canAdvanceOnboardingStep,
  deriveUseCaseDefaults,
  isOnboardingPrimaryStepId,
  mapAutonomyModeToExecutionMode,
  mapAutonomyModeToQualityPreset,
  mapExecutionModeToAutonomyMode,
  nextOnboardingStep,
  previousOnboardingStep,
  toggleDeliverable,
  ONBOARDING_PRIMARY_STEP_ORDER,
} from '../../src/renderer/application/onboarding/onboardingState';

const results: Array<{ name: string; ok: boolean; error?: unknown }> = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, ok: true });
  } catch (error) {
    results.push({ name, ok: false, error });
  }
}

test('initial state defaults to use_case step', () => {
  const state = buildInitialOnboardingState({ defaultDataChoice: 'sample' });
  assert.equal(state.step, 'use_case');
  assert.equal(state.dataChoiceId, 'sample');
  assert.equal(state.useCaseId, null);
  assert.equal(state.deliverables.length, 0);
});

test('isOnboardingPrimaryStepId guards string union', () => {
  assert.equal(isOnboardingPrimaryStepId('use_case'), true);
  assert.equal(isOnboardingPrimaryStepId('confirm'), true);
  assert.equal(isOnboardingPrimaryStepId('not-a-step'), false);
});

test('deriveUseCaseDefaults returns curated deliverables per use case', () => {
  assert.deepEqual(deriveUseCaseDefaults('reporting'), {
    deliverables: ['report', 'presentation'],
    mode: 'controlled',
  });
  assert.deepEqual(deriveUseCaseDefaults('sql_exploration'), {
    deliverables: ['report'],
    mode: 'fast',
  });
  assert.deepEqual(deriveUseCaseDefaults('weekly_kpi_triage'), {
    deliverables: ['report', 'presentation'],
    mode: 'fast',
  });
  assert.deepEqual(deriveUseCaseDefaults('ab_test_analysis'), {
    deliverables: ['report', 'presentation'],
    mode: 'controlled',
  });
});

test('autonomy <-> execution mode mapping is bijective', () => {
  for (const mode of ['fast', 'balanced', 'controlled'] as const) {
    const exec = mapAutonomyModeToExecutionMode(mode);
    const back = mapExecutionModeToAutonomyMode(exec);
    assert.equal(back, mode);
  }
});

test('autonomy mode maps to quality preset', () => {
  assert.equal(mapAutonomyModeToQualityPreset('fast'), 'fast');
  assert.equal(mapAutonomyModeToQualityPreset('balanced'), 'balanced');
  assert.equal(mapAutonomyModeToQualityPreset('controlled'), 'best_quality');
});

test('next/previous step traversal honors fixed order', () => {
  assert.equal(nextOnboardingStep('use_case'), 'data');
  assert.equal(nextOnboardingStep('model'), 'notify');
  assert.equal(previousOnboardingStep('confirm'), 'notify');
  assert.equal(nextOnboardingStep('confirm'), null);
  assert.equal(previousOnboardingStep('use_case'), null);
  assert.equal(previousOnboardingStep('mode'), 'deliverables');
  assert.equal(ONBOARDING_PRIMARY_STEP_ORDER.length, 7);
});

test('canAdvanceOnboardingStep enforces selection invariants', () => {
  const empty = buildInitialOnboardingState({ defaultDataChoice: 'upload' });
  assert.equal(canAdvanceOnboardingStep(empty), false, 'use_case requires a selection');

  const withUseCase = applyUseCaseSelection(empty, 'data_analysis');
  assert.equal(canAdvanceOnboardingStep({ ...withUseCase, step: 'deliverables' }), true);

  const cleared = { ...withUseCase, step: 'deliverables' as const, deliverables: [] };
  assert.equal(canAdvanceOnboardingStep(cleared), false, 'deliverables empty must block');

  assert.equal(
    canAdvanceOnboardingStep({ ...withUseCase, step: 'model', modelId: null }),
    false,
    'model step requires a chosen model',
  );
  assert.equal(
    canAdvanceOnboardingStep({ ...withUseCase, step: 'model', modelId: 'gpt-4o' }),
    true,
  );
});

test('toggleDeliverable adds and removes deliverables idempotently', () => {
  const base = applyUseCaseSelection(
    buildInitialOnboardingState({ defaultDataChoice: 'upload' }),
    'general',
  );
  const added = toggleDeliverable(base, 'notebook');
  assert.ok(added.deliverables.includes('notebook'));
  const removed = toggleDeliverable(added, 'notebook');
  assert.ok(!removed.deliverables.includes('notebook'));
});

test('buildOnboardingFinalizePayload emits the documented wire contract', () => {
  const payload = buildOnboardingFinalizePayload({
    sessionId: 'sess-1',
    useCaseId: 'data_analysis',
    starterPrompt: 'Profile this dataset',
    dataChoiceId: 'sample',
    deliverables: ['chart_summary'],
    autonomyMode: 'balanced',
    modelId: 'claude-opus-4-7',
  });
  assert.equal(payload.sessionId, 'sess-1');
  assert.equal(payload.useCaseId, 'data_analysis');
  assert.deepEqual(payload.responses.step3_deliverables, ['chart_summary']);
  assert.equal(payload.responses.step5_model, 'claude-opus-4-7');
  assert.deepEqual(payload.responses.step6_notify, {
    choice: 'desktop_only',
    telegramConnected: false,
  });
  assert.equal(payload.responses.step6_confirmed, true);
  assert.equal(payload.responses.step7_confirmed, true);
  assert.equal(payload.responses.step2_data.sampleId, 'builtin:data_analysis');
});

test('buildOnboardingFinalizePayload preserves new onboarding use case ids', () => {
  const payload = buildOnboardingFinalizePayload({
    useCaseId: 'ab_test_analysis',
    starterPrompt: 'Validate this experiment and prepare a ship-or-hold readout.',
    dataChoiceId: 'sample',
    deliverables: ['report', 'presentation'],
    autonomyMode: 'controlled',
    modelId: 'gpt-5.4',
  });

  assert.equal(payload.useCaseId, 'ab_test_analysis');
  assert.equal(payload.responses.step1_useCase, 'ab_test_analysis');
  assert.equal(payload.responses.step2_data.sampleId, 'builtin:ab_test_analysis');
  assert.deepEqual(payload.responses.step3_deliverables, ['report', 'presentation']);
});

const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
  console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
  if (!entry.ok) {
    console.log('       ', entry.error);
  }
}
console.log(
  `\nonboardingState.spec — ${results.length - failed.length}/${results.length} passed`,
);

if (failed.length > 0) {
  process.exitCode = 1;
}
