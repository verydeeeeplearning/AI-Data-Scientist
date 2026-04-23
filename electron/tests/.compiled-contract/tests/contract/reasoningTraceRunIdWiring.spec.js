"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
/**
 * Contract spec: ``setRunId`` is the producer that anchors persistence
 * snapshots, and ``hydrateFromPersistence(runId)`` MUST be a strict equality
 * gate against the stored snapshot's runId.
 *
 * Scenarios covered:
 *   1. ``setRunId('run-A')`` → ``hydrateFromPersistence('run-A')`` applies
 *      the snapshot.
 *   2. ``setRunId('run-A')`` → ``hydrateFromPersistence('run-B')`` is a
 *      no-op (mismatch — stale snapshot belongs to a different run).
 *   3. ``clearPersistence()`` after ``setRunId`` removes the localStorage
 *      entry.
 *   4. The store's ``runId`` field updates correctly when ``setRunId``
 *      runs and survives subsequent persistence reads.
 */
// ---------------------------------------------------------------------------
// Minimal in-process localStorage shim — node has no DOM by default.
// ---------------------------------------------------------------------------
class MemoryStorage {
    constructor() {
        this.store = new Map();
    }
    getItem(key) {
        return this.store.has(key) ? this.store.get(key) : null;
    }
    setItem(key, value) {
        this.store.set(key, value);
    }
    removeItem(key) {
        this.store.delete(key);
    }
    clear() {
        this.store.clear();
    }
    key(_index) {
        return null;
    }
    get length() {
        return this.store.size;
    }
}
// Install BEFORE importing the store module (top-level imports run after).
const memory = new MemoryStorage();
globalThis.window = {
    localStorage: memory,
};
// Now import — the store reads ``window.localStorage`` lazily on each call,
// but we install the shim up front to be safe.
const reasoningTraceStore_1 = require("../../src/renderer/stores/reasoningTraceStore");
const SNAPSHOT_KEY = 'ds-agent-plan-tree-snapshot';
function makePlanTree(label) {
    return {
        id: 'root',
        label,
        status: 'running',
        reasoningRefs: [],
        toolEventRefs: [],
        children: [],
    };
}
function resetAll() {
    memory.clear();
    reasoningTraceStore_1.useReasoningTraceStore.getState().reset();
}
function run() {
    // === Case 1: setRunId then hydrate(matching runId) restores the snapshot ===
    {
        resetAll();
        const tree = makePlanTree('plan-A');
        const store = reasoningTraceStore_1.useReasoningTraceStore.getState();
        store.setRunId('run-A');
        store.replacePlanTree(tree);
        store.upsertTrace({
            id: 'r-1',
            stageKey: null,
            emittedAt: 1700000000000,
            thinking: 'why?',
        });
        // Snapshot persisted; clobber in-memory state to simulate a fresh
        // tab/page reload.
        reasoningTraceStore_1.useReasoningTraceStore.getState().reset();
        strict_1.default.equal(reasoningTraceStore_1.useReasoningTraceStore.getState().planState.planTree, null);
        reasoningTraceStore_1.useReasoningTraceStore.getState().hydrateFromPersistence('run-A');
        const after = reasoningTraceStore_1.useReasoningTraceStore.getState();
        strict_1.default.equal(after.runId, 'run-A');
        strict_1.default.ok(after.planState.planTree);
        strict_1.default.equal(after.planState.planTree?.label, 'plan-A');
        strict_1.default.equal(after.traces.length, 1);
        strict_1.default.equal(after.traces[0].id, 'r-1');
    }
    // === Case 2: setRunId('run-A') then hydrate('run-B') is a no-op ===
    {
        resetAll();
        const store = reasoningTraceStore_1.useReasoningTraceStore.getState();
        store.setRunId('run-A');
        store.replacePlanTree(makePlanTree('plan-A'));
        // Reset in-memory; snapshot for run-A still in storage.
        reasoningTraceStore_1.useReasoningTraceStore.getState().reset();
        reasoningTraceStore_1.useReasoningTraceStore.getState().hydrateFromPersistence('run-B');
        const after = reasoningTraceStore_1.useReasoningTraceStore.getState();
        // No hydration happened — runId stays null, planTree stays null.
        strict_1.default.equal(after.runId, null);
        strict_1.default.equal(after.planState.planTree, null);
        strict_1.default.equal(after.traces.length, 0);
    }
    // === Case 3: clearPersistence() after setRunId removes the entry ===
    {
        resetAll();
        const store = reasoningTraceStore_1.useReasoningTraceStore.getState();
        store.setRunId('run-A');
        store.replacePlanTree(makePlanTree('plan-A'));
        strict_1.default.ok(memory.getItem(SNAPSHOT_KEY), 'snapshot should be present after setRunId+replace');
        reasoningTraceStore_1.useReasoningTraceStore.getState().clearPersistence();
        strict_1.default.equal(memory.getItem(SNAPSHOT_KEY), null);
    }
    // === Case 4: store.runId field updates correctly through setRunId ===
    {
        resetAll();
        const store = reasoningTraceStore_1.useReasoningTraceStore.getState();
        strict_1.default.equal(store.runId, null);
        store.setRunId('run-A');
        strict_1.default.equal(reasoningTraceStore_1.useReasoningTraceStore.getState().runId, 'run-A');
        store.setRunId('run-B');
        strict_1.default.equal(reasoningTraceStore_1.useReasoningTraceStore.getState().runId, 'run-B');
        store.setRunId(null);
        strict_1.default.equal(reasoningTraceStore_1.useReasoningTraceStore.getState().runId, null);
    }
    console.log('[contract] PASS reasoning-trace-run-id-wiring (4 cases)');
}
run();
