import { create } from 'zustand';
import {
  applyPlanReplannedDiff,
  type PlanReplannedDiff,
} from '../application/runtime/applyPlanReplannedDiff';
import type { StageKey } from '../domain/execution/stage';
import type { PlanNode, PlanNodePatch } from '../types/events';

export interface ReasoningTraceEntry {
  readonly id: string;
  readonly stageKey: StageKey | null;
  readonly emittedAt: number;
  readonly planNodeId?: string;
  readonly thinking?: string;
  readonly hypothesis?: string;
  readonly action?: string;
  readonly observation?: string;
  readonly decision?: string;
}

export interface ReasoningPlanState {
  readonly lastCreatedAt: number | null;
  readonly lastUpdatedAt: number | null;
  readonly lastReplannedAt: number | null;
  readonly lastReplanReason: string | null;
  readonly planTree: PlanNode | null;
  /** Node ids that were added in the most recent replan (transient highlight). */
  readonly replanAddedIds: ReadonlyArray<string>;
  /** Node ids that were removed in the most recent replan (transient strikethrough). */
  readonly replanRemovedIds: ReadonlyArray<string>;
  /** Node ids that were modified in the most recent replan (transient highlight). */
  readonly replanModifiedIds: ReadonlyArray<string>;
}

interface ReasoningTraceState {
  traces: ReasoningTraceEntry[];
  planState: ReasoningPlanState;
  runId: string | null;
  upsertTrace: (trace: ReasoningTraceEntry) => void;
  replacePlanTree: (planTree: PlanNode) => void;
  patchPlanNode: (nodeId: string, updates: PlanNodePatch) => void;
  applyReplanDiff: (diff: PlanReplannedDiff) => void;
  clearReplanHighlights: () => void;
  markPlanCreated: (timestamp: number) => void;
  markPlanUpdated: (timestamp: number) => void;
  markPlanReplanned: (timestamp: number, reason: string | null) => void;
  setRunId: (runId: string | null) => void;
  hydrateFromPersistence: (runId: string) => void;
  clearPersistence: () => void;
  reset: () => void;
}

const MAX_TRACE_ENTRIES = 200;
const PERSISTENCE_KEY = 'ds-agent-plan-tree-snapshot';
const PERSISTENCE_VERSION = 1;

interface PersistedSnapshot {
  readonly version: number;
  readonly runId: string;
  readonly planTree: PlanNode | null;
  readonly traces: ReadonlyArray<ReasoningTraceEntry>;
  readonly planState: ReasoningPlanState;
}

function sortTraces(entries: readonly ReasoningTraceEntry[]): ReasoningTraceEntry[] {
  return [...entries].sort((left, right) => {
    if (left.emittedAt !== right.emittedAt) {
      return right.emittedAt - left.emittedAt;
    }
    return right.id.localeCompare(left.id);
  });
}

const INITIAL_PLAN_STATE: ReasoningPlanState = {
  lastCreatedAt: null,
  lastUpdatedAt: null,
  lastReplannedAt: null,
  lastReplanReason: null,
  planTree: null,
  replanAddedIds: [],
  replanRemovedIds: [],
  replanModifiedIds: [],
};

function clonePlanNode(node: PlanNode): PlanNode {
  return {
    ...node,
    children: node.children.map(clonePlanNode),
    reasoningRefs: [...node.reasoningRefs],
    toolEventRefs: [...node.toolEventRefs],
  };
}

function applyPlanNodePatch(
  node: PlanNode,
  nodeId: string,
  updates: PlanNodePatch,
): PlanNode {
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

function safeStorage(): Storage | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return null;
    }
    return window.localStorage;
  } catch {
    return null;
  }
}

function persistSnapshot(snapshot: PersistedSnapshot): void {
  const storage = safeStorage();
  if (!storage) return;
  try {
    storage.setItem(PERSISTENCE_KEY, JSON.stringify(snapshot));
  } catch {
    // Quota errors and serialization failures are non-fatal.
  }
}

function readSnapshot(): PersistedSnapshot | null {
  const storage = safeStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(PERSISTENCE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedSnapshot;
    if (!parsed || parsed.version !== PERSISTENCE_VERSION) {
      return null;
    }
    if (typeof parsed.runId !== 'string' || parsed.runId.length === 0) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function clearStoredSnapshot(): void {
  const storage = safeStorage();
  if (!storage) return;
  try {
    storage.removeItem(PERSISTENCE_KEY);
  } catch {
    // Ignore.
  }
}

export const useReasoningTraceStore = create<ReasoningTraceState>((set, get) => {
  function persistCurrent(): void {
    const state = get();
    if (state.runId == null) return;
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
          planTree: applyPlanReplannedDiff(state.planState.planTree, diff),
          replanAddedIds: [...diff.added],
          replanRemovedIds: [...diff.removed],
          replanModifiedIds: [...diff.modified],
        },
      }));
      persistCurrent();
    },

    clearReplanHighlights: () =>
      set((state) => ({
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

    reset: () =>
      set({
        traces: [],
        planState: INITIAL_PLAN_STATE,
        runId: null,
      }),
  };
});
