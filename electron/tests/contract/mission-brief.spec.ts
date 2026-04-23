import assert from 'node:assert/strict';

import {
  buildDeliveryGlobalContext,
  formatRenderResultNotice,
  normalizeDeliveryTenant,
  parseMissionArtifactGate,
  parseMissionArtifactGateError,
  resolveProviderBackedRenderOptions,
  resolveThemeId,
} from '../../src/renderer/components/mission/missionBriefModel';
import { buildRecoveryTaskContractDraft } from '../../src/renderer/components/mission/CreateContractModal';
import { resolveRecoveryTaskContractDefaults } from '../../src/renderer/application/onboarding/recoveryTaskContractDefaults';
import { ONBOARDING_USE_CASE_IDS, resolveUseCase } from '../../src/shared/useCaseMapping';

function run(): void {
  assert.equal(resolveUseCase('reporting').defaultMission, 'reporting');
  assert.equal(resolveUseCase('dashboard').defaultMission, 'dashboard');
  assert.equal(resolveUseCase('weekly_kpi_triage').defaultMission, 'weekly-kpi-triage');
  assert.equal(resolveUseCase('ab_test_analysis').defaultMission, 'ab-test-analysis');
  assert.equal(resolveUseCase('general').defaultMission, 'general');
  assert.equal(resolveUseCase('reporting').defaultAudience, 'executive');
  assert.equal(resolveUseCase('prediction').defaultAudience, 'peer_ds');
  assert.equal(resolveUseCase('weekly_kpi_triage').defaultAudience, 'senior_staff');
  assert.equal(normalizeDeliveryTenant('  acme  '), 'acme');
  assert.equal(normalizeDeliveryTenant(''), 'default');
  assert.equal(resolveThemeId({ theme_id: ' deloitte_v1 ', region: 'apac' }), 'deloitte_v1');
  assert.deepEqual(
    buildDeliveryGlobalContext({ region: 'apac', theme_id: 'legacy_v1' }, ' acme_v2 '),
    { region: 'apac', theme_id: 'acme_v2' },
  );
  assert.deepEqual(
    buildDeliveryGlobalContext({ region: 'apac', theme_id: 'legacy_v1' }, '   '),
    { region: 'apac' },
  );
  assert.deepEqual(
    resolveProviderBackedRenderOptions(false, 'openai/gpt-5.4'),
    { providerBacked: false },
  );
  assert.deepEqual(
    resolveProviderBackedRenderOptions(true, ' openai/gpt-5.4 '),
    { providerBacked: true, model: 'openai/gpt-5.4' },
  );
  assert.deepEqual(
    parseMissionArtifactGate([
      'Mission artifacts [prediction]: required=ds_appendix, evaluation_report, model_card',
      'Mission artifacts gate: contract_missing=evaluation_report',
      'Mission artifacts gate: delivery_missing=model_card',
    ]),
    {
      missionName: 'prediction',
      requiredArtifacts: ['ds_appendix', 'evaluation_report', 'model_card'],
      transitionTarget: null,
      failure: null,
      ready: false,
      issues: [
        {
          kind: 'contract_missing',
          label: 'Missing in contract',
          artifacts: ['evaluation_report'],
        },
        {
          kind: 'delivery_missing',
          label: 'Missing in delivered outputs',
          artifacts: ['model_card'],
        },
      ],
    },
  );
  assert.deepEqual(
    parseMissionArtifactGate([
      'Mission artifacts [data_analysis]: required=exec_brief, ds_appendix',
      'Mission artifacts gate: ready',
    ]),
    {
      missionName: 'data_analysis',
      requiredArtifacts: ['exec_brief', 'ds_appendix'],
      transitionTarget: null,
      failure: null,
      ready: true,
      issues: [],
    },
  );
  assert.deepEqual(
    parseMissionArtifactGateError({
      message: 'Mission required artifacts are missing from required_deliverables: ds_appendix',
      error_code: 'INVALID_TRANSITION',
      metadata: {
        kind: 'mission_artifact_gate',
        transition_target: 'review',
        failure: 'missing_contract_artifacts',
        mission_name: 'data_analysis',
        required_artifacts: ['exec_brief', 'ds_appendix'],
        mapped_required_artifacts: {
          exec_brief: ['exec_brief'],
          ds_appendix: ['ds_appendix'],
        },
        unmapped_required_artifacts: [],
        missing_contract_artifacts: ['ds_appendix'],
        missing_delivery_artifacts: ['exec_brief', 'ds_appendix'],
      },
    }),
    {
      missionName: 'data_analysis',
      requiredArtifacts: ['exec_brief', 'ds_appendix'],
      transitionTarget: 'review',
      failure: 'missing_contract_artifacts',
      ready: false,
      issues: [
        {
          kind: 'contract_missing',
          label: 'Missing in contract',
          artifacts: ['ds_appendix'],
        },
        {
          kind: 'delivery_missing',
          label: 'Missing in delivered outputs',
          artifacts: ['exec_brief', 'ds_appendix'],
        },
      ],
    },
  );
  assert.equal(
    formatRenderResultNotice({
      pack_id: 'DP-2026-001',
      artifact_id: 'ART-2026-001',
      output_path: 'C:/tmp/exec-brief.pptx',
      format: 'pptx',
      verifier_status: 'pass',
      flagged_claims: [],
      pack_status: 'rendered',
      new_version: 4,
      renderer_mode: 'provider-backed',
      renderer_model: 'openai/gpt-5.4',
    }),
    'Rendered ART-2026-001 (pptx) to C:/tmp/exec-brief.pptx. Renderer: provider-backed | Model: openai/gpt-5.4.',
  );
  for (const useCaseId of ONBOARDING_USE_CASE_IDS) {
    const normalizedGoal = `Goal for ${useCaseId}.`;
    const recoveryDefaults = resolveRecoveryTaskContractDefaults(useCaseId);
    const draft = buildRecoveryTaskContractDraft({
      sessionId: `session-recovery-${useCaseId}`,
      useCaseId,
      businessGoal: ` ${normalizedGoal} `,
    });

    assert.deepEqual(draft, {
      session_id: `session-recovery-${useCaseId}`,
      contract_type: recoveryDefaults.useCaseSpec.contractType,
      business_goal: normalizedGoal,
      goal_brief: {
        business_question: normalizedGoal,
        ds_problem_statement: recoveryDefaults.goalBriefTemplate.ds_problem_statement,
        comparison_baseline: recoveryDefaults.goalBriefTemplate.comparison_baseline,
        decision_to_make: recoveryDefaults.goalBriefTemplate.decision_to_make,
        hypothesis: null,
        expected_effort: recoveryDefaults.goalBriefTemplate.expected_effort,
      },
      required_deliverables: recoveryDefaults.useCaseSpec.defaultDeliverableSpecs.map((item) => ({
        ...item,
      })),
      allowed_data_sources: [],
      forbidden_data_patterns: [],
      budget: {},
      autonomy: {},
      authority: recoveryDefaults.useCaseSpec.defaultAuthority,
      audience: recoveryDefaults.useCaseSpec.defaultAudience,
      mission: resolveUseCase(useCaseId).defaultMission,
      created_by: 'user',
    });
  }

  console.log('[contract] PASS mission-brief model');
}

run();
