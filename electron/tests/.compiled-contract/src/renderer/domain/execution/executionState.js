"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createExecutionState = createExecutionState;
exports.normalizeQualityPreset = normalizeQualityPreset;
exports.reduceSetModel = reduceSetModel;
exports.reduceSetQualityPreset = reduceSetQualityPreset;
exports.reduceSetMode = reduceSetMode;
exports.reduceSetCost = reduceSetCost;
exports.reduceSetStep = reduceSetStep;
exports.reduceSetActiveSessions = reduceSetActiveSessions;
exports.reduceSetConnected = reduceSetConnected;
exports.reduceUpdateFromStatus = reduceUpdateFromStatus;
const DEFAULT_MODEL = 'anthropic/claude-sonnet-4-6';
function createExecutionState(overrides = {}) {
    return Object.freeze({
        model: DEFAULT_MODEL,
        qualityPreset: 'balanced',
        mode: 'auto',
        cost: 0,
        step: 0,
        activeSessions: 0,
        connected: false,
        ...overrides,
    });
}
function normalizeQualityPreset(value) {
    if (value === 'best_quality'
        || value === 'balanced'
        || value === 'fast'
        || value === 'local'
        || value === 'custom') {
        return value;
    }
    return 'custom';
}
function normalizeMode(value, current) {
    if (value === 'auto' || value === 'supervised' || value === 'step-by-step') {
        return value;
    }
    return current;
}
function reduceSetModel(state, model) {
    return createExecutionState({ ...state, model });
}
function reduceSetQualityPreset(state, qualityPreset) {
    return createExecutionState({ ...state, qualityPreset });
}
function reduceSetMode(state, mode) {
    return createExecutionState({ ...state, mode });
}
function reduceSetCost(state, cost) {
    return createExecutionState({ ...state, cost });
}
function reduceSetStep(state, step) {
    return createExecutionState({ ...state, step });
}
function reduceSetActiveSessions(state, n) {
    return createExecutionState({ ...state, activeSessions: n });
}
function reduceSetConnected(state, connected) {
    return createExecutionState({ ...state, connected });
}
function reduceUpdateFromStatus(state, data) {
    const model = typeof data.model === 'string' ? data.model : state.model;
    const qualityPreset = 'qualityPreset' in data ? normalizeQualityPreset(data.qualityPreset) : state.qualityPreset;
    const mode = 'mode' in data ? normalizeMode(data.mode, state.mode) : state.mode;
    const activeSessions = typeof data.activeSessions === 'number' ? data.activeSessions : state.activeSessions;
    return createExecutionState({
        ...state,
        model,
        qualityPreset,
        mode,
        activeSessions,
    });
}
