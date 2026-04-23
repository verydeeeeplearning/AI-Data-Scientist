import assert from 'node:assert/strict';

import {
  buildOnboardingFinalizePayload,
  canContinueFromModelSelection,
  deriveUseCaseDefaults,
  mapAutonomyModeToExecutionMode,
  mapAutonomyModeToQualityPreset,
  mapExecutionModeToAutonomyMode,
  ONBOARDING_PRIMARY_STEPS,
} from '../../src/renderer/components/settings/OnboardingWizard';

function run(): void {
  {
    assert.deepEqual(
      ONBOARDING_PRIMARY_STEPS.map((entry) => entry.id),
      ['use_case', 'data', 'deliverables', 'mode', 'model', 'confirm'],
    );
  }

  {
    const defaults = deriveUseCaseDefaults('reporting');
    assert.deepEqual(defaults.deliverables, ['report', 'presentation']);
    assert.equal(defaults.mode, 'controlled');
  }

  {
    const defaults = deriveUseCaseDefaults('weekly_kpi_triage');
    assert.deepEqual(defaults.deliverables, ['report', 'presentation']);
    assert.equal(defaults.mode, 'fast');
  }

  {
    const defaults = deriveUseCaseDefaults('ab_test_analysis');
    assert.deepEqual(defaults.deliverables, ['report', 'presentation']);
    assert.equal(defaults.mode, 'controlled');
  }

  {
    assert.equal(mapAutonomyModeToExecutionMode('fast'), 'auto');
    assert.equal(mapAutonomyModeToExecutionMode('balanced'), 'supervised');
    assert.equal(mapAutonomyModeToExecutionMode('controlled'), 'step-by-step');
    assert.equal(mapExecutionModeToAutonomyMode('auto'), 'fast');
    assert.equal(mapExecutionModeToAutonomyMode('step-by-step'), 'controlled');
    assert.equal(mapExecutionModeToAutonomyMode('unknown'), 'balanced');
    assert.equal(mapAutonomyModeToQualityPreset('fast'), 'fast');
    assert.equal(mapAutonomyModeToQualityPreset('controlled'), 'best_quality');
  }

  {
    const payload = buildOnboardingFinalizePayload({
      sessionId: 'session-42',
      useCaseId: 'prediction',
      starterPrompt: 'Investigate churn risk for the next quarter.',
      dataChoiceId: 'sample',
      deliverables: ['report', 'notebook'],
      autonomyMode: 'balanced',
      modelId: 'anthropic/claude-sonnet-4-6',
    });

    assert.equal(payload.sessionId, 'session-42');
    assert.equal(payload.useCaseId, 'prediction');
    assert.equal(payload.responses.step1_useCase, 'prediction');
    assert.deepEqual(payload.responses.step2_data, {
      type: 'sample',
      sampleId: 'builtin:prediction',
    });
    assert.deepEqual(payload.responses.step3_deliverables, ['report', 'notebook']);
    assert.equal(payload.responses.step4_mode, 'balanced');
    assert.equal(payload.responses.step5_model, 'anthropic/claude-sonnet-4-6');
    assert.equal(payload.responses.step6_confirmed, true);
  }

  {
    assert.equal(
      canContinueFromModelSelection({
        model: { provider: 'openai' },
        access: { ready: false, authType: 'api_key' },
        apiKey: '',
        vaultAvailable: true,
      }),
      false,
    );
    assert.equal(
      canContinueFromModelSelection({
        model: { provider: 'openai' },
        access: { ready: false, authType: 'api_key' },
        apiKey: 'sk-test',
        vaultAvailable: true,
      }),
      true,
    );
    assert.equal(
      canContinueFromModelSelection({
        model: { provider: 'anthropic' },
        access: { ready: true, authType: 'api_key' },
        apiKey: '',
        vaultAvailable: false,
      }),
      true,
    );
    assert.equal(
      canContinueFromModelSelection({
        model: { provider: 'openai' },
        access: { ready: false, authType: 'oauth' },
        apiKey: '',
        vaultAvailable: true,
      }),
      false,
    );
  }

  console.log('[contract] PASS onboarding-wizard (18 cases)');
}

run();
