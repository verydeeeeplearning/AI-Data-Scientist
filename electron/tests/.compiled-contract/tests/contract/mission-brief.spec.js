"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const missionBriefModel_1 = require("../../src/renderer/components/mission/missionBriefModel");
const CreateContractModal_1 = require("../../src/renderer/components/mission/CreateContractModal");
const recoveryTaskContractDefaults_1 = require("../../src/renderer/application/onboarding/recoveryTaskContractDefaults");
const useCaseMapping_1 = require("../../src/shared/useCaseMapping");
function run() {
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('reporting').defaultMission, 'reporting');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('dashboard').defaultMission, 'dashboard');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('weekly_kpi_triage').defaultMission, 'weekly-kpi-triage');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('ab_test_analysis').defaultMission, 'ab-test-analysis');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('general').defaultMission, 'general');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('reporting').defaultAudience, 'executive');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('prediction').defaultAudience, 'peer_ds');
    strict_1.default.equal((0, useCaseMapping_1.resolveUseCase)('weekly_kpi_triage').defaultAudience, 'senior_staff');
    strict_1.default.equal((0, missionBriefModel_1.normalizeDeliveryTenant)('  acme  '), 'acme');
    strict_1.default.equal((0, missionBriefModel_1.normalizeDeliveryTenant)(''), 'default');
    strict_1.default.equal((0, missionBriefModel_1.resolveThemeId)({ theme_id: ' deloitte_v1 ', region: 'apac' }), 'deloitte_v1');
    strict_1.default.deepEqual((0, missionBriefModel_1.buildDeliveryGlobalContext)({ region: 'apac', theme_id: 'legacy_v1' }, ' acme_v2 '), { region: 'apac', theme_id: 'acme_v2' });
    strict_1.default.deepEqual((0, missionBriefModel_1.buildDeliveryGlobalContext)({ region: 'apac', theme_id: 'legacy_v1' }, '   '), { region: 'apac' });
    strict_1.default.deepEqual((0, missionBriefModel_1.resolveProviderBackedRenderOptions)(false, 'openai/gpt-5.4'), { providerBacked: false });
    strict_1.default.deepEqual((0, missionBriefModel_1.resolveProviderBackedRenderOptions)(true, ' openai/gpt-5.4 '), { providerBacked: true, model: 'openai/gpt-5.4' });
    strict_1.default.deepEqual((0, missionBriefModel_1.parseMissionArtifactGate)([
        'Mission artifacts [prediction]: required=ds_appendix, evaluation_report, model_card',
        'Mission artifacts gate: contract_missing=evaluation_report',
        'Mission artifacts gate: delivery_missing=model_card',
    ]), {
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
    });
    strict_1.default.deepEqual((0, missionBriefModel_1.parseMissionArtifactGate)([
        'Mission artifacts [data_analysis]: required=exec_brief, ds_appendix',
        'Mission artifacts gate: ready',
    ]), {
        missionName: 'data_analysis',
        requiredArtifacts: ['exec_brief', 'ds_appendix'],
        transitionTarget: null,
        failure: null,
        ready: true,
        issues: [],
    });
    strict_1.default.deepEqual((0, missionBriefModel_1.parseMissionArtifactGateError)({
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
    }), {
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
    });
    strict_1.default.equal((0, missionBriefModel_1.formatRenderResultNotice)({
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
    }), 'Rendered ART-2026-001 (pptx) to C:/tmp/exec-brief.pptx. Renderer: provider-backed | Model: openai/gpt-5.4.');
    for (const useCaseId of useCaseMapping_1.ONBOARDING_USE_CASE_IDS) {
        const normalizedGoal = `Goal for ${useCaseId}.`;
        const recoveryDefaults = (0, recoveryTaskContractDefaults_1.resolveRecoveryTaskContractDefaults)(useCaseId);
        const draft = (0, CreateContractModal_1.buildRecoveryTaskContractDraft)({
            sessionId: `session-recovery-${useCaseId}`,
            useCaseId,
            businessGoal: ` ${normalizedGoal} `,
        });
        strict_1.default.deepEqual(draft, {
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
            mission: (0, useCaseMapping_1.resolveUseCase)(useCaseId).defaultMission,
            created_by: 'user',
        });
    }
    console.log('[contract] PASS mission-brief model');
}
run();
