"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MISSION_BUDGET_SNOOZE_KEY = exports.ALL_SLOT_KEYS = exports.COLLAPSED_SLOT_KEYS = void 0;
exports.listVisibleSlotKeys = listVisibleSlotKeys;
exports.applyMissionPatch = applyMissionPatch;
exports.projectConnection = projectConnection;
exports.shouldShowBudgetWarning = shouldShowBudgetWarning;
exports.deriveMissionBudgetState = deriveMissionBudgetState;
exports.snoozeUntil = snoozeUntil;
exports.isSnoozeActive = isSnoozeActive;
exports.parseSnoozeStorage = parseSnoozeStorage;
exports.serializeSnoozeStorage = serializeSnoozeStorage;
exports.nextBudgetWarningVisibility = nextBudgetWarningVisibility;
const mission_1 = require("../../domain/mission");
exports.COLLAPSED_SLOT_KEYS = [
    'goal',
    'stage',
    'budget',
];
exports.ALL_SLOT_KEYS = [
    'goal',
    'dataSources',
    'deliverables',
    'constraints',
    'stage',
    'mode',
    'model',
    'budget',
    'connection',
];
function listVisibleSlotKeys(collapsed) {
    return collapsed ? exports.COLLAPSED_SLOT_KEYS : exports.ALL_SLOT_KEYS;
}
function applyMissionPatch(current, patch) {
    if (!current) {
        return current;
    }
    return (0, mission_1.mergeMissionContext)(current, patch);
}
function projectConnection(mission, status) {
    return {
        ...mission,
        connection: {
            ...mission.connection,
            state: (0, mission_1.getMissionConnectionStateFromWs)(status),
        },
    };
}
function shouldShowBudgetWarning(transition) {
    if (!transition.streaming) {
        return false;
    }
    if (transition.next === 'warning' && transition.previous === 'default') {
        return true;
    }
    if (transition.next === 'error' && transition.previous !== 'error') {
        return true;
    }
    return false;
}
function deriveMissionBudgetState(mission) {
    return (0, mission_1.getMissionBudgetState)(mission.budget);
}
exports.MISSION_BUDGET_SNOOZE_KEY = 'ds-agent-budget-snooze-until';
const SNOOZE_DURATIONS_MS = {
    '5m': 5 * 60 * 1000,
    '30m': 30 * 60 * 1000,
    '1h': 60 * 60 * 1000,
};
function snoozeUntil(now, option) {
    return now + SNOOZE_DURATIONS_MS[option];
}
function isSnoozeActive(state, now) {
    if (state.until === null) {
        return false;
    }
    return state.until > now;
}
function parseSnoozeStorage(value) {
    if (value === null) {
        return { until: null };
    }
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return { until: null };
    }
    return { until: parsed };
}
function serializeSnoozeStorage(state) {
    if (state.until === null || state.until <= 0) {
        return null;
    }
    return String(state.until);
}
function nextBudgetWarningVisibility(input) {
    if (input.snoozedUntil !== null
        && input.snoozedUntil > input.now) {
        return false;
    }
    return shouldShowBudgetWarning({
        previous: input.previous,
        next: input.next,
        streaming: input.streaming,
    });
}
