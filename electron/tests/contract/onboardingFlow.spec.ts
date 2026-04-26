import assert from 'node:assert/strict';

import {
  canContinueFromModelSelection,
  deriveUseCaseDefaults,
  mapAutonomyModeToExecutionMode,
  mapAutonomyModeToQualityPreset,
  mapExecutionModeToAutonomyMode,
  ONBOARDING_PRIMARY_STEPS,
} from '../../src/renderer/components/settings/OnboardingWizard';

function run(): void {
  assert.deepEqual(
    ONBOARDING_PRIMARY_STEPS.map((entry) => entry.id),
    ['use_case', 'data', 'deliverables', 'mode', 'model', 'notify', 'confirm'],
  );
  assert.equal(ONBOARDING_PRIMARY_STEPS.length, 7);

  const reportingDefaults = deriveUseCaseDefaults('reporting');
  assert.deepEqual(reportingDefaults.deliverables, ['report', 'presentation']);
  assert.equal(reportingDefaults.mode, 'controlled');

  const predictionDefaults = deriveUseCaseDefaults('prediction');
  assert.deepEqual(predictionDefaults.deliverables, ['report', 'notebook']);
  assert.equal(predictionDefaults.mode, 'balanced');

  const sqlDefaults = deriveUseCaseDefaults('sql_exploration');
  assert.deepEqual(sqlDefaults.deliverables, ['report']);
  assert.equal(sqlDefaults.mode, 'fast');

  const weeklyDefaults = deriveUseCaseDefaults('weekly_kpi_triage');
  assert.deepEqual(weeklyDefaults.deliverables, ['report', 'presentation']);
  assert.equal(weeklyDefaults.mode, 'fast');

  const abDefaults = deriveUseCaseDefaults('ab_test_analysis');
  assert.deepEqual(abDefaults.deliverables, ['report', 'presentation']);
  assert.equal(abDefaults.mode, 'controlled');

  assert.equal(mapAutonomyModeToExecutionMode('fast'), 'auto');
  assert.equal(mapAutonomyModeToExecutionMode('balanced'), 'supervised');
  assert.equal(mapAutonomyModeToExecutionMode('controlled'), 'step-by-step');

  assert.equal(mapExecutionModeToAutonomyMode('auto'), 'fast');
  assert.equal(mapExecutionModeToAutonomyMode('supervised'), 'balanced');
  assert.equal(mapExecutionModeToAutonomyMode('step-by-step'), 'controlled');

  assert.equal(mapAutonomyModeToQualityPreset('fast'), 'fast');
  assert.equal(mapAutonomyModeToQualityPreset('balanced'), 'balanced');
  assert.equal(mapAutonomyModeToQualityPreset('controlled'), 'best_quality');

  assert.equal(
    canContinueFromModelSelection({
      model: null,
      access: null,
      apiKey: '',
      vaultAvailable: true,
    }),
    false,
  );

  assert.equal(
    canContinueFromModelSelection({
      model: { provider: 'openai' } as { provider: string },
      access: { ready: false, authType: 'api_key' },
      apiKey: '',
      vaultAvailable: true,
    }),
    false,
  );

  assert.equal(
    canContinueFromModelSelection({
      model: { provider: 'openai' } as { provider: string },
      access: { ready: false, authType: 'api_key' },
      apiKey: 'sk-test',
      vaultAvailable: true,
    }),
    true,
  );

  assert.equal(
    canContinueFromModelSelection({
      model: { provider: 'openai' } as { provider: string },
      access: { ready: false, authType: 'api_key' },
      apiKey: 'sk-test',
      vaultAvailable: false,
    }),
    false,
  );

  assert.equal(
    canContinueFromModelSelection({
      model: { provider: 'codex' } as { provider: string },
      access: { ready: false, authType: 'oauth' },
      apiKey: '',
      vaultAvailable: true,
    }),
    false,
  );

  assert.equal(
    canContinueFromModelSelection({
      model: { provider: 'ollama' } as { provider: string },
      access: { ready: true, authType: 'local' },
      apiKey: '',
      vaultAvailable: true,
    }),
    true,
  );

  console.log('[contract] PASS onboarding-flow (20 cases)');
}

run();
