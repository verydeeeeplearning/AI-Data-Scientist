import assert from 'node:assert/strict';

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
  private store = new Map<string, string>();
  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  clear(): void {
    this.store.clear();
  }
  key(_index: number): string | null {
    return null;
  }
  get length(): number {
    return this.store.size;
  }
}

// Install BEFORE importing the store module (top-level imports run after).
const memory = new MemoryStorage();
(globalThis as unknown as { window: { localStorage: MemoryStorage } }).window = {
  localStorage: memory,
};

// Now import — the store reads ``window.localStorage`` lazily on each call,
// but we install the shim up front to be safe.
import {
  useReasoningTraceStore,
} from '../../src/renderer/stores/reasoningTraceStore';
import type { PlanNode } from '../../src/renderer/types/events';

const SNAPSHOT_KEY = 'ds-agent-plan-tree-snapshot';

function makePlanTree(label: string): PlanNode {
  return {
    id: 'root',
    label,
    status: 'running',
    reasoningRefs: [],
    toolEventRefs: [],
    children: [],
  };
}

function resetAll(): void {
  memory.clear();
  useReasoningTraceStore.getState().reset();
}

function run(): void {
  // === Case 1: setRunId then hydrate(matching runId) restores the snapshot ===
  {
    resetAll();
    const tree = makePlanTree('plan-A');
    const store = useReasoningTraceStore.getState();
    store.setRunId('run-A');
    store.replacePlanTree(tree);
    store.upsertTrace({
      id: 'r-1',
      stageKey: null,
      emittedAt: 1_700_000_000_000,
      thinking: 'why?',
    });

    // Snapshot persisted; clobber in-memory state to simulate a fresh
    // tab/page reload.
    useReasoningTraceStore.getState().reset();
    assert.equal(useReasoningTraceStore.getState().planState.planTree, null);

    useReasoningTraceStore.getState().hydrateFromPersistence('run-A');
    const after = useReasoningTraceStore.getState();
    assert.equal(after.runId, 'run-A');
    assert.ok(after.planState.planTree);
    assert.equal(after.planState.planTree?.label, 'plan-A');
    assert.equal(after.traces.length, 1);
    assert.equal(after.traces[0].id, 'r-1');
  }

  // === Case 2: setRunId('run-A') then hydrate('run-B') is a no-op ===
  {
    resetAll();
    const store = useReasoningTraceStore.getState();
    store.setRunId('run-A');
    store.replacePlanTree(makePlanTree('plan-A'));
    // Reset in-memory; snapshot for run-A still in storage.
    useReasoningTraceStore.getState().reset();

    useReasoningTraceStore.getState().hydrateFromPersistence('run-B');
    const after = useReasoningTraceStore.getState();
    // No hydration happened — runId stays null, planTree stays null.
    assert.equal(after.runId, null);
    assert.equal(after.planState.planTree, null);
    assert.equal(after.traces.length, 0);
  }

  // === Case 3: clearPersistence() after setRunId removes the entry ===
  {
    resetAll();
    const store = useReasoningTraceStore.getState();
    store.setRunId('run-A');
    store.replacePlanTree(makePlanTree('plan-A'));
    assert.ok(memory.getItem(SNAPSHOT_KEY), 'snapshot should be present after setRunId+replace');

    useReasoningTraceStore.getState().clearPersistence();
    assert.equal(memory.getItem(SNAPSHOT_KEY), null);
  }

  // === Case 4: store.runId field updates correctly through setRunId ===
  {
    resetAll();
    const store = useReasoningTraceStore.getState();
    assert.equal(store.runId, null);
    store.setRunId('run-A');
    assert.equal(useReasoningTraceStore.getState().runId, 'run-A');
    store.setRunId('run-B');
    assert.equal(useReasoningTraceStore.getState().runId, 'run-B');
    store.setRunId(null);
    assert.equal(useReasoningTraceStore.getState().runId, null);
  }

  console.log('[contract] PASS reasoning-trace-run-id-wiring (4 cases)');
}

run();
