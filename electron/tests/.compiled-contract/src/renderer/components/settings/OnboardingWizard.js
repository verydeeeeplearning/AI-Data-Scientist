"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ONBOARDING_PRIMARY_STEPS = void 0;
exports.deriveUseCaseDefaults = deriveUseCaseDefaults;
exports.mapAutonomyModeToExecutionMode = mapAutonomyModeToExecutionMode;
exports.mapExecutionModeToAutonomyMode = mapExecutionModeToAutonomyMode;
exports.mapAutonomyModeToQualityPreset = mapAutonomyModeToQualityPreset;
exports.buildOnboardingFinalizePayload = buildOnboardingFinalizePayload;
exports.canContinueFromModelSelection = canContinueFromModelSelection;
exports.OnboardingWizard = OnboardingWizard;
const jsx_runtime_1 = require("react/jsx-runtime");
/// <reference path="../../vite-env.d.ts" />
/**
 * Product onboarding wizard:
 * Wave 2 staged flow -> use case -> data -> deliverables -> mode -> model -> confirm.
 */
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const recommendModel_1 = require("../../application/llm/recommendModel");
const onboardingTelemetry_1 = require("../../application/onboarding/onboardingTelemetry");
const onboardingState_1 = require("../../application/onboarding/onboardingState");
const useProviderAuth_1 = require("../../hooks/useProviderAuth");
const observability_1 = require("../../observability");
const agentStore_1 = require("../../stores/agentStore");
const authStore_1 = require("../../stores/authStore");
const chatStore_1 = require("../../stores/chatStore");
const configStore_1 = require("../../stores/configStore");
const i18nStore_1 = require("../../stores/i18nStore");
const telegramStore_1 = require("../../stores/telegramStore");
const mainIpcErrors_1 = require("../../utils/mainIpcErrors");
const modelAuth_1 = require("../../utils/modelAuth");
const qualityPreset_1 = require("../../utils/qualityPreset");
const CapabilityBadge_1 = require("./CapabilityBadge");
const LocaleSelector_1 = require("./LocaleSelector");
const TelegramConnectFlow_1 = require("./telegram/TelegramConnectFlow");
const NEEDS_API_KEY = new Set([
    'anthropic',
    'openai',
    'groq',
    'deepseek',
    'minimax',
    'qwen',
    'zhipu',
    'moonshot',
]);
const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';
exports.ONBOARDING_PRIMARY_STEPS = [
    { id: 'use_case', label: 'Use Case' },
    { id: 'data', label: 'Data' },
    { id: 'deliverables', label: 'Deliverables' },
    { id: 'mode', label: 'Mode' },
    { id: 'model', label: 'Model' },
    { id: 'notify', label: 'Notify' },
    { id: 'confirm', label: 'Confirm' },
];
function buildUseCases(t) {
    return [
        {
            id: 'data_analysis',
            title: t('onboarding.use_case.option.data_analysis.title'),
            description: t('onboarding.use_case.option.data_analysis.description'),
            starterPrompt: t('onboarding.use_case.option.data_analysis.starter_prompt'),
            systemContext: t('onboarding.use_case.option.data_analysis.system_context'),
            icon: lucide_react_1.Search,
        },
        {
            id: 'reporting',
            title: t('onboarding.use_case.option.reporting.title'),
            description: t('onboarding.use_case.option.reporting.description'),
            starterPrompt: t('onboarding.use_case.option.reporting.starter_prompt'),
            systemContext: t('onboarding.use_case.option.reporting.system_context'),
            icon: lucide_react_1.FileText,
        },
        {
            id: 'prediction',
            title: t('onboarding.use_case.option.prediction.title'),
            description: t('onboarding.use_case.option.prediction.description'),
            starterPrompt: t('onboarding.use_case.option.prediction.starter_prompt'),
            systemContext: t('onboarding.use_case.option.prediction.system_context'),
            icon: lucide_react_1.LineChart,
        },
        {
            id: 'dashboard',
            title: t('onboarding.use_case.option.dashboard.title'),
            description: t('onboarding.use_case.option.dashboard.description'),
            starterPrompt: t('onboarding.use_case.option.dashboard.starter_prompt'),
            systemContext: t('onboarding.use_case.option.dashboard.system_context'),
            icon: lucide_react_1.Presentation,
        },
        {
            id: 'sql_exploration',
            title: t('onboarding.use_case.option.sql_exploration.title'),
            description: t('onboarding.use_case.option.sql_exploration.description'),
            starterPrompt: t('onboarding.use_case.option.sql_exploration.starter_prompt'),
            systemContext: t('onboarding.use_case.option.sql_exploration.system_context'),
            icon: lucide_react_1.BarChart3,
        },
        {
            id: 'weekly_kpi_triage',
            title: t('onboarding.use_case.option.weekly_kpi_triage.title'),
            description: t('onboarding.use_case.option.weekly_kpi_triage.description'),
            starterPrompt: t('onboarding.use_case.option.weekly_kpi_triage.starter_prompt'),
            systemContext: t('onboarding.use_case.option.weekly_kpi_triage.system_context'),
            icon: lucide_react_1.BarChart3,
        },
        {
            id: 'ab_test_analysis',
            title: t('onboarding.use_case.option.ab_test_analysis.title'),
            description: t('onboarding.use_case.option.ab_test_analysis.description'),
            starterPrompt: t('onboarding.use_case.option.ab_test_analysis.starter_prompt'),
            systemContext: t('onboarding.use_case.option.ab_test_analysis.system_context'),
            icon: lucide_react_1.LineChart,
        },
        {
            id: 'general',
            title: t('onboarding.use_case.option.general.title'),
            description: t('onboarding.use_case.option.general.description'),
            starterPrompt: t('onboarding.use_case.option.general.starter_prompt'),
            systemContext: t('onboarding.use_case.option.general.system_context'),
            icon: lucide_react_1.Bot,
        },
    ];
}
function buildObservabilityChoices(t) {
    return [
        {
            id: 'none',
            title: t('onboarding.privacy.option.none.title'),
            description: t('onboarding.privacy.option.none.description'),
        },
        {
            id: 'crash_only',
            title: t('onboarding.privacy.option.crash_only.title'),
            description: t('onboarding.privacy.option.crash_only.description'),
        },
        {
            id: 'crash_and_telemetry',
            title: t('onboarding.privacy.option.crash_and_telemetry.title'),
            description: t('onboarding.privacy.option.crash_and_telemetry.description'),
        },
    ];
}
function buildDataChoices(t, sampleApiAvailable) {
    return [
        {
            id: 'upload',
            title: t('onboarding.data.option.upload.title'),
            description: t('onboarding.data.option.upload.description'),
            detail: t('onboarding.data.option.upload.detail'),
            icon: lucide_react_1.Upload,
        },
        {
            id: 'sample',
            title: t('onboarding.data.option.sample.title'),
            description: sampleApiAvailable
                ? t('onboarding.data.option.sample.description')
                : t('onboarding.data.option.sample.description_unavailable'),
            detail: sampleApiAvailable
                ? t('onboarding.data.option.sample.detail')
                : t('onboarding.data.option.sample.detail_unavailable'),
            icon: lucide_react_1.BarChart3,
            disabled: !sampleApiAvailable,
        },
        {
            id: 'database_deferred',
            title: t('onboarding.data.option.database_deferred.title'),
            description: t('onboarding.data.option.database_deferred.description'),
            detail: t('onboarding.data.option.database_deferred.detail'),
            icon: lucide_react_1.Database,
        },
    ];
}
function buildDeliverableChoices(t) {
    return [
        {
            id: 'chart_summary',
            title: t('onboarding.deliverables.option.chart_summary.title'),
            description: t('onboarding.deliverables.option.chart_summary.description'),
            detail: t('onboarding.deliverables.option.chart_summary.detail'),
            icon: lucide_react_1.BarChart3,
        },
        {
            id: 'report',
            title: t('onboarding.deliverables.option.report.title'),
            description: t('onboarding.deliverables.option.report.description'),
            detail: t('onboarding.deliverables.option.report.detail'),
            icon: lucide_react_1.FileText,
        },
        {
            id: 'notebook',
            title: t('onboarding.deliverables.option.notebook.title'),
            description: t('onboarding.deliverables.option.notebook.description'),
            detail: t('onboarding.deliverables.option.notebook.detail'),
            icon: lucide_react_1.LineChart,
        },
        {
            id: 'presentation',
            title: t('onboarding.deliverables.option.presentation.title'),
            description: t('onboarding.deliverables.option.presentation.description'),
            detail: t('onboarding.deliverables.option.presentation.detail'),
            icon: lucide_react_1.Presentation,
        },
    ];
}
function buildAutonomyChoices(t) {
    return [
        {
            id: 'fast',
            title: t('onboarding.mode.option.fast.title'),
            description: t('onboarding.mode.option.fast.description'),
            detail: t('onboarding.mode.option.fast.detail'),
            icon: lucide_react_1.ChevronRight,
        },
        {
            id: 'balanced',
            title: t('onboarding.mode.option.balanced.title'),
            description: t('onboarding.mode.option.balanced.description'),
            detail: t('onboarding.mode.option.balanced.detail'),
            icon: lucide_react_1.Bot,
        },
        {
            id: 'controlled',
            title: t('onboarding.mode.option.controlled.title'),
            description: t('onboarding.mode.option.controlled.description'),
            detail: t('onboarding.mode.option.controlled.detail'),
            icon: lucide_react_1.Check,
        },
    ];
}
function deriveUseCaseDefaults(useCaseId) {
    switch (useCaseId) {
        case 'data_analysis':
            return { deliverables: ['chart_summary'], mode: 'balanced' };
        case 'reporting':
            return { deliverables: ['report', 'presentation'], mode: 'controlled' };
        case 'prediction':
            return { deliverables: ['report', 'notebook'], mode: 'balanced' };
        case 'dashboard':
            return { deliverables: ['chart_summary', 'presentation'], mode: 'balanced' };
        case 'sql_exploration':
            return { deliverables: ['report'], mode: 'fast' };
        case 'weekly_kpi_triage':
            return { deliverables: ['report', 'presentation'], mode: 'fast' };
        case 'ab_test_analysis':
            return { deliverables: ['report', 'presentation'], mode: 'controlled' };
        case 'general':
        default:
            return { deliverables: ['report'], mode: 'balanced' };
    }
}
function mapAutonomyModeToExecutionMode(mode) {
    if (mode === 'fast') {
        return 'auto';
    }
    if (mode === 'controlled') {
        return 'step-by-step';
    }
    return 'supervised';
}
function mapExecutionModeToAutonomyMode(value) {
    if (value === 'auto') {
        return 'fast';
    }
    if (value === 'step-by-step') {
        return 'controlled';
    }
    return 'balanced';
}
function mapAutonomyModeToQualityPreset(mode) {
    if (mode === 'fast') {
        return 'fast';
    }
    if (mode === 'controlled') {
        return 'best_quality';
    }
    return 'balanced';
}
function buildOnboardingFinalizePayload(args) {
    const notifyMetadata = {
        choice: args.notifyChoice ?? 'desktop_only',
        telegramConnected: Boolean(args.telegramConnected),
        ...(args.telegramChatId ? { telegramChatId: args.telegramChatId } : {}),
        ...(args.telegramBotUsername ? { telegramBotUsername: args.telegramBotUsername } : {}),
    };
    return {
        ...(args.sessionId ? { sessionId: args.sessionId } : {}),
        useCaseId: args.useCaseId,
        starterPrompt: args.starterPrompt,
        responses: {
            step1_useCase: args.useCaseId,
            step2_data: {
                type: args.dataChoiceId,
                ...(args.dataChoiceId === 'sample' ? { sampleId: `builtin:${args.useCaseId}` } : {}),
            },
            step3_deliverables: [...args.deliverables],
            step4_mode: args.autonomyMode,
            step5_model: args.modelId,
            step6_notify: notifyMetadata,
            step6_confirmed: true,
            step7_confirmed: true,
        },
    };
}
function canContinueFromModelSelection(args) {
    if (!args.model || !args.access) {
        return false;
    }
    if (args.access.ready) {
        return true;
    }
    if (args.access.authType === 'oauth') {
        return false;
    }
    if (NEEDS_API_KEY.has(args.model.provider)) {
        return args.apiKey.trim().length > 0 && args.vaultAvailable;
    }
    return true;
}
function badgeClasses(ready) {
    return ready ? 'bg-ds-success/15 text-ds-success' : 'bg-amber-500/15 text-amber-300';
}
function findUseCase(useCases, useCaseId) {
    if (!useCaseId) {
        return null;
    }
    return useCases.find((entry) => entry.id === useCaseId) ?? null;
}
function getConnectionHint(model, ready, t) {
    if (ready) {
        return t('onboarding.connect.hint.ready');
    }
    if (model.authType === 'oauth') {
        return t('onboarding.connect.hint.oauth');
    }
    if (model.authType === 'local') {
        return t('onboarding.connect.hint.local');
    }
    return t('onboarding.connect.hint.api_key');
}
function getKeyPlaceholder(provider) {
    const placeholders = {
        anthropic: 'sk-ant-...',
        openai: 'sk-...',
        groq: 'gsk_...',
        deepseek: 'sk-...',
        minimax: 'eyJ...',
        qwen: 'sk-...',
        zhipu: 'your-api-key',
        moonshot: 'sk-...',
    };
    return placeholders[provider] ?? 'your-api-key';
}
function hasCompletedOnboardingBefore() {
    try {
        return (localStorage.getItem(ONBOARDING_STORAGE_KEY) === 'true'
            || localStorage.getItem(LEGACY_ONBOARDING_STORAGE_KEY) === 'true');
    }
    catch {
        return false;
    }
}
function observabilityChoiceFromSettings(errorReportingEnabled, telemetryEnabled) {
    if (!errorReportingEnabled) {
        return 'none';
    }
    return telemetryEnabled ? 'crash_and_telemetry' : 'crash_only';
}
function observabilitySettingsFromChoice(choice) {
    if (choice === 'crash_and_telemetry') {
        return { errorReportingEnabled: true, telemetryEnabled: true };
    }
    if (choice === 'crash_only') {
        return { errorReportingEnabled: true, telemetryEnabled: false };
    }
    return { errorReportingEnabled: false, telemetryEnabled: false };
}
function getBackendBaseUrl(search = window.location.search) {
    const params = new URLSearchParams(search);
    const rawPort = params.get('port');
    const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
    return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}
