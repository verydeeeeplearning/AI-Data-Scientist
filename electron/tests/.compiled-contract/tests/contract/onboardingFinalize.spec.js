"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const OnboardingWizard_1 = require("../../src/renderer/components/settings/OnboardingWizard");
function run() {
    const samplePayload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
        sessionId: 'session-123',
        useCaseId: 'reporting',
        starterPrompt: 'Prepare an executive reporting readout.',
        dataChoiceId: 'sample',
        deliverables: ['report', 'presentation'],
        autonomyMode: 'controlled',
        modelId: 'anthropic/claude-sonnet-4-6',
    });
    strict_1.default.equal(samplePayload.sessionId, 'session-123');
    strict_1.default.equal(samplePayload.useCaseId, 'reporting');
    strict_1.default.equal(samplePayload.starterPrompt, 'Prepare an executive reporting readout.');
    strict_1.default.equal(samplePayload.responses.step1_useCase, 'reporting');
    strict_1.default.deepEqual(samplePayload.responses.step2_data, {
        type: 'sample',
        sampleId: 'builtin:reporting',
    });
    strict_1.default.deepEqual(samplePayload.responses.step3_deliverables, ['report', 'presentation']);
    strict_1.default.equal(samplePayload.responses.step4_mode, 'controlled');
    strict_1.default.equal(samplePayload.responses.step5_model, 'anthropic/claude-sonnet-4-6');
    strict_1.default.deepEqual(samplePayload.responses.step6_notify, {
        choice: 'desktop_only',
        telegramConnected: false,
    });
    strict_1.default.equal(samplePayload.responses.step6_confirmed, true);
    strict_1.default.equal(samplePayload.responses.step7_confirmed, true);
    const deferredPayload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
        sessionId: null,
        useCaseId: 'sql_exploration',
        starterPrompt: 'Investigate the schema and summarize the key findings.',
        dataChoiceId: 'database_deferred',
        deliverables: ['report'],
        autonomyMode: 'fast',
        modelId: 'openai/gpt-4.1-mini',
    });
    strict_1.default.equal(Object.prototype.hasOwnProperty.call(deferredPayload, 'sessionId'), false);
    strict_1.default.equal(deferredPayload.useCaseId, 'sql_exploration');
    strict_1.default.deepEqual(deferredPayload.responses.step2_data, {
        type: 'database_deferred',
    });
    strict_1.default.deepEqual(deferredPayload.responses.step3_deliverables, ['report']);
    strict_1.default.equal(deferredPayload.responses.step4_mode, 'fast');
    strict_1.default.equal(deferredPayload.responses.step5_model, 'openai/gpt-4.1-mini');
    strict_1.default.deepEqual(deferredPayload.responses.step6_notify, {
        choice: 'desktop_only',
        telegramConnected: false,
    });
    strict_1.default.equal(deferredPayload.responses.step6_confirmed, true);
    const uploadPayload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
        sessionId: 'existing-456',
        useCaseId: 'data_analysis',
        starterPrompt: 'Run an exploratory analysis and surface the main findings.',
        dataChoiceId: 'upload',
        deliverables: ['chart_summary'],
        autonomyMode: 'balanced',
        modelId: 'openai/gpt-4.1',
    });
    strict_1.default.deepEqual(uploadPayload.responses.step2_data, {
        type: 'upload',
    });
    strict_1.default.deepEqual(uploadPayload.responses.step3_deliverables, ['chart_summary']);
    strict_1.default.equal(uploadPayload.responses.step4_mode, 'balanced');
    strict_1.default.equal(uploadPayload.responses.step5_model, 'openai/gpt-4.1');
    const abTestPayload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
        sessionId: 'experiment-789',
        useCaseId: 'ab_test_analysis',
        starterPrompt: 'Validate this experiment and recommend whether to ship.',
        dataChoiceId: 'sample',
        deliverables: ['report', 'presentation'],
        autonomyMode: 'controlled',
        modelId: 'openai/gpt-5.4-mini',
    });
    strict_1.default.equal(abTestPayload.sessionId, 'experiment-789');
    strict_1.default.equal(abTestPayload.useCaseId, 'ab_test_analysis');
    strict_1.default.deepEqual(abTestPayload.responses.step2_data, {
        type: 'sample',
        sampleId: 'builtin:ab_test_analysis',
    });
    strict_1.default.deepEqual(abTestPayload.responses.step3_deliverables, ['report', 'presentation']);
    strict_1.default.equal(abTestPayload.responses.step4_mode, 'controlled');
    strict_1.default.equal(abTestPayload.responses.step5_model, 'openai/gpt-5.4-mini');
    strict_1.default.deepEqual(abTestPayload.responses.step6_notify, {
        choice: 'desktop_only',
        telegramConnected: false,
    });
    strict_1.default.equal(abTestPayload.responses.step6_confirmed, true);
    const telegramPayload = (0, OnboardingWizard_1.buildOnboardingFinalizePayload)({
        sessionId: 'telegram-999',
        useCaseId: 'general',
        starterPrompt: 'Help me analyze this workspace.',
        dataChoiceId: 'upload',
        deliverables: ['report'],
        autonomyMode: 'balanced',
        modelId: 'anthropic/claude-sonnet-4-6',
        notifyChoice: 'telegram',
        telegramConnected: true,
        telegramChatId: 'chat-1',
        telegramBotUsername: 'demo_bot',
    });
    strict_1.default.deepEqual(telegramPayload.responses.step6_notify, {
        choice: 'telegram',
        telegramConnected: true,
        telegramChatId: 'chat-1',
        telegramBotUsername: 'demo_bot',
    });
    strict_1.default.equal(telegramPayload.responses.step7_confirmed, true);
    console.log('[contract] PASS onboarding-finalize (32 cases)');
}
run();
