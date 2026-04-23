"use strict";
/**
 * Pure onboarding state domain.
 *
 * Wave 2 W2-E phase 2: extract step transitions, defaults, and the
 * `OnboardingFinalizeRequest` builder out of the OnboardingWizard component
 * so they can be unit-tested without React, exercised by telemetry, and
 * reused by future entry surfaces (CLI bootstrap, restore-from-config flow).
 *
 * The component still owns React state; this module owns the transition
 * rules and serialization contracts so the boundaries match the Clean
 * Architecture rule (component is a presenter, this is application logic).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ONBOARDING_PRIMARY_STEP_ORDER = void 0;
exports.buildInitialOnboardingState = buildInitialOnboardingState;
exports.isOnboardingPrimaryStepId = isOnboardingPrimaryStepId;
exports.deriveUseCaseDefaults = deriveUseCaseDefaults;
exports.mapAutonomyModeToExecutionMode = mapAutonomyModeToExecutionMode;
exports.mapExecutionModeToAutonomyMode = mapExecutionModeToAutonomyMode;
exports.mapAutonomyModeToQualityPreset = mapAutonomyModeToQualityPreset;
exports.buildOnboardingFinalizePayload = buildOnboardingFinalizePayload;
exports.nextOnboardingStep = nextOnboardingStep;
exports.previousOnboardingStep = previousOnboardingStep;
exports.canAdvanceOnboardingStep = canAdvanceOnboardingStep;
exports.applyUseCaseSelection = applyUseCaseSelection;
exports.toggleDeliverable = toggleDeliverable;
exports.ONBOARDING_PRIMARY_STEP_ORDER = [
    'use_case',
    'data',
    'deliverables',
    'mode',
    'model',
    'confirm',
];
function buildInitialOnboardingState(args) {
    return {
        step: 'use_case',
        useCaseId: null,
        dataChoiceId: args.defaultDataChoice,
        deliverables: [],
        autonomyMode: 'balanced',
        modelId: null,
    };
}
function isOnboardingPrimaryStepId(value) {
    return (typeof value === 'string'
        && exports.ONBOARDING_PRIMARY_STEP_ORDER.includes(value));
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
    if (mode === 'fast')
        return 'auto';
    if (mode === 'controlled')
        return 'step-by-step';
    return 'supervised';
}
function mapExecutionModeToAutonomyMode(value) {
    if (value === 'auto')
        return 'fast';
    if (value === 'step-by-step')
        return 'controlled';
    return 'balanced';
}
function mapAutonomyModeToQualityPreset(mode) {
    if (mode === 'fast')
        return 'fast';
    if (mode === 'controlled')
        return 'best_quality';
    return 'balanced';
}
function buildOnboardingFinalizePayload(args) {
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
            step6_confirmed: true,
        },
    };
}
function nextOnboardingStep(current) {
    const index = exports.ONBOARDING_PRIMARY_STEP_ORDER.indexOf(current);
    if (index < 0 || index >= exports.ONBOARDING_PRIMARY_STEP_ORDER.length - 1) {
        return null;
    }
    return exports.ONBOARDING_PRIMARY_STEP_ORDER[index + 1];
}
function previousOnboardingStep(current) {
    const index = exports.ONBOARDING_PRIMARY_STEP_ORDER.indexOf(current);
    if (index <= 0) {
        return null;
    }
    return exports.ONBOARDING_PRIMARY_STEP_ORDER[index - 1];
}
function canAdvanceOnboardingStep(state) {
    switch (state.step) {
        case 'use_case':
            return state.useCaseId !== null;
        case 'data':
            return state.dataChoiceId !== 'database_deferred' || true;
        case 'deliverables':
            return state.deliverables.length > 0;
        case 'mode':
            return true;
        case 'model':
            return state.modelId !== null;
        case 'confirm':
            return true;
        default:
            return false;
    }
}
function applyUseCaseSelection(state, useCaseId) {
    const defaults = deriveUseCaseDefaults(useCaseId);
    return {
        ...state,
        useCaseId,
        deliverables: defaults.deliverables,
        autonomyMode: defaults.mode,
    };
}
function toggleDeliverable(state, deliverableId) {
    const next = state.deliverables.includes(deliverableId)
        ? state.deliverables.filter((entry) => entry !== deliverableId)
        : [...state.deliverables, deliverableId];
    return { ...state, deliverables: next };
}
