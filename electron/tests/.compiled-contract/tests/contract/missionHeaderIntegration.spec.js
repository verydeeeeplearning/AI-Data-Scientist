"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const missionHeaderState_1 = require("../../src/renderer/application/mission/missionHeaderState");
const mission_1 = require("../../src/renderer/domain/mission");
const BASE_MISSION = {
    goal: {
        title: 'Reduce churn for premium users',
        successCriteria: ['Deliver retention analysis'],
    },
    dataSources: [{ type: 'file', label: 'train.csv', rowCount: 1200 }],
    deliverables: ['report'],
    constraints: {
        language: 'ko',
        requiresApproval: true,
        localOnlyModel: false,
    },
    stage: { current: 1, total: 4, label: 'Mission agreed' },
    mode: 'supervised',
    model: {
        primary: 'anthropic/claude-sonnet-4-6',
        fallbacks: ['openai/gpt-4.1'],
        capabilities: ['balanced_reasoning'],
    },
    budget: {
        spentUsd: 1.5,
        limitUsd: 10,
        elapsedSec: 30,
        nearLimit: false,
    },
    connection: { state: 'connected' },
};
function run() {
    // Scenario 1: WS reconnect updates mission connection without losing prior data.
    {
        const projected = (0, missionHeaderState_1.projectConnection)(BASE_MISSION, 'connecting');
        strict_1.default.equal(projected.connection.state, 'reconnecting');
        strict_1.default.equal(projected.goal.title, BASE_MISSION.goal.title);
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('connected'), 'connected');
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('connecting'), 'reconnecting');
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('disconnected'), 'disconnected');
        const reconnected = (0, missionHeaderState_1.projectConnection)(projected, 'connected');
        strict_1.default.equal(reconnected.connection.state, 'connected');
    }
    // Scenario 2: Budget 80% threshold triggers BudgetWarning, ESC dismiss only resets state.
    {
        const warningMission = {
            ...BASE_MISSION,
            budget: { ...BASE_MISSION.budget, spentUsd: 8.4, nearLimit: true },
        };
        strict_1.default.equal((0, missionHeaderState_1.deriveMissionBudgetState)(warningMission), 'warning');
        strict_1.default.equal((0, missionHeaderState_1.deriveMissionBudgetState)(BASE_MISSION), 'default');
        const errorMission = {
            ...BASE_MISSION,
            budget: { ...BASE_MISSION.budget, spentUsd: 11, nearLimit: true },
        };
        strict_1.default.equal((0, missionHeaderState_1.deriveMissionBudgetState)(errorMission), 'error');
        strict_1.default.equal((0, missionHeaderState_1.shouldShowBudgetWarning)({
            previous: 'default',
            next: 'warning',
            streaming: true,
        }), true);
        strict_1.default.equal((0, missionHeaderState_1.shouldShowBudgetWarning)({
            previous: 'default',
            next: 'warning',
            streaming: false,
        }), false);
        strict_1.default.equal((0, missionHeaderState_1.shouldShowBudgetWarning)({
            previous: 'warning',
            next: 'warning',
            streaming: true,
        }), false);
        strict_1.default.equal((0, missionHeaderState_1.shouldShowBudgetWarning)({
            previous: 'warning',
            next: 'error',
            streaming: true,
        }), true);
        strict_1.default.equal((0, missionHeaderState_1.shouldShowBudgetWarning)({
            previous: 'error',
            next: 'error',
            streaming: true,
        }), false);
    }
    // Scenario 3: Collapsed shows core 3 slots, expanded reveals all 9.
    {
        const collapsedKeys = (0, missionHeaderState_1.listVisibleSlotKeys)(true);
        strict_1.default.deepEqual(Array.from(collapsedKeys), Array.from(missionHeaderState_1.COLLAPSED_SLOT_KEYS));
        strict_1.default.equal(collapsedKeys.length, 3);
        strict_1.default.deepEqual(Array.from(collapsedKeys).sort(), ['budget', 'goal', 'stage']);
        const expandedKeys = (0, missionHeaderState_1.listVisibleSlotKeys)(false);
        strict_1.default.equal(expandedKeys.length, 9);
        strict_1.default.deepEqual(Array.from(expandedKeys).sort(), [
            'budget',
            'connection',
            'constraints',
            'dataSources',
            'deliverables',
            'goal',
            'mode',
            'model',
            'stage',
        ]);
    }
    // Scenario 4: mission.context.updated patch performs partial merge.
    {
        const updated = (0, missionHeaderState_1.applyMissionPatch)(BASE_MISSION, {
            stage: { current: 2, label: 'Analysis running' },
            budget: { spentUsd: 8.2, nearLimit: true },
        });
        strict_1.default.notEqual(updated, null);
        strict_1.default.equal(updated.stage.current, 2);
        strict_1.default.equal(updated.stage.total, 4);
        strict_1.default.equal(updated.stage.label, 'Analysis running');
        strict_1.default.equal(updated.budget.spentUsd, 8.2);
        strict_1.default.equal(updated.budget.limitUsd, 10);
        strict_1.default.equal(updated.goal.title, BASE_MISSION.goal.title);
        strict_1.default.equal((0, mission_1.getMissionBudgetState)(updated.budget), 'warning');
        const noOp = (0, missionHeaderState_1.applyMissionPatch)(null, { mode: 'auto' });
        strict_1.default.equal(noOp, null);
    }
    // Snooze interactions: snoozed timer suppresses warning, expired snooze allows it.
    {
        const now = 1000000000;
        const future = (0, missionHeaderState_1.snoozeUntil)(now, '5m');
        strict_1.default.equal(future, now + 5 * 60 * 1000);
        strict_1.default.equal((0, missionHeaderState_1.isSnoozeActive)({ until: future }, now), true);
        strict_1.default.equal((0, missionHeaderState_1.isSnoozeActive)({ until: future }, future + 1), false);
        strict_1.default.equal((0, missionHeaderState_1.isSnoozeActive)({ until: null }, now), false);
        const blocked = (0, missionHeaderState_1.nextBudgetWarningVisibility)({
            previous: 'default',
            next: 'warning',
            streaming: true,
            snoozedUntil: future,
            now,
        });
        strict_1.default.equal(blocked, false);
        const allowed = (0, missionHeaderState_1.nextBudgetWarningVisibility)({
            previous: 'default',
            next: 'warning',
            streaming: true,
            snoozedUntil: null,
            now,
        });
        strict_1.default.equal(allowed, true);
        const expired = (0, missionHeaderState_1.nextBudgetWarningVisibility)({
            previous: 'default',
            next: 'warning',
            streaming: true,
            snoozedUntil: now - 1,
            now,
        });
        strict_1.default.equal(expired, true);
        strict_1.default.equal((0, missionHeaderState_1.parseSnoozeStorage)(null).until, null);
        strict_1.default.equal((0, missionHeaderState_1.parseSnoozeStorage)('not-a-number').until, null);
        strict_1.default.equal((0, missionHeaderState_1.parseSnoozeStorage)('-5').until, null);
        strict_1.default.equal((0, missionHeaderState_1.parseSnoozeStorage)('123').until, 123);
        strict_1.default.equal((0, missionHeaderState_1.serializeSnoozeStorage)({ until: null }), null);
        strict_1.default.equal((0, missionHeaderState_1.serializeSnoozeStorage)({ until: 0 }), null);
        strict_1.default.equal((0, missionHeaderState_1.serializeSnoozeStorage)({ until: 555 }), '555');
        strict_1.default.equal(missionHeaderState_1.MISSION_BUDGET_SNOOZE_KEY, 'ds-agent-budget-snooze-until');
    }
    console.log('[contract] PASS mission-header-integration (28 cases)');
}
run();