function extractApiErrorMessage(payload, fallback) {
    if (!payload || typeof payload !== 'object') {
        return fallback;
    }
    const detail = payload.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
        return detail;
    }
    return fallback;
}
async function finalizeOnboardingHandoff(payload, search = window.location.search) {
    const response = await fetch(`${getBackendBaseUrl(search)}/api/onboarding/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        let body = null;
        try {
            body = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractApiErrorMessage(body, `Onboarding finalize failed with status ${response.status}`));
    }
    return (await response.json());
}
function formatDataChoiceTitle(choiceId, t) {
    if (choiceId === 'sample') {
        return t('onboarding.data.option.sample.title');
    }
    if (choiceId === 'database_deferred') {
        return t('onboarding.data.option.database_deferred.title');
    }
    return t('onboarding.data.option.upload.title');
}
function formatDeliverableTitle(choiceId, t) {
    if (choiceId === 'chart_summary') {
        return t('onboarding.deliverables.option.chart_summary.title');
    }
    if (choiceId === 'report') {
        return t('onboarding.deliverables.option.report.title');
    }
    if (choiceId === 'notebook') {
        return t('onboarding.deliverables.option.notebook.title');
    }
    return t('onboarding.deliverables.option.presentation.title');
}
function formatAutonomyModeTitle(choiceId, t) {
    if (choiceId === 'fast') {
        return t('onboarding.mode.option.fast.title');
    }
    if (choiceId === 'controlled') {
        return t('onboarding.mode.option.controlled.title');
    }
    return t('onboarding.mode.option.balanced.title');
}
function formatExecutionModeTitle(choiceId, t) {
    const runtimeMode = mapAutonomyModeToExecutionMode(choiceId);
    if (runtimeMode === 'auto') {
        return t('common.mode.auto');
    }
    if (runtimeMode === 'supervised') {
        return t('common.mode.supervised');
    }
    return t('common.mode.step');
}
function persistOnboardingComplete() {
    try {
        localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
        localStorage.setItem(LEGACY_ONBOARDING_STORAGE_KEY, 'true');
        return true;
    }
    catch {
        return false;
    }
}
function SelectionIndicator({ selected, label, }) {
    return ((0, jsx_runtime_1.jsxs)("span", { className: `inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${selected
            ? 'border-ds-success/30 bg-ds-success/15 text-ds-success'
            : 'border-ds-border bg-ds-surface text-ds-muted'}`, children: [selected ? ((0, jsx_runtime_1.jsx)(lucide_react_1.CheckCircle2, { size: 12, "aria-hidden": "true" })) : ((0, jsx_runtime_1.jsx)(lucide_react_1.Circle, { size: 12, "aria-hidden": "true" })), label] }));
}
function SummaryCard({ selectedUseCase, selectedDataChoiceId, selectedDeliverables, selectedAutonomyMode, selectedModel, selectedModelAccess, t, }) {
    return ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-bg p-5", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.summary.title') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-4 space-y-4", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.summary.use_case') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm font-medium text-ds-text", children: selectedUseCase?.title ?? t('onboarding.summary.use_case_empty') })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.summary.data_plan') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm text-ds-text", children: formatDataChoiceTitle(selectedDataChoiceId, t) })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.summary.deliverables') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm text-ds-text", children: selectedDeliverables.length > 0
                                    ? selectedDeliverables.map((entry) => formatDeliverableTitle(entry, t)).join(', ')
                                    : t('onboarding.summary.deliverables_empty') })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.summary.mode') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm text-ds-text", children: formatAutonomyModeTitle(selectedAutonomyMode, t) }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: [t('onboarding.summary.runtime'), ": ", formatExecutionModeTitle(selectedAutonomyMode, t), " /", ' ', t('onboarding.summary.model_preference'), ": ", formatAutonomyModeTitle(selectedAutonomyMode, t)] })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.summary.model') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm text-ds-text", children: selectedModel?.displayName ?? t('onboarding.summary.model_empty') }), selectedModelAccess && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: [selectedModelAccess.providerLabel, " / ", selectedModelAccess.shortLabel] }))] })] })] }));
}
function OnboardingWizard({ onComplete, rpc, groups, telemetry = onboardingTelemetry_1.NOOP_ONBOARDING_TELEMETRY }) {
    const providerStatuses = (0, authStore_1.useAuthStore)((s) => s.providerStatuses);
    const oauthStatuses = (0, authStore_1.useAuthStore)((s) => s.oauthStatuses);
    const setAuthSnapshot = (0, authStore_1.useAuthStore)((s) => s.setSnapshot);
    const setFirstRun = (0, configStore_1.useConfigStore)((s) => s.setFirstRun);
    const setShowOnboarding = (0, configStore_1.useConfigStore)((s) => s.setShowOnboarding);
    const setPendingStarterPrompt = (0, configStore_1.useConfigStore)((s) => s.setPendingStarterPrompt);
    const setMode = (0, agentStore_1.useAgentStore)((s) => s.setMode);
    const currentSessionId = (0, chatStore_1.useChatStore)((s) => s.sessionId);
    const setSessionId = (0, chatStore_1.useChatStore)((s) => s.setSessionId);
    const telegramPairedChat = (0, telegramStore_1.useTelegramStore)((s) => s.pairedChat);
    const telegramBotIdentity = (0, telegramStore_1.useTelegramStore)((s) => s.botIdentity);
    const { locale, setLocale, t } = (0, i18nStore_1.useI18n)();
    const sampleApiAvailable = Boolean(window.electronAPI?.loadSampleForUseCase);
    const [step, setStep] = (0, react_1.useState)('use_case');
    const [selectedUseCaseId, setSelectedUseCaseId] = (0, react_1.useState)(null);
    const [selectedDataChoiceId, setSelectedDataChoiceId] = (0, react_1.useState)(sampleApiAvailable ? 'sample' : 'upload');
    const [selectedDeliverables, setSelectedDeliverables] = (0, react_1.useState)([]);
    const [selectedAutonomyMode, setSelectedAutonomyMode] = (0, react_1.useState)('balanced');
    const [selectedModel, setSelectedModel] = (0, react_1.useState)(null);
    const [notifyChoice, setNotifyChoice] = (0, react_1.useState)(null);
    const [observabilityChoice, setObservabilityChoice] = (0, react_1.useState)(null);
    const [apiKey, setApiKey] = (0, react_1.useState)('');
    const [loading, setLoading] = (0, react_1.useState)(false);
    const [oauthWaiting, setOauthWaiting] = (0, react_1.useState)(false);
    const [oauthError, setOauthError] = (0, react_1.useState)('');
    const [apiKeyError, setApiKeyError] = (0, react_1.useState)('');
    const [finishError, setFinishError] = (0, react_1.useState)('');
    const [vaultAvailable, setVaultAvailable] = (0, react_1.useState)(true);
    const [sentryConfigured, setSentryConfigured] = (0, react_1.useState)(false);
    const [finalizedSessionId, setFinalizedSessionId] = (0, react_1.useState)(null);
    const allModels = (0, react_1.useMemo)(() => groups.flatMap((group) => group.models), [groups]);
    const useCases = (0, react_1.useMemo)(() => buildUseCases(t), [locale, t]);
    const dataChoices = (0, react_1.useMemo)(() => buildDataChoices(t, sampleApiAvailable), [sampleApiAvailable, t]);
    const deliverableChoices = (0, react_1.useMemo)(() => buildDeliverableChoices(t), [t]);
    const autonomyChoices = (0, react_1.useMemo)(() => buildAutonomyChoices(t), [t]);
    const observabilityChoices = (0, react_1.useMemo)(() => buildObservabilityChoices(t), [locale, t]);
    const selectedUseCase = (0, react_1.useMemo)(() => findUseCase(useCases, selectedUseCaseId), [selectedUseCaseId, useCases]);
    const selectedModelAccess = (0, react_1.useMemo)(() => selectedModel
        ? (0, modelAuth_1.describeModelAccess)({
            modelId: selectedModel.id,
            modelEntry: selectedModel,
            providerStatuses,
            oauthStatuses,
        })
        : null, [oauthStatuses, providerStatuses, selectedModel]);
    const completedOnboardingBefore = (0, react_1.useMemo)(() => hasCompletedOnboardingBefore(), []);
    const readyModelIds = (0, react_1.useMemo)(() => new Set(allModels
        .filter((entry) => (0, modelAuth_1.describeModelAccess)({
        modelId: entry.id,
        modelEntry: entry,
        providerStatuses,
        oauthStatuses,
    }).ready)
        .map((entry) => entry.id)), [allModels, oauthStatuses, providerStatuses]);
    const recommendedModel = (0, react_1.useMemo)(() => (0, recommendModel_1.recommendModel)(allModels, {
        locale,
        taskType: selectedUseCaseId,
        qualityPreset: mapAutonomyModeToQualityPreset(selectedAutonomyMode),
        readyModelIds,
    }), [allModels, locale, readyModelIds, selectedAutonomyMode, selectedUseCaseId]);
    const recommendedReason = recommendedModel?.reasons.map((reason) => t(`llm.recommend.reason.${reason}`)).join(' / ') ?? '';
    const canContinueFromModel = (0, react_1.useMemo)(() => canContinueFromModelSelection({
        model: selectedModel,
        access: selectedModelAccess,
        apiKey,
        vaultAvailable: !window.electronAPI?.getSecretVaultStatus || vaultAvailable,
    }), [apiKey, selectedModel, selectedModelAccess, vaultAvailable]);
    (0, react_1.useEffect)(() => {
        telemetry({
            type: 'onboarding.started',
            alreadyCompletedBefore: completedOnboardingBefore,
        });
        // Telemetry "started" should fire exactly once per wizard mount.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    (0, react_1.useEffect)(() => {
        const stepIndex = onboardingState_1.ONBOARDING_PRIMARY_STEP_ORDER.indexOf(step);
        if (stepIndex >= 0) {
            telemetry({ type: 'onboarding.step_entered', step, stepIndex });
        }
    }, [step, telemetry]);
    (0, react_1.useEffect)(() => {
        if (!window.electronAPI?.getSecretVaultStatus) {
            return;
        }
        void window.electronAPI
            .getSecretVaultStatus()
            .then((status) => {
            setVaultAvailable(status.available);
            if (!status.available) {
                setApiKeyError(status.error ?? t('onboarding.api_key.vault_unavailable'));
            }
        })
            .catch((error) => {
            console.warn('[OnboardingWizard] vault status lookup failed:', error);
        });
    }, [t]);
    (0, react_1.useEffect)(() => {
        let cancelled = false;
        void rpc('config.get')
            .then((result) => {
            if (cancelled) {
                return;
            }
            const config = result.config;
            if (!config || typeof config !== 'object') {
                return;
            }
            const configRecord = config;
            const agent = configRecord.agent && typeof configRecord.agent === 'object'
                ? configRecord.agent
                : null;
            const provider = configRecord.provider && typeof configRecord.provider === 'object'
                ? configRecord.provider
                : null;
            const observability = configRecord.observability && typeof configRecord.observability === 'object'
                ? configRecord.observability
                : null;
            const language = agent?.language;
            if (language === 'ko' || language === 'en' || language === 'ja') {
                if (language !== locale) {
                    setLocale(language);
                }
            }
            const configuredMode = mapExecutionModeToAutonomyMode(agent?.mode);
            if (selectedUseCaseId === null) {
                setSelectedAutonomyMode(configuredMode);
            }
            if (!selectedUseCaseId) {
                const useCaseHint = typeof agent?.use_case_hint === 'string' ? agent.use_case_hint : null;
                const preselectedUseCase = findUseCase(useCases, useCaseHint);
                if (preselectedUseCase) {
                    const defaults = deriveUseCaseDefaults(preselectedUseCase.id);
                    setSelectedUseCaseId(preselectedUseCase.id);
                    setSelectedDeliverables(defaults.deliverables);
                    setSelectedAutonomyMode(configuredMode ?? defaults.mode);
                }
            }
            if (!selectedModel) {
                const defaultModel = typeof provider?.default_model === 'string' ? provider.default_model : null;
                const preselectedModel = defaultModel === null
                    ? null
                    : allModels.find((entry) => entry.id === defaultModel) ?? null;
                if (preselectedModel) {
                    setSelectedModel(preselectedModel);
                }
            }
            const hasSentryDsn = typeof observability?.sentry_dsn === 'string' && observability.sentry_dsn.trim().length > 0;
            const nextErrorReporting = Boolean(observability?.error_reporting_enabled);
            const nextTelemetry = Boolean(observability?.telemetry_enabled);
            setSentryConfigured(hasSentryDsn);
            (0, observability_1.configureRendererObservability)({
                sentryConfigured: hasSentryDsn,
                errorReportingEnabled: nextErrorReporting,
                telemetryEnabled: nextTelemetry,
            });
            setObservabilityChoice((current) => {
                if (current !== null) {
                    return current;
                }
                if (completedOnboardingBefore || nextErrorReporting || nextTelemetry) {
                    return observabilityChoiceFromSettings(nextErrorReporting, nextTelemetry);
                }
                return null;
            });
        })
            .catch((error) => {
            console.warn('[OnboardingWizard] config preload failed:', error);
        });
        return () => {
            cancelled = true;
        };
    }, [allModels, completedOnboardingBefore, locale, rpc, selectedModel, selectedUseCaseId, setLocale, useCases]);
    const handleLocaleChange = async (next) => {
        setLocale(next);
        try {
            await rpc('config.set', { path: 'agent.language', value: next });
        }
        catch (error) {
            console.warn('[OnboardingWizard] failed to sync agent.language:', error);
        }
    };
    const handleUseCaseSelect = (useCaseId) => {
        const defaults = deriveUseCaseDefaults(useCaseId);
        setSelectedUseCaseId(useCaseId);
        setSelectedDeliverables(defaults.deliverables);
        setSelectedAutonomyMode(defaults.mode);
        setFinishError('');
        telemetry({ type: 'onboarding.use_case_selected', useCaseId });
    };
    const handleModelSelect = (model) => {
        setSelectedModel(model);
        setApiKey('');
        setApiKeyError('');
        setOauthError('');
        setFinishError('');
    };
    const toggleDeliverable = (deliverableId) => {
        setFinishError('');
        setSelectedDeliverables((current) => current.includes(deliverableId)
            ? current.filter((entry) => entry !== deliverableId)
            : [...current, deliverableId]);
    };
    const handleOAuthLogin = async () => {
        if (!selectedModel) {
            return;
        }
        setOauthWaiting(true);
        setOauthError('');
        try {
            await rpc('oauth.startLogin', { provider: selectedModel.provider });
            for (let index = 0; index < 300; index += 1) {
                await new Promise((resolve) => setTimeout(resolve, 1000));
                const statusResult = await rpc('oauth.status');
                const providerStatus = statusResult.providers?.[selectedModel.provider];
                if (providerStatus?.authenticated) {
                    setAuthSnapshot(await (0, useProviderAuth_1.fetchAuthSnapshot)(rpc));
                    return;
                }
            }
            setOauthError(t('onboarding.oauth.timeout'));
        }
        catch (error) {
            setOauthError(error instanceof Error ? error.message : String(error));
        }
        finally {
            setOauthWaiting(false);
        }
    };
    const handleSkipOnboarding = () => {
        persistOnboardingComplete();
        setFirstRun(false);
        setShowOnboarding(false);
    };
    const handleFinish = async () => {
        if (!selectedModel || !selectedUseCase || observabilityChoice === null) {
            setFinishError(t('onboarding.error.choose_privacy'));
            return;
        }
        if (selectedDeliverables.length === 0) {
            setFinishError(t('onboarding.error.choose_deliverable'));
            return;
        }
        const qualityPreset = mapAutonomyModeToQualityPreset(selectedAutonomyMode);
        const executionMode = mapAutonomyModeToExecutionMode(selectedAutonomyMode);
        const observabilitySettings = observabilitySettingsFromChoice(observabilityChoice);
        const handoffSessionId = finalizedSessionId ?? currentSessionId;
        const shouldLoadSample = selectedDataChoiceId === 'sample' && sampleApiAvailable;
        setLoading(true);
        setApiKeyError('');
        setFinishError('');
        let starterPromptForChat = selectedUseCase.starterPrompt;
        const finalizeStartedAt = Date.now();
        telemetry({
            type: 'onboarding.finalize_started',
            useCaseId: selectedUseCase.id,
            dataChoiceId: selectedDataChoiceId,
            deliverables: selectedDeliverables,
            autonomyMode: selectedAutonomyMode,
            modelId: selectedModel.id,
        });
        try {
            if (apiKey.trim()
                && NEEDS_API_KEY.has(selectedModel.provider)
                && selectedModelAccess?.ready !== true) {
                if (window.electronAPI?.setApiKey) {
                    const result = await window.electronAPI.setApiKey(selectedModel.provider, apiKey.trim());
                    if (!result.ok) {
                        throw new Error((0, mainIpcErrors_1.resolveMainIpcErrorMessage)(result, 'onboarding.error.api_key_save_failed'));
                    }
                }
                else {
                    await rpc('config.setApiKey', { provider: selectedModel.provider, key: apiKey.trim() });
                }
                setAuthSnapshot(await (0, useProviderAuth_1.fetchAuthSnapshot)(rpc));
            }
            await Promise.all([
                rpc('config.set', { path: 'provider.default_model', value: selectedModel.id }),
                rpc('config.set', { path: 'provider.quality_preset', value: qualityPreset }),
                rpc('config.set', { path: 'agent.mode', value: executionMode }),
                rpc('config.set', { path: 'agent.use_case_hint', value: selectedUseCase.id }),
                rpc('config.set', {
                    path: 'agent.use_case_context',
                    value: selectedUseCase.systemContext,
                }),
                rpc('config.set', {
                    path: 'observability.error_reporting_enabled',
                    value: observabilitySettings.errorReportingEnabled,
                }),
                rpc('config.set', {
                    path: 'observability.telemetry_enabled',
                    value: observabilitySettings.telemetryEnabled,
                }),
            ]);
            (0, observability_1.configureRendererObservability)({
                sentryConfigured,
                errorReportingEnabled: observabilitySettings.errorReportingEnabled,
                telemetryEnabled: observabilitySettings.telemetryEnabled,
            });
            if (window.electronAPI?.updateObservability) {
                await window.electronAPI.updateObservability({
                    errorReportingEnabled: observabilitySettings.errorReportingEnabled,
                    telemetryEnabled: observabilitySettings.telemetryEnabled,
                });
            }
            if (shouldLoadSample) {
                if (!window.electronAPI?.loadSampleForUseCase) {
                    throw new Error(t('onboarding.error.sample_desktop_only'));
                }
                const sampleResult = await window.electronAPI.loadSampleForUseCase(selectedUseCase.id);
                if (!sampleResult.ok) {
                    throw new Error((0, mainIpcErrors_1.resolveMainIpcErrorMessage)(sampleResult, 'onboarding.error.sample_load_failed'));
                }
                const uploaded = await rpc('files.upload', {
                    name: sampleResult.sample.filename,
                    data: sampleResult.sample.data,
                });
                const uploadedPath = typeof uploaded.path === 'string' ? uploaded.path : sampleResult.sample.filename;
                starterPromptForChat = t('onboarding.sample.prompt_anchor', {
                    filename: sampleResult.sample.filename,
                    path: uploadedPath,
                    prompt: selectedUseCase.starterPrompt,
                });
            }
            const resolvedNotifyChoice = notifyChoice === 'telegram' ? 'telegram' : 'desktop_only';
            const telegramConnected = Boolean(telegramPairedChat);
            const finalizePayload = buildOnboardingFinalizePayload({
                sessionId: handoffSessionId,
                useCaseId: selectedUseCase.id,
                starterPrompt: starterPromptForChat,
                dataChoiceId: selectedDataChoiceId,
                deliverables: selectedDeliverables,
                autonomyMode: selectedAutonomyMode,
                modelId: selectedModel.id,
                notifyChoice: resolvedNotifyChoice,
                telegramConnected,
                telegramChatId: telegramPairedChat?.chatId ?? null,
                telegramBotUsername: telegramBotIdentity?.username ?? null,
            });
            const finalizeResult = await finalizeOnboardingHandoff(finalizePayload);
            if (!finalizeResult.sessionId || finalizeResult.sessionId.trim().length === 0) {
                throw new Error(t('onboarding.error.finalize_missing_session'));
            }
            setFinalizedSessionId(finalizeResult.sessionId);
            setSessionId(finalizeResult.sessionId);
            setMode(executionMode);
            persistOnboardingComplete();
            setPendingStarterPrompt(starterPromptForChat);
            telemetry({
                type: 'onboarding.finalize_succeeded',
                useCaseId: selectedUseCase.id,
                modelId: selectedModel.id,
                durationMs: Date.now() - finalizeStartedAt,
            });
            onComplete({
                model: selectedModel.id,
                qualityPreset: (0, qualityPreset_1.normalizeQualityPreset)(qualityPreset),
                useCaseId: selectedUseCase.id,
                starterPrompt: starterPromptForChat,
                notifyChoice: resolvedNotifyChoice,
                telegramConnected,
            });
        }
        catch (error) {
            const reason = error instanceof Error ? error.message : String(error);
            setFinishError(reason);
            setLoading(false);
            telemetry({
                type: 'onboarding.finalize_failed',
                useCaseId: selectedUseCase?.id ?? null,
                modelId: selectedModel?.id ?? null,
                reason,
                durationMs: Date.now() - finalizeStartedAt,
            });
        }
    };
    return ((0, jsx_runtime_1.jsx)("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-ds-bg px-4 py-6", children: (0, jsx_runtime_1.jsxs)("div", { className: "max-h-[calc(100vh-3rem)] w-full max-w-6xl overflow-y-auto pr-1", children: [(0, jsx_runtime_1.jsxs)("div", { className: "mb-8 text-center", children: [(0, jsx_runtime_1.jsx)("div", { className: "mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-ds-accent/20", children: (0, jsx_runtime_1.jsx)(lucide_react_1.Bot, { size: 32, className: "text-ds-accent" }) }), (0, jsx_runtime_1.jsx)("h1", { className: "text-3xl font-bold text-ds-text", children: t('onboarding.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm text-ds-muted", children: t('onboarding.appSubtitle') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.flow.caption') }), (0, jsx_runtime_1.jsx)("div", { className: "mx-auto mt-5 max-w-xl rounded-2xl border border-ds-border bg-ds-surface p-4 text-left", children: (0, jsx_runtime_1.jsx)(LocaleSelector_1.LocaleSelector, { value: locale, onChange: handleLocaleChange, labelKey: "onboarding.locale.label", descriptionKey: "onboarding.locale.description" }) }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: handleSkipOnboarding, className: "mt-4 text-xs font-medium text-ds-muted transition-colors hover:text-ds-text focus:outline-none focus:ring-2 focus:ring-ds-accent/60", children: t('onboarding.skip.action') })] }), (0, jsx_runtime_1.jsx)("div", { className: "mb-6 grid gap-2 md:grid-cols-6", children: exports.ONBOARDING_PRIMARY_STEPS.map((entry, index) => {
                        const activeIndex = exports.ONBOARDING_PRIMARY_STEPS.findIndex((stepEntry) => stepEntry.id === step);
                        const complete = index < activeIndex;
                        const active = entry.id === step;
                        return ((0, jsx_runtime_1.jsxs)("div", { className: `rounded-xl border px-4 py-3 text-left ${active || complete
                                ? 'border-ds-accent/40 bg-ds-accent/10'
                                : 'border-ds-border bg-ds-surface'}`, children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: index + 1 }) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-sm font-medium text-ds-text", children: t(`onboarding.steps.${entry.id}`) })] }, entry.id));
                    }) }), step === 'use_case' && ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-surface p-8", children: [(0, jsx_runtime_1.jsxs)("div", { className: "mb-6", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.use_case.eyebrow') }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.use_case.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm text-ds-muted", children: t('onboarding.use_case.description') })] }), (0, jsx_runtime_1.jsx)("div", { className: "grid gap-4 md:grid-cols-2 xl:grid-cols-3", children: useCases.map((useCase) => {
                                const Icon = useCase.icon;
                                const selected = selectedUseCase?.id === useCase.id;
                                return ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => handleUseCaseSelect(useCase.id), "aria-pressed": selected, className: `rounded-2xl border p-5 text-left shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-ds-accent/60 ${selected
                                        ? 'border-ds-accent bg-ds-accent/10 shadow-ds-accent/10'
                                        : 'border-ds-border bg-ds-bg hover:-translate-y-0.5 hover:border-ds-accent/50 hover:bg-ds-accent/5 hover:shadow-md'}`, children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsx)("div", { className: `inline-flex h-10 w-10 items-center justify-center rounded-xl ${selected ? 'bg-ds-accent text-white' : 'bg-ds-surface text-ds-accent'}`, children: (0, jsx_runtime_1.jsx)(Icon, { size: 18 }) }), (0, jsx_runtime_1.jsx)(SelectionIndicator, { selected: selected, label: selected
                                                        ? t('onboarding.use_case.card.selected')
                                                        : t('onboarding.use_case.card.select') })] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: useCase.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: useCase.description }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-4 rounded-xl border border-ds-border/60 bg-ds-surface p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.use_case.starter_prompt') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs leading-5 text-ds-muted", children: useCase.starterPrompt })] })] }, useCase.id));
                            }) }), (0, jsx_runtime_1.jsx)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex justify-end border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('data'), disabled: !selectedUseCase, className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40", children: [t('onboarding.continue'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] }) })] })), step === 'data' && ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-surface p-8", children: [(0, jsx_runtime_1.jsxs)("div", { className: "grid gap-8 lg:grid-cols-[1.05fr_0.95fr]", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 2 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.data.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.data.description') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-6 grid gap-4 md:grid-cols-3", children: dataChoices.map((choice) => {
                                                const Icon = choice.icon;
                                                const selected = selectedDataChoiceId === choice.id;
                                                return ((0, jsx_runtime_1.jsxs)("button", { type: "button", disabled: choice.disabled, onClick: () => {
                                                        setFinishError('');
                                                        setSelectedDataChoiceId(choice.id);
                                                    }, className: `rounded-2xl border p-5 text-left transition-colors ${selected
                                                        ? 'border-ds-accent/60 bg-ds-accent/10'
                                                        : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'} ${choice.disabled ? 'cursor-not-allowed opacity-50' : ''}`, children: [(0, jsx_runtime_1.jsx)("div", { className: "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent", children: (0, jsx_runtime_1.jsx)(Icon, { size: 18 }) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: choice.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: choice.description }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs leading-5 text-ds-muted/80", children: choice.detail })] }, choice.id));
                                            }) })] }), (0, jsx_runtime_1.jsx)(SummaryCard, { selectedUseCase: selectedUseCase, selectedDataChoiceId: selectedDataChoiceId, selectedDeliverables: selectedDeliverables, selectedAutonomyMode: selectedAutonomyMode, selectedModel: selectedModel, selectedModelAccess: selectedModelAccess, t: t })] }), (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex items-center justify-between border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('use_case'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_use_case') }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('deliverables'), className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover", children: [t('onboarding.continue'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] })] })] })), step === 'deliverables' && ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-surface p-8", children: [(0, jsx_runtime_1.jsxs)("div", { className: "grid gap-8 lg:grid-cols-[1.05fr_0.95fr]", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 3 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.deliverables.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.deliverables.description') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-6 grid gap-4 md:grid-cols-2", children: deliverableChoices.map((choice) => {
                                                const Icon = choice.icon;
                                                const selected = selectedDeliverables.includes(choice.id);
                                                return ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => toggleDeliverable(choice.id), className: `rounded-2xl border p-5 text-left transition-colors ${selected
                                                        ? 'border-ds-accent/60 bg-ds-accent/10'
                                                        : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'}`, children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent", children: (0, jsx_runtime_1.jsx)(Icon, { size: 18 }) }), selected && ((0, jsx_runtime_1.jsx)("span", { className: "rounded-full bg-ds-success/15 px-2 py-0.5 text-[10px] font-medium text-ds-success", children: t('onboarding.selected') }))] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: choice.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: choice.description }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs leading-5 text-ds-muted/80", children: choice.detail })] }, choice.id));
                                            }) })] }), (0, jsx_runtime_1.jsx)(SummaryCard, { selectedUseCase: selectedUseCase, selectedDataChoiceId: selectedDataChoiceId, selectedDeliverables: selectedDeliverables, selectedAutonomyMode: selectedAutonomyMode, selectedModel: selectedModel, selectedModelAccess: selectedModelAccess, t: t })] }), (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex items-center justify-between border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('data'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_data') }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('mode'), disabled: selectedDeliverables.length === 0, className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40", children: [t('onboarding.continue'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] })] })] })), step === 'mode' && ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-surface p-8", children: [(0, jsx_runtime_1.jsxs)("div", { className: "grid gap-8 lg:grid-cols-[1.05fr_0.95fr]", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 4 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.mode.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.mode.description') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-6 grid gap-4 md:grid-cols-3", children: autonomyChoices.map((choice) => {
                                                const Icon = choice.icon;
                                                const selected = selectedAutonomyMode === choice.id;
                                                return ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => {
                                                        setFinishError('');
                                                        setSelectedAutonomyMode(choice.id);
                                                    }, className: `rounded-2xl border p-5 text-left transition-colors ${selected
                                                        ? 'border-ds-accent/60 bg-ds-accent/10'
                                                        : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'}`, children: [(0, jsx_runtime_1.jsx)("div", { className: "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent", children: (0, jsx_runtime_1.jsx)(Icon, { size: 18 }) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: choice.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: choice.description }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs leading-5 text-ds-muted/80", children: choice.detail })] }, choice.id));
                                            }) })] }), (0, jsx_runtime_1.jsx)(SummaryCard, { selectedUseCase: selectedUseCase, selectedDataChoiceId: selectedDataChoiceId, selectedDeliverables: selectedDeliverables, selectedAutonomyMode: selectedAutonomyMode, selectedModel: selectedModel, selectedModelAccess: selectedModelAccess, t: t })] }), (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex items-center justify-between border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('deliverables'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_deliverables') }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('model'), className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover", children: [t('onboarding.continue'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] })] })] })), step === 'model' && selectedUseCase && ((0, jsx_runtime_1.jsx)("div", { className: "rounded-2xl border border-ds-border bg-ds-surface p-8", children: (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-8 lg:grid-cols-[0.95fr_1.45fr]", children: [(0, jsx_runtime_1.jsx)(SummaryCard, { selectedUseCase: selectedUseCase, selectedDataChoiceId: selectedDataChoiceId, selectedDeliverables: selectedDeliverables, selectedAutonomyMode: selectedAutonomyMode, selectedModel: selectedModel, selectedModelAccess: selectedModelAccess, t: t }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsxs)("div", { className: "mb-6", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 5 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.model_step.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm text-ds-muted", children: t('onboarding.model_step.description') })] }), (0, jsx_runtime_1.jsxs)("div", { className: "space-y-4", children: [groups.map((group) => ((0, jsx_runtime_1.jsxs)("div", { role: "group", "aria-label": t(group.titleKey), className: "overflow-hidden rounded-2xl border border-ds-border bg-ds-bg", children: [(0, jsx_runtime_1.jsxs)("div", { className: "border-b border-ds-border px-4 py-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-medium uppercase tracking-[0.18em] text-ds-muted", children: t(group.titleKey) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t(group.descriptionKey) })] }), group.models.length === 0 ? ((0, jsx_runtime_1.jsxs)("div", { className: "px-4 py-4 text-sm text-ds-muted", children: [(0, jsx_runtime_1.jsx)("div", { className: "font-medium text-ds-text", children: t(group.emptyTitleKey) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t(group.emptyDescriptionKey) })] })) : (group.models.map((entry) => {
                                                        const access = (0, modelAuth_1.describeModelAccess)({
                                                            modelId: entry.id,
                                                            modelEntry: entry,
                                                            providerStatuses,
                                                            oauthStatuses,
                                                        });
                                                        const isRecommended = recommendedModel?.model.id === entry.id;
                                                        return ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => handleModelSelect(entry), className: `
                                flex w-full items-start justify-between gap-4 border-b border-ds-border/40
                                px-4 py-4 text-left transition-colors last:border-b-0
                                hover:bg-ds-accent/5
                                ${selectedModel?.id === entry.id ? 'bg-ds-accent/10' : ''}
                              `, children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-center gap-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: entry.displayName }), isRecommended && ((0, jsx_runtime_1.jsx)("span", { className: "rounded-full bg-ds-accent/10 px-2 py-0.5 text-[10px] font-medium text-ds-accent", children: t('llm.recommend.badge') }))] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-xs leading-5 text-ds-muted", children: getConnectionHint(entry, access.ready, t) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 flex flex-wrap gap-1", children: entry.badges.map((badge) => ((0, jsx_runtime_1.jsx)(CapabilityBadge_1.CapabilityBadge, { badge: badge }, `${entry.id}-${badge}`))) }), isRecommended && recommendedReason && ((0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-[11px] leading-5 text-ds-accent", children: recommendedReason })), (0, jsx_runtime_1.jsxs)("div", { className: "mt-2 text-[11px] leading-5 text-ds-muted/80", children: [access.providerLabel, " / ", access.authTypeLabel] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[11px] leading-5 text-ds-muted/80", children: access.detail })] }), (0, jsx_runtime_1.jsxs)("div", { className: "flex shrink-0 flex-col items-end gap-2", children: [(0, jsx_runtime_1.jsx)("span", { className: `rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeClasses(access.ready)}`, children: access.shortLabel }), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16, className: "text-ds-muted" })] })] }, entry.id));
                                                    }))] }, group.id))), groups.length === 0 && ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-bg p-8 text-center", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 20, className: "mx-auto mb-3 animate-spin text-ds-accent" }), (0, jsx_runtime_1.jsx)("p", { className: "text-sm text-ds-muted", children: t('onboarding.connect.loading') })] }))] }), selectedModel && selectedModelAccess && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-6 rounded-2xl border border-ds-border bg-ds-bg p-5", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-4", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: selectedModel.displayName }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: selectedModelAccess.detail })] }), (0, jsx_runtime_1.jsx)("span", { className: `rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeClasses(selectedModelAccess.ready)}`, children: selectedModelAccess.shortLabel })] }), selectedModelAccess.authType === 'oauth' && !selectedModelAccess.ready && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-5", children: [oauthWaiting ? ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border bg-ds-surface px-4 py-5 text-center", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 20, className: "mx-auto mb-3 animate-spin text-ds-accent" }), (0, jsx_runtime_1.jsx)("p", { className: "text-sm text-ds-muted", children: t('onboarding.oauth.waiting') })] })) : ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => void handleOAuthLogin(), className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.LogIn, { size: 16 }), t('onboarding.oauth.start')] })), oauthError && (0, jsx_runtime_1.jsx)("p", { className: "mt-4 text-xs text-red-400", children: oauthError })] })), selectedModelAccess.authType !== 'oauth' && !selectedModelAccess.ready && NEEDS_API_KEY.has(selectedModel.provider) && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-5", children: [!vaultAvailable && window.electronAPI?.getSecretVaultStatus && ((0, jsx_runtime_1.jsx)("p", { className: "mb-3 text-xs text-red-400", children: apiKeyError || t('onboarding.api_key.vault_unavailable') })), (0, jsx_runtime_1.jsx)("label", { className: "block text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.model_step.api_key_label') }), (0, jsx_runtime_1.jsx)("input", { type: "password", value: apiKey, onChange: (event) => setApiKey(event.target.value), placeholder: getKeyPlaceholder(selectedModel.provider), className: "mt-3 w-full rounded-xl border border-ds-border bg-ds-surface px-4 py-3 text-sm text-ds-text placeholder:text-ds-muted/50 focus:border-ds-accent focus:outline-none", onKeyDown: (event) => {
                                                            if (event.key === 'Enter' && canContinueFromModel) {
                                                                setStep('notify');
                                                            }
                                                        } }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs leading-5 text-ds-muted", children: t('onboarding.model_step.api_key_description') })] }))] })), (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex items-center justify-between border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('mode'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_mode') }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('notify'), disabled: !canContinueFromModel, className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40", children: [t('onboarding.continue'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] })] })] })] }) })), step === 'notify' && selectedModel && selectedUseCase && ((0, jsx_runtime_1.jsx)("div", { className: "mx-auto max-w-5xl rounded-2xl border border-ds-border bg-ds-surface p-8", children: (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-8 lg:grid-cols-[0.9fr_1.1fr]", children: [(0, jsx_runtime_1.jsx)(SummaryCard, { selectedUseCase: selectedUseCase, selectedDataChoiceId: selectedDataChoiceId, selectedDeliverables: selectedDeliverables, selectedAutonomyMode: selectedAutonomyMode, selectedModel: selectedModel, selectedModelAccess: selectedModelAccess, t: t }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 6 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.notify.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.notify.description') }), !notifyChoice ? ((0, jsx_runtime_1.jsxs)("div", { className: "mt-6 grid gap-4 md:grid-cols-2", children: [(0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setNotifyChoice('telegram'), className: "rounded-2xl border border-ds-border bg-ds-bg p-5 text-left transition-colors hover:border-ds-accent/40 hover:bg-ds-accent/5", children: [(0, jsx_runtime_1.jsx)("div", { className: "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent", children: (0, jsx_runtime_1.jsx)(lucide_react_1.Bell, { size: 18, "aria-hidden": "true" }) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: t('onboarding.notify.telegram.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.notify.telegram.description') })] }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => {
                                                    setNotifyChoice('desktop');
                                                    setStep('confirm');
                                                }, className: "rounded-2xl border border-ds-border bg-ds-bg p-5 text-left transition-colors hover:border-ds-accent/40 hover:bg-ds-accent/5", children: [(0, jsx_runtime_1.jsx)("div", { className: "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent", children: (0, jsx_runtime_1.jsx)(lucide_react_1.Monitor, { size: 18, "aria-hidden": "true" }) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 text-base font-medium text-ds-text", children: t('onboarding.notify.desktop.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.notify.desktop.description') })] })] })) : null, notifyChoice === 'telegram' ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-6", children: (0, jsx_runtime_1.jsx)(TelegramConnectFlow_1.TelegramConnectFlow, { rpc: rpc, embedded: true, onComplete: () => setStep('confirm'), onSkip: () => setStep('confirm'), onCancel: () => {
                                                setNotifyChoice(null);
                                            } }) })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex items-center justify-between border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('model'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_model') }), (0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => setStep('confirm'), className: "inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover", children: [t('onboarding.notify.continueDesktop'), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 16 })] })] })] })] }) })), step === 'confirm' && selectedModel && selectedUseCase && ((0, jsx_runtime_1.jsxs)("div", { className: "mx-auto max-w-4xl rounded-2xl border border-ds-border bg-ds-surface p-8", children: [(0, jsx_runtime_1.jsx)("div", { className: "mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-ds-success/20", children: (0, jsx_runtime_1.jsx)(lucide_react_1.Check, { size: 24, className: "text-ds-success" }) }), (0, jsx_runtime_1.jsx)("div", { className: "text-xs uppercase tracking-[0.2em] text-ds-muted", children: t('onboarding.steps.label', { step: 7 }) }), (0, jsx_runtime_1.jsx)("h2", { className: "mt-2 text-2xl font-semibold text-ds-text", children: t('onboarding.confirm.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-sm leading-6 text-ds-muted", children: t('onboarding.confirm.description') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-bg p-5", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.confirm.mission_card') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-4 space-y-4", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: selectedUseCase.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: selectedUseCase.description })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.confirm.data') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-sm text-ds-text", children: formatDataChoiceTitle(selectedDataChoiceId, t) })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.confirm.deliverables') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-sm text-ds-text", children: selectedDeliverables.map((entry) => formatDeliverableTitle(entry, t)).join(', ') })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.confirm.autonomy') }), (0, jsx_runtime_1.jsxs)("p", { className: "mt-1 text-sm text-ds-text", children: [formatAutonomyModeTitle(selectedAutonomyMode, t), " /", ' ', formatExecutionModeTitle(selectedAutonomyMode, t)] })] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.confirm.model') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-sm text-ds-text", children: selectedModel.displayName }), selectedModelAccess && ((0, jsx_runtime_1.jsxs)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: [selectedModelAccess.providerLabel, " / ", selectedModelAccess.shortLabel] }))] }), (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.done.suggested_prompt') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-text", children: selectedUseCase.starterPrompt })] })] })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-2xl border border-ds-border bg-ds-bg p-5 text-left", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.privacy.eyebrow') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-base font-medium text-ds-text", children: t('onboarding.privacy.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-muted", children: t('onboarding.privacy.description') }), !sentryConfigured && ((0, jsx_runtime_1.jsx)("div", { className: "mt-4 rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200", children: t('onboarding.privacy.not_configured') })), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 grid gap-3", children: observabilityChoices.map((choice) => {
                                                const selected = observabilityChoice === choice.id;
                                                return ((0, jsx_runtime_1.jsxs)("button", { type: "button", onClick: () => {
                                                        setFinishError('');
                                                        setObservabilityChoice(choice.id);
                                                    }, className: `rounded-2xl border p-4 text-left transition-colors ${selected
                                                        ? 'border-ds-accent/60 bg-ds-accent/10'
                                                        : 'border-ds-border bg-ds-surface hover:border-ds-accent/40 hover:bg-ds-accent/5'}`, children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: choice.title }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs leading-5 text-ds-muted", children: choice.description })] }, choice.id));
                                            }) })] })] }), selectedDataChoiceId === 'sample' && sampleApiAvailable && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-4 rounded-2xl border border-ds-accent/30 bg-ds-accent/5 p-5 text-left", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-[0.18em] text-ds-muted", children: t('onboarding.sample.eyebrow') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-sm leading-6 text-ds-text", children: t('onboarding.sample.description') })] })), finishError && (0, jsx_runtime_1.jsx)("p", { className: "mt-4 text-xs text-red-400", children: finishError }), (0, jsx_runtime_1.jsxs)("div", { className: "sticky bottom-0 -mx-8 mt-6 flex flex-col gap-3 border-t border-ds-border bg-ds-surface/95 px-8 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between", children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => setStep('notify'), className: "text-xs font-medium text-ds-muted transition-colors hover:text-ds-text", children: t('onboarding.actions.back_to_notify') }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => void handleFinish(), disabled: loading || observabilityChoice === null, className: "inline-flex items-center justify-center gap-2 rounded-xl bg-ds-accent px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-50", children: loading ? ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 16, className: "animate-spin" }), selectedDataChoiceId === 'sample' && sampleApiAvailable
                                                ? t('onboarding.sample.preparing')
                                                : t('onboarding.done.start')] })) : (selectedDataChoiceId === 'sample' && sampleApiAvailable
                                        ? t('onboarding.sample.try')
                                        : t('onboarding.done.start')) })] })] }))] }) }));
}
