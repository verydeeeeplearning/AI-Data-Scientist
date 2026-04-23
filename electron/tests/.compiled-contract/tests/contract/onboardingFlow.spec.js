"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const OnboardingWizard_1 = require("../../src/renderer/components/settings/OnboardingWizard");
function run() {
    strict_1.default.deepEqual(OnboardingWizard_1.ONBOARDING_PRIMARY_STEPS.map((entry) => entry.id), ['use_case', 'data', 'deliverables', 'mode', 'model', 'confirm']);
    strict_1.default.equal(OnboardingWizard_1.ONBOARDING_PRIMARY_STEPS.length, 6);
    const reportingDefaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('reporting');
    strict_1.default.deepEqual(reportingDefaults.deliverables, ['report', 'presentation']);
    strict_1.default.equal(reportingDefaults.mode, 'controlled');
    const predictionDefaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('prediction');
    strict_1.default.deepEqual(predictionDefaults.deliverables, ['report', 'notebook']);
    strict_1.default.equal(predictionDefaults.mode, 'balanced');
    const sqlDefaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('sql_exploration');
    strict_1.default.deepEqual(sqlDefaults.deliverables, ['report']);
    strict_1.default.equal(sqlDefaults.mode, 'fast');
    const weeklyDefaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('weekly_kpi_triage');
    strict_1.default.deepEqual(weeklyDefaults.deliverables, ['report', 'presentation']);
    strict_1.default.equal(weeklyDefaults.mode, 'fast');
    const abDefaults = (0, OnboardingWizard_1.deriveUseCaseDefaults)('ab_test_analysis');
    strict_1.default.deepEqual(abDefaults.deliverables, ['report', 'presentation']);
    strict_1.default.equal(abDefaults.mode, 'controlled');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('fast'), 'auto');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('balanced'), 'supervised');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToExecutionMode)('controlled'), 'step-by-step');
    strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('auto'), 'fast');
    strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('supervised'), 'balanced');
    strict_1.default.equal((0, OnboardingWizard_1.mapExecutionModeToAutonomyMode)('step-by-step'), 'controlled');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToQualityPreset)('fast'), 'fast');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToQualityPreset)('balanced'), 'balanced');
    strict_1.default.equal((0, OnboardingWizard_1.mapAutonomyModeToQualityPreset)('controlled'), 'best_quality');
    strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
        model: null,
        access: null,
        apiKey: '',
        vaultAvailable: true,
    }), false);
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
        model: { provider: 'openai' },
        access: { ready: false, authType: 'api_key' },
        apiKey: 'sk-test',
        vaultAvailable: false,
    }), false);
    strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
        model: { provider: 'codex' },
        access: { ready: false, authType: 'oauth' },
        apiKey: '',
        vaultAvailable: true,
    }), false);
    strict_1.default.equal((0, OnboardingWizard_1.canContinueFromModelSelection)({
        model: { provider: 'ollama' },
        access: { ready: true, authType: 'local' },
        apiKey: '',
        vaultAvailable: true,
    }), true);
    console.log('[contract] PASS onboarding-flow (20 cases)');
}
run();
