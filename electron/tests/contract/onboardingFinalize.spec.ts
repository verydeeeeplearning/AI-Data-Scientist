import assert from 'node:assert/strict';

import { buildOnboardingFinalizePayload } from '../../src/renderer/components/settings/OnboardingWizard';

function run(): void {
  const samplePayload = buildOnboardingFinalizePayload({
    sessionId: 'session-123',
    useCaseId: 'reporting',
    starterPrompt: 'Prepare an executive reporting readout.',
    dataChoiceId: 'sample',
    deliverables: ['report', 'presentation'],
    autonomyMode: 'controlled',
    modelId: 'anthropic/claude-sonnet-4-6',
  });

  assert.equal(samplePayload.sessionId, 'session-123');
  assert.equal(samplePayload.useCaseId, 'reporting');
  assert.equal(samplePayload.starterPrompt, 'Prepare an executive reporting readout.');
  assert.equal(samplePayload.responses.step1_useCase, 'reporting');
  assert.deepEqual(samplePayload.responses.step2_data, {
    type: 'sample',
    sampleId: 'builtin:reporting',
  });
  assert.deepEqual(samplePayload.responses.step3_deliverables, ['report', 'presentation']);
  assert.equal(samplePayload.responses.step4_mode, 'controlled');
  assert.equal(samplePayload.responses.step5_model, 'anthropic/claude-sonnet-4-6');
  assert.equal(samplePayload.responses.step6_confirmed, true);

  const deferredPayload = buildOnboardingFinalizePayload({
    sessionId: null,
    useCaseId: 'sql_exploration',
    starterPrompt: 'Investigate the schema and summarize the key findings.',
    dataChoiceId: 'database_deferred',
    deliverables: ['report'],
    autonomyMode: 'fast',
    modelId: 'openai/gpt-4.1-mini',
  });

  assert.equal(Object.prototype.hasOwnProperty.call(deferredPayload, 'sessionId'), false);
  assert.equal(deferredPayload.useCaseId, 'sql_exploration');
  assert.deepEqual(deferredPayload.responses.step2_data, {
    type: 'database_deferred',
  });
  assert.deepEqual(deferredPayload.responses.step3_deliverables, ['report']);
  assert.equal(deferredPayload.responses.step4_mode, 'fast');
  assert.equal(deferredPayload.responses.step5_model, 'openai/gpt-4.1-mini');
  assert.equal(deferredPayload.responses.step6_confirmed, true);

  const uploadPayload = buildOnboardingFinalizePayload({
    sessionId: 'existing-456',
    useCaseId: 'data_analysis',
    starterPrompt: 'Run an exploratory analysis and surface the main findings.',
    dataChoiceId: 'upload',
    deliverables: ['chart_summary'],
    autonomyMode: 'balanced',
    modelId: 'openai/gpt-4.1',
  });

  assert.deepEqual(uploadPayload.responses.step2_data, {
    type: 'upload',
  });
  assert.deepEqual(uploadPayload.responses.step3_deliverables, ['chart_summary']);
  assert.equal(uploadPayload.responses.step4_mode, 'balanced');
  assert.equal(uploadPayload.responses.step5_model, 'openai/gpt-4.1');

  const abTestPayload = buildOnboardingFinalizePayload({
    sessionId: 'experiment-789',
    useCaseId: 'ab_test_analysis',
    starterPrompt: 'Validate this experiment and recommend whether to ship.',
    dataChoiceId: 'sample',
    deliverables: ['report', 'presentation'],
    autonomyMode: 'controlled',
    modelId: 'openai/gpt-5.4-mini',
  });

  assert.equal(abTestPayload.sessionId, 'experiment-789');
  assert.equal(abTestPayload.useCaseId, 'ab_test_analysis');
  assert.deepEqual(abTestPayload.responses.step2_data, {
    type: 'sample',
    sampleId: 'builtin:ab_test_analysis',
  });
  assert.deepEqual(abTestPayload.responses.step3_deliverables, ['report', 'presentation']);
  assert.equal(abTestPayload.responses.step4_mode, 'controlled');
  assert.equal(abTestPayload.responses.step5_model, 'openai/gpt-5.4-mini');
  assert.equal(abTestPayload.responses.step6_confirmed, true);

  console.log('[contract] PASS onboarding-finalize (20 cases)');
}

run();
