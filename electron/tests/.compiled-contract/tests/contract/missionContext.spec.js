"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const mission_1 = require("../../src/renderer/domain/mission");
const wsMissionSubscriber_1 = require("../../src/renderer/infrastructure/ws/wsMissionSubscriber");
const BASE_MISSION = {
    goal: {
        title: 'Reduce churn for premium users',
        successCriteria: ['Deliver retention analysis'],
    },
    dataSources: [
        { type: 'file', label: 'train.csv', rowCount: 1200 },
    ],
    deliverables: ['report'],
    constraints: {
        language: 'ko',
        requiresApproval: true,
        localOnlyModel: false,
    },
    stage: {
        current: 1,
        total: 4,
        label: 'Mission agreed',
    },
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
    connection: {
        state: 'connected',
    },
};
function createEventBus() {
    const listeners = new Map();
    return {
        on(event, handler) {
            const handlers = listeners.get(event) ?? new Set();
            handlers.add(handler);
            listeners.set(event, handlers);
            return () => {
                handlers.delete(handler);
                if (handlers.size === 0) {
                    listeners.delete(event);
                }
            };
        },
        emit(event, payload) {
            for (const handler of listeners.get(event) ?? []) {
                handler(payload);
            }
        },
    };
}
function run() {
    {
        const merged = (0, mission_1.mergeMissionContext)(BASE_MISSION, {
            stage: {
                current: 2,
                label: 'Analysis running',
            },
            budget: {
                spentUsd: 8.4,
                nearLimit: true,
            },
            model: {
                capabilities: ['deep_reasoning', 'richer_reports'],
            },
        });
        strict_1.default.equal(merged.stage.current, 2);
        strict_1.default.equal(merged.stage.total, 4);
        strict_1.default.equal(merged.stage.label, 'Analysis running');
        strict_1.default.equal(merged.budget.spentUsd, 8.4);
        strict_1.default.equal(merged.budget.limitUsd, 10);
        strict_1.default.deepEqual(merged.model.capabilities, ['deep_reasoning', 'richer_reports']);
    }
    {
        strict_1.default.equal((0, mission_1.getMissionBudgetState)(BASE_MISSION.budget), 'default');
        strict_1.default.equal((0, mission_1.getMissionBudgetState)({ ...BASE_MISSION.budget, spentUsd: 8.2, nearLimit: true }), 'warning');
        strict_1.default.equal((0, mission_1.getMissionBudgetState)({ ...BASE_MISSION.budget, spentUsd: 10, nearLimit: true }), 'error');
    }
    {
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('connected'), 'connected');
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('connecting'), 'reconnecting');
        strict_1.default.equal((0, mission_1.getMissionConnectionStateFromWs)('disconnected'), 'disconnected');
    }
    {
        const bus = createEventBus();
        const received = [];
        const unsubscribe = (0, wsMissionSubscriber_1.subscribeToMissionContextUpdates)(bus.on, 'session-a', (patch) => {
            received.push(patch);
        });
        bus.emit('mission.context.updated', {
            sessionId: 'session-b',
            stage: { current: 3, label: 'Wrong session' },
        });
        bus.emit('mission.context.updated', {
            sessionId: 'session-a',
            stage: { current: 2, label: 'Analysis running' },
        });
        strict_1.default.deepEqual(received, [{ stage: { current: 2, label: 'Analysis running' } }]);
        unsubscribe();
    }
    {
        const bus = createEventBus();
        let received = null;
        (0, wsMissionSubscriber_1.subscribeToMissionContextUpdates)(bus.on, 'session-a', (patch) => {
            received = patch;
        });
        bus.emit('mission.context.updated', {
            budget: { spentUsd: 2.1 },
            model: { primary: 'anthropic/claude-3-7-sonnet' },
        });
        strict_1.default.deepEqual(received, {
            budget: { spentUsd: 2.1 },
            model: { primary: 'anthropic/claude-3-7-sonnet' },
        });
    }
    {
        const bus = createEventBus();
        let called = false;
        (0, wsMissionSubscriber_1.subscribeToMissionContextUpdates)(bus.on, 'session-a', () => {
            called = true;
        });
        bus.emit('mission.context.updated', null);
        bus.emit('mission.context.updated', 'not-an-object');
        strict_1.default.equal(called, false);
    }
    console.log('[contract] PASS mission-context (12 cases)');
}
run();
