import assert from 'node:assert/strict';

import {
  applyPlanReplannedDiff,
  type PlanNodeSnapshot,
  type PlanReplannedDiff,
} from '../../src/renderer/application/runtime/applyPlanReplannedDiff';
import type { PlanNode } from '../../src/renderer/types/events';

function makeNode(id: string, overrides: Partial<PlanNode> = {}): PlanNode {
  return {
    id,
    label: overrides.label ?? id,
    description: overrides.description,
    status: overrides.status ?? 'pending',
    estimatedDurationSec: overrides.estimatedDurationSec,
    startedAt: overrides.startedAt,
    completedAt: overrides.completedAt,
    reasoningRefs: overrides.reasoningRefs ? [...overrides.reasoningRefs] : [],
    toolEventRefs: overrides.toolEventRefs ? [...overrides.toolEventRefs] : [],
    children: overrides.children ?? [],
    parentId: overrides.parentId,
  };
}

function makeSnapshot(id: string, overrides: Partial<PlanNodeSnapshot> = {}): PlanNodeSnapshot {
  return {
    id,
    label: overrides.label ?? id,
    description: overrides.description,
    status: overrides.status ?? 'pending',
    parentId: overrides.parentId ?? null,
    reasoningRefs: overrides.reasoningRefs ?? [],
    toolEventRefs: overrides.toolEventRefs ?? [],
    children: overrides.children,
    estimatedDurationSec: overrides.estimatedDurationSec,
    startedAt: overrides.startedAt,
    completedAt: overrides.completedAt,
  };
}

function flattenIds(node: PlanNode | null): string[] {
  if (!node) return [];
  const out: string[] = [node.id];
  for (const child of node.children) {
    out.push(...flattenIds(child));
  }
  return out;
}

function findNode(node: PlanNode | null, id: string): PlanNode | null {
  if (!node) return null;
  if (node.id === id) return node;
  for (const child of node.children) {
    const found = findNode(child, id);
    if (found) return found;
  }
  return null;
}

function run(): void {
  // Common starting tree: root with stages A and B as children.
  function baseTree(): PlanNode {
    return makeNode('root', {
      label: 'Workflow',
      status: 'running',
      children: [
        makeNode('stage-a', { label: 'Stage A', status: 'completed' }),
        makeNode('stage-b', { label: 'Stage B', status: 'running' }),
      ],
    });
  }

  // === Case 1: added-only — a brand-new stage joins the workflow ===
  {
    const newNodes: PlanNodeSnapshot[] = [
      makeSnapshot('root', {
        label: 'Workflow',
        status: 'running',
        children: [
          makeSnapshot('stage-a', { parentId: 'root' }),
          makeSnapshot('stage-b', { parentId: 'root' }),
          makeSnapshot('stage-c', { parentId: 'root', label: 'Stage C' }),
        ],
      }),
      makeSnapshot('stage-a', { parentId: 'root', label: 'Stage A', status: 'completed' }),
      makeSnapshot('stage-b', { parentId: 'root', label: 'Stage B', status: 'running' }),
      makeSnapshot('stage-c', { parentId: 'root', label: 'Stage C', status: 'pending' }),
    ];
    const diff: PlanReplannedDiff = {
      oldNodes: [],
      newNodes,
      added: ['stage-c'],
      removed: [],
      modified: [],
      reason: 'agent expanded plan',
    };

    const next = applyPlanReplannedDiff(baseTree(), diff);
    const ids = flattenIds(next);
    assert.deepEqual(ids, ['root', 'stage-a', 'stage-b', 'stage-c']);
    const stageC = findNode(next, 'stage-c');
    assert.ok(stageC);
    assert.equal(stageC.label, 'Stage C');
    assert.equal(stageC.status, 'pending');
  }

  // === Case 2: removed-only — a stage drops out of the plan ===
  {
    const newNodes: PlanNodeSnapshot[] = [
      makeSnapshot('root', {
        status: 'running',
        children: [
          makeSnapshot('stage-a', { parentId: 'root' }),
        ],
      }),
      makeSnapshot('stage-a', { parentId: 'root', label: 'Stage A', status: 'completed' }),
    ];
    const diff: PlanReplannedDiff = {
      oldNodes: [],
      newNodes,
      added: [],
      removed: ['stage-b'],
      modified: [],
      reason: 'agent pruned plan',
    };

    const next = applyPlanReplannedDiff(baseTree(), diff);
    const ids = flattenIds(next);
    assert.deepEqual(ids, ['root', 'stage-a']);
    assert.equal(findNode(next, 'stage-b'), null);
  }

  // === Case 3: modified-only — stage-b status flips, no structural change ===
  {
    const newNodes: PlanNodeSnapshot[] = [
      makeSnapshot('root', {
        status: 'running',
        children: [
          makeSnapshot('stage-a', { parentId: 'root' }),
          makeSnapshot('stage-b', { parentId: 'root' }),
        ],
      }),
      makeSnapshot('stage-a', { parentId: 'root', label: 'Stage A', status: 'completed' }),
      makeSnapshot('stage-b', {
        parentId: 'root',
        label: 'Stage B (re-run)',
        status: 'failed',
      }),
    ];
    const diff: PlanReplannedDiff = {
      oldNodes: [],
      newNodes,
      added: [],
      removed: [],
      modified: ['stage-b'],
      reason: 'stage-b retried after failure',
    };

    const next = applyPlanReplannedDiff(baseTree(), diff);
    const stageB = findNode(next, 'stage-b');
    assert.ok(stageB);
    assert.equal(stageB.status, 'failed');
    assert.equal(stageB.label, 'Stage B (re-run)');
    // No structural changes.
    assert.deepEqual(flattenIds(next), ['root', 'stage-a', 'stage-b']);
  }

  // === Case 4: mixed — add, remove, AND modify in one diff ===
  {
    const newNodes: PlanNodeSnapshot[] = [
      makeSnapshot('root', {
        status: 'running',
        children: [
          makeSnapshot('stage-a', { parentId: 'root' }),
          makeSnapshot('stage-c', { parentId: 'root' }),
        ],
      }),
      makeSnapshot('stage-a', {
        parentId: 'root',
        label: 'Stage A v2',
        status: 'running',
      }),
      makeSnapshot('stage-c', {
        parentId: 'root',
        label: 'Stage C (new)',
        status: 'pending',
      }),
    ];
    const diff: PlanReplannedDiff = {
      oldNodes: [],
      newNodes,
      added: ['stage-c'],
      removed: ['stage-b'],
      modified: ['stage-a'],
      reason: 'agent restructured plan after data review',
    };

    const next = applyPlanReplannedDiff(baseTree(), diff);
    assert.deepEqual(flattenIds(next), ['root', 'stage-a', 'stage-c']);
    const stageA = findNode(next, 'stage-a');
    assert.ok(stageA);
    assert.equal(stageA.label, 'Stage A v2');
    assert.equal(stageA.status, 'running');
    assert.equal(findNode(next, 'stage-b'), null);
    const stageC = findNode(next, 'stage-c');
    assert.ok(stageC);
    assert.equal(stageC.label, 'Stage C (new)');
  }

  // === Case 5: empty newNodes + currentTree=null → returns null (no crash) ===
  {
    const diff: PlanReplannedDiff = {
      oldNodes: [],
      newNodes: [],
      added: [],
      removed: [],
      modified: [],
      reason: 'noop',
    };
    assert.equal(applyPlanReplannedDiff(null, diff), null);
  }

  console.log('[contract] PASS plan-replanned-reducer (5 cases)');
}

run();
