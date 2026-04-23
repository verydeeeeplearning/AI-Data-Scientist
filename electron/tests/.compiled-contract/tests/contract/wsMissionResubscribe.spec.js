"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const wsMissionSubscriber_1 = require("../../src/renderer/infrastructure/ws/wsMissionSubscriber");
function createBus() {
    const listeners = new Map();
    return {
        on(event, handler) {
            const set = listeners.get(event) ?? new Set();
            set.add(handler);
            listeners.set(event, set);
            return () => {
                set.delete(handler);
                if (set.size === 0) {
                    listeners.delete(event);
                }
            };
        },
        emit(event, payload) {
            for (const handler of listeners.get(event) ?? []) {
                handler(payload);
            }
        },
        listenerCount(event) {
            return listeners.get(event)?.size ?? 0;
        },
    };
}
function simulateLifecycle() {
    const bus = createBus();
    const received = [];
    const records = [];
    function resubscribe(status) {
        while (records.length > 0) {
            const record = records.pop();
            record?.unsubscribe();
        }
        if (status !== 'connected') {
            return;
        }
        const unsubscribe = (0, wsMissionSubscriber_1.subscribeToMissionContextUpdates)(bus.on, 'session-x', (patch) => {
            received.push(patch);
        });
        records.push({ bus, unsubscribe });
    }
    return {
        records,
        received,
        resubscribe,
        teardown() {
            while (records.length > 0) {
                records.pop()?.unsubscribe();
            }
        },
        bus,
    };
}
function run() {
    // First connect — single subscription wired.
    {
        const lifecycle = simulateLifecycle();
        lifecycle.resubscribe('connected');
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);
        lifecycle.bus.emit('mission.context.updated', {
            sessionId: 'session-x',
            stage: { current: 2, label: 'Analysis running' },
        });
        strict_1.default.deepEqual(lifecycle.received, [
            { stage: { current: 2, label: 'Analysis running' } },
        ]);
        lifecycle.teardown();
    }
    // Reconnect cycle — disconnect tears down listener, reconnect re-attaches exactly one.
    {
        const lifecycle = simulateLifecycle();
        lifecycle.resubscribe('connected');
        lifecycle.resubscribe('disconnected');
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);
        lifecycle.resubscribe('connecting');
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);
        lifecycle.resubscribe('connected');
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);
        lifecycle.bus.emit('mission.context.updated', {
            sessionId: 'session-x',
            mode: 'auto',
        });
        strict_1.default.deepEqual(lifecycle.received.at(-1), { mode: 'auto' });
        lifecycle.teardown();
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);
    }
    // Multiple reconnects do not stack listeners.
    {
        const lifecycle = simulateLifecycle();
        for (let i = 0; i < 5; i += 1) {
            lifecycle.resubscribe('disconnected');
            lifecycle.resubscribe('connected');
        }
        strict_1.default.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);
        lifecycle.teardown();
    }
    // sessionId scoping survives reconnect.
    {
        const lifecycle = simulateLifecycle();
        lifecycle.resubscribe('connected');
        lifecycle.bus.emit('mission.context.updated', {
            sessionId: 'session-other',
            mode: 'controlled',
        });
        lifecycle.bus.emit('mission.context.updated', {
            sessionId: 'session-x',
            mode: 'controlled',
        });
        strict_1.default.equal(lifecycle.received.length, 1);
        strict_1.default.deepEqual(lifecycle.received[0], { mode: 'controlled' });
        lifecycle.teardown();
    }
    console.log('[contract] PASS ws-mission-resubscribe (8 cases)');
}
run();
