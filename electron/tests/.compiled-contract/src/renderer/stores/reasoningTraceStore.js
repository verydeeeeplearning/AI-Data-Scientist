"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useReasoningTraceStore = void 0;
const zustand_1 = require("zustand");
const applyPlanReplannedDiff_1 = require("../application/runtime/applyPlanReplannedDiff");
const MAX_TRACE_ENTRIES = 200;
const PERSISTENCE_KEY = 'ds-agent-plan-tree-snapshot';
const PERSISTENCE_VERSION = 1;
function sortTraces(entries) {
    return [...entries].sort((left, right) => {
        if (left.emittedAt !== right.emittedAt) {
            return right.emittedAt - left.emittedAt;
        }
        return right.id.localeCompare(left.id);
    });
}
const INITIAL_PLAN_STATE = {
    lastCreatedAt: null,
    lastUpdatedAt: null,
    lastReplannedAt: null,
    lastReplanReason: null,
    planTree: null,
    replanAddedIds: [],
    replanRemovedIds: [],
    replanModifiedIds: [],
};
function clonePlanNode(node) {
    return {
        ...node,
        children: node.children.map(clonePlanNode),
        reasoningRefs: [...node.reasoningRefs],
        toolEventRefs: [...node.toolEventRefs],
    };
}
function applyPlanNodePatch(node, nodeId, updates) {
    const nextChildren = node.children.map((child) => applyPlanNodePatch(child, nodeId, updates));
    const matchedNode = node.id === nodeId;
    const childrenChanged = nextChildren.some((child, index) => child !== node.children[index]);
    if (!matchedNode && !childrenChanged) {
        return node;
    }
    if (!matchedNode) {
        return {
            ...node,
            children: nextChildren,
        };
    }
    return {
        ...node,
        ...updates,
        children: updates.children ?? nextChildren,
        reasoningRefs: updates.reasoningRefs ?? node.reasoningRefs,
        toolEventRefs: updates.toolEventRefs ?? node.toolEventRefs,
    };
}
function safeStorage() {
    try {
        if (typeof window === 'undefined' || !window.localStorage) {
            return null;
        }
        return window.localStorage;
    }
    catch {
        return null;
    }
}
function persistSnapshot(snapshot) {
    const storage = safeStorage();
    if (!storage)
        return;
    try {
        storage.setItem(PERSISTENCE_KEY, JSON.stringify(snapshot));
    }
    catch {
        // Quota errors and serialization failures are non-fatal.
    }
}
function readSnapshot() {
    const storage = safeStorage();
    if (!storage)
        return null;
    try {
        const raw = storage.getItem(PERSISTENCE_KEY);
        if (!raw)
            return null;
        const parsed = JSON.parse(raw);
        if (!parsed || parsed.version !== PERSISTENCE_VERSION) {
            return null;
        }
        if (typeof parsed.runId !== 'string' || parsed.runId.length === 0) {
            return null;
        }
        return parsed;
    }
    catch {
        return null;
    }
}
function clearStoredSnapshot() {
    const storage = safeStorage();
    if (!storage)
        return;
    try {
        storage.removeItem(PERSISTENCE_KEY);
    }
    catch {
        // Ignore.
    }
}
exports.useReasoningTraceStore = (0, zustand_1.create)((set, get) => {
    function persistCurrent() {
        const state = get();
        if (state.runId == null)
            return;
        persistSnapshot({
            version: PERSISTENCE_VERSION,
            runId: state.runId,
            planTree: state.planState.planTree,
            traces: state.traces,
            planState: state.planState,
        });
    }
    return {
        traces: [],
        planState: INITIAL_PLAN_STATE,
        runId: null,
        upsertTrace: (trace) => {
            set((state) => ({
                traces: sortTraces([
                    trace,
                    ...state.traces.filter((entry) => entry.id !== trace.id),
                ]).slice(0, MAX_TRACE_ENTRIES),
            }));
            persistCurrent();
        },
        replacePlanTree: (planTree) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    planTree: clonePlanNode(planTree),
                },
            }));
            persistCurrent();
        },
        patchPlanNode: (nodeId, updates) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    planTree: state.planState.planTree == null
                        ? null
                        : applyPlanNodePatch(state.planState.planTree, nodeId, updates),
                },
            }));
            persistCurrent();
        },
        applyReplanDiff: (diff) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    planTree: (0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(state.planState.planTree, diff),
                    replanAddedIds: [...diff.added],
                    replanRemovedIds: [...diff.removed],
                    replanModifiedIds: [...diff.modified],
                },
            }));
            persistCurrent();
        },
        clearReplanHighlights: () => set((state) => ({
            planState: {
                ...state.planState,
                replanAddedIds: [],
                replanRemovedIds: [],
                replanModifiedIds: [],
            },
        })),
        markPlanCreated: (timestamp) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    lastCreatedAt: timestamp,
                },
            }));
            persistCurrent();
        },
        markPlanUpdated: (timestamp) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    lastUpdatedAt: timestamp,
                },
            }));
            persistCurrent();
        },
        markPlanReplanned: (timestamp, reason) => {
            set((state) => ({
                planState: {
                    ...state.planState,
                    lastReplannedAt: timestamp,
                    lastReplanReason: reason,
                },
            }));
            persistCurrent();
        },
        setRunId: (runId) => {
            set({ runId });
            if (runId) {
                persistCurrent();
            }
        },
        hydrateFromPersistence: (runId) => {
            const snapshot = readSnapshot();
            if (!snapshot || snapshot.runId !== runId) {
                return;
            }
            set({
                runId,
                traces: [...snapshot.traces],
                planState: { ...snapshot.planState },
            });
        },
        clearPersistence: () => {
            clearStoredSnapshot();
        },
        reset: () => set({
            traces: [],
            planState: INITIAL_PLAN_STATE,
            runId: null,
        }),
    };
});
