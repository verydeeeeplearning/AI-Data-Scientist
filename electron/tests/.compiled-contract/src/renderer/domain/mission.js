"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mergeMissionContext = mergeMissionContext;
exports.getMissionBudgetRatio = getMissionBudgetRatio;
exports.getMissionBudgetState = getMissionBudgetState;
exports.getMissionConnectionStateFromWs = getMissionConnectionStateFromWs;
exports.formatMissionMode = formatMissionMode;
function mergeMissionContext(current, patch) {
    return {
        goal: {
            ...current.goal,
            ...patch.goal,
            successCriteria: patch.goal?.successCriteria ?? current.goal.successCriteria,
        },
        dataSources: patch.dataSources ?? current.dataSources,
        deliverables: patch.deliverables ?? current.deliverables,
        constraints: {
            ...current.constraints,
            ...patch.constraints,
        },
        stage: {
            ...current.stage,
            ...patch.stage,
        },
        mode: patch.mode ?? current.mode,
        model: {
            ...current.model,
            ...patch.model,
            fallbacks: patch.model?.fallbacks ?? current.model.fallbacks,
            capabilities: patch.model?.capabilities ?? current.model.capabilities,
        },
        budget: {
            ...current.budget,
            ...patch.budget,
        },
        connection: {
            ...current.connection,
            ...patch.connection,
        },
    };
}
function getMissionBudgetRatio(budget) {
    if (budget.limitUsd <= 0) {
        return 0;
    }
    return Math.max(0, Math.min(1, budget.spentUsd / budget.limitUsd));
}
function getMissionBudgetState(budget) {
    const ratio = getMissionBudgetRatio(budget);
    if (ratio >= 1) {
        return 'error';
    }
    if (budget.nearLimit || ratio >= 0.8) {
        return 'warning';
    }
    return 'default';
}
function getMissionConnectionStateFromWs(status) {
    if (status === 'connected') {
        return 'connected';
    }
    if (status === 'connecting') {
        return 'reconnecting';
    }
    return 'disconnected';
}
function formatMissionMode(mode) {
    switch (mode) {
        case 'auto':
            return 'Auto';
        case 'supervised':
            return 'Supervised';
        case 'step-by-step':
            return 'Step by Step';
        default:
            return mode
                .split(/[-_\\s]+/)
                .filter(Boolean)
                .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
                .join(' ');
    }
}
