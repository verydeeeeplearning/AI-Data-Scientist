"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const OnboardingWizard_1 = require("../../src/renderer/components/settings/OnboardingWizard");
function run() {
    {
        strict_1.default.deepEqual(OnboardingWizard_1.ONBOARDING_PRIMARY_STEPS.map((entry) => entry.id), ['use_case', 'data', 'deliverables', 'mode', 'model', 'notify', 'confirm']);
    }
    {
        const defaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('reporting');
        strict_1.default.deepEqual(defaults.deliverables, ['report', 'presentation']);
        strict_1.default.equal(defaults.mode, 'controlled');
    }
    {
        const defaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('weekly_kpi_triage');
        strict_1.default.deepEqual(defaults.deliverables, ['report', 'presentation']);
        strict_1.default.equal(defaults.mode, 'fast');
    }
    {
        const defaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('ab_test_analysis');
        strict_1.default.deepEqual(defaults.deliverables, ['report', 'presentation']);
        strict_1.default.equal(defaults.mode, 'controlled');
    }
    {
        strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('fast'), 'auto');
        strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('balanced'), 'supervised');
        strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('controlled'), 'step-by-step');
        strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('auto'), 'fast');
        strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('step-by-step'), 'controlled');
        strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('unknown'), 'balanced');
        strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToQualityPreset)('fast'), 'fast');
        strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToQualityPreset)('controlled'), 'best_quality');
    }
    {
        const payload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
            sessionId: 'session-42',
            useCaseId: 'prediction',
            starterPrompt: 'Investigate churn risk for the next quarter.',
            dataChoiceId: 'sample',
            deliverables: ['report', 'notebook'],
            autonomyMode: 'balanced',
            modelId: 'anthropic/claude-sonnet-4-6',
        });
        strict_1.default.equal(payload.sessionId, 'session-42');
        strict_1.default.equal(payload.useCaseId, 'prediction');
        strict_1.default.equal(payload.responses.step1_useCase, 'prediction');
        strict_1.default.deepEqual(payload.responses.step2_data, {
            type: 'sample',
            sampleId: 'builtin:prediction',
        });
        strict_1.default.deepEqual(payload.responses.step3_deliverables, ['report', 'notebook']);
        strict_1.default.equal(payload.responses.step4_mode, 'balanced');
        strict_1.default.equal(payload.responses.step5_model, 'anthropic/claude-sonnet-4-6');
        strict_1.default.deepEqual(payload.responses.step6_notify, {
            choice: 'desktop_only',
            telegramConnected: false,
        });
        strict_1.default.equal(payload.responses.step6_confirmed, true);
        strict_1.default.equal(payload.responses.step7_confirmed, true);
    }
    {
        strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
            model: { provider: 'openai' },
            access: { ready: false, authType: 'api_key' },
            apiKey: '',
            vaultAvailable: true,
        }), false);
        strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
            model: { provider: 'openai' },
            access: { ready: false, authType: 'api_key' },
            apiKey: 'sk-test',
            vaultAvailable: true,
        }), true);
        strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
            model: { provider: 'anthropic' },
            access: { ready: true, authType: 'api_key' },
            apiKey: '',
            vaultAvailable: false,
        }), true);
        strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
            model: { provider: 'openai' },
            access: { ready: false, authType: 'oauth' },
            apiKey: '',
            vaultAvailable: true,
        }), false);
    }
    console.log('[contract] PASS onboarding-wizard (18 cases)');
}
run();
