/**
 * Pure reducer for ``plan.replanned`` events.
 *
 * Given the previously-known plan tree and a structural diff payload,
 * produce the next plan tree to render. Kept framework-free so it can be
 * exercised by node-only contract specs (no React, no zustand).
 *
 * Strategy: when the backend supplies ``newNodes`` (the post-replan flat
 * list including the root), reconstruct the tree from that list. Falls
 * back to merging just the ``modified`` ids onto the current tree when no
 * new tree material is provided (defensive — backends MAY ship slimmer
 * diffs in the future).
 */

import type { PlanNode, PlanNodeStatus } from '../../types/events';

export interface PlanReplannedDiff {
  readonly oldNodes: ReadonlyArray<PlanNodeSnapshot>;
  readonly newNodes: ReadonlyArray<PlanNodeSnapshot>;
  readonly added: ReadonlyArray<string>;
  readonly removed: ReadonlyArray<string>;
  readonly modified: ReadonlyArray<string>;
  readonly reason: string;
}

/**
 * Snapshot shape used inside ``oldNodes`` / ``newNodes`` payloads. Mirrors
 * ``PlanNode`` but every field is optional except the discriminating id —
 * the backend serializes flat lists where children/refs may be omitted.
 */
export interface PlanNodeSnapshot {
  readonly id: string;
  readonly parentId?: string | null;
  readonly label?: string;
  readonly description?: string;
  readonly status?: PlanNodeStatus;
  readonly estimatedDurationSec?: number;
  readonly startedAt?: number;
  readonly completedAt?: number;
  readonly reasoningRefs?: ReadonlyArray<string>;
  readonly toolEventRefs?: ReadonlyArray<string>;
  readonly children?: ReadonlyArray<PlanNodeSnapshot>;
}

const PLAN_NODE_STATUSES: ReadonlySet<PlanNodeStatus> = new Set([
  'pending',
  'running',
  'completed',
  'failed',
  'skipped',
]);

function asPlanNodeStatus(value: unknown): PlanNodeStatus {
  if (typeof value === 'string' && PLAN_NODE_STATUSES.has(value as PlanNodeStatus)) {
    return value as PlanNodeStatus;
  }
  return 'pending';
}

function snapshotToPlanNode(snapshot: PlanNodeSnapshot, fallbackChildren: PlanNode[]): PlanNode {
  return {
    id: snapshot.id,
    parentId: snapshot.parentId ?? undefined,
    label: snapshot.label ?? snapshot.id,
    description: snapshot.description,
    status: asPlanNodeStatus(snapshot.status),
    estimatedDurationSec: snapshot.estimatedDurationSec,
    startedAt: snapshot.startedAt,
    completedAt: snapshot.completedAt,
    reasoningRefs: snapshot.reasoningRefs ? [...snapshot.reasoningRefs] : [],
    toolEventRefs: snapshot.toolEventRefs ? [...snapshot.toolEventRefs] : [],
    children: fallbackChildren,
  };
}

function buildTreeFromSnapshots(
  newNodes: ReadonlyArray<PlanNodeSnapshot>,
  removed: ReadonlySet<string>,
): PlanNode | null {
  if (newNodes.length === 0) {
    return null;
  }

  const byId = new Map<string, PlanNodeSnapshot>();
  for (const snapshot of newNodes) {
    if (removed.has(snapshot.id)) {
      continue;
    }
    byId.set(snapshot.id, snapshot);
  }

  const referencedAsChild = new Set<string>();
  for (const snapshot of byId.values()) {
    if (snapshot.children) {
      for (const child of snapshot.children) {
        referencedAsChild.add(child.id);
      }
    }
    if (snapshot.parentId && byId.has(snapshot.parentId)) {
      referencedAsChild.add(snapshot.id);
    }
  }

  const roots: PlanNodeSnapshot[] = [];
  for (const snapshot of byId.values()) {
    if (!referencedAsChild.has(snapshot.id)) {
      roots.push(snapshot);
    }
  }

  const root = roots[0] ?? newNodes[0];
  const visited = new Set<string>();

  function build(snapshot: PlanNodeSnapshot): PlanNode {
    if (visited.has(snapshot.id)) {
      // Defensive: cycle. Emit a leaf to break the loop.
      return snapshotToPlanNode(snapshot, []);
    }
    visited.add(snapshot.id);

    const childSnapshots: PlanNodeSnapshot[] = [];
    if (snapshot.children && snapshot.children.length > 0) {
      for (const child of snapshot.children) {
        const resolved = byId.get(child.id) ?? child;
        if (!removed.has(resolved.id)) {
          childSnapshots.push(resolved);
        }
      }
    } else {
      // Fall back to parentId linkage when ``children`` is absent.
      for (const candidate of byId.values()) {
        if (candidate.parentId === snapshot.id && candidate.id !== snapshot.id) {
          childSnapshots.push(candidate);
        }
      }
    }

    return snapshotToPlanNode(
      snapshot,
      childSnapshots.map((child) => build(child)),
    );
  }

  return build(root);
}

function applyModifiedToTree(
  current: PlanNode,
  modifiedById: ReadonlyMap<string, PlanNodeSnapshot>,
  removed: ReadonlySet<string>,
): PlanNode {
  const nextChildren: PlanNode[] = [];
  for (const child of current.children) {
    if (removed.has(child.id)) {
      continue;
    }
    nextChildren.push(applyModifiedToTree(child, modifiedById, removed));
  }

  const patch = modifiedById.get(current.id);
  if (!patch) {
    if (nextChildren.length !== current.children.length) {
      return { ...current, children: nextChildren };
    }
    let identical = true;
    for (let index = 0; index < nextChildren.length; index += 1) {
      if (nextChildren[index] !== current.children[index]) {
        identical = false;
        break;
      }
    }
    return identical ? current : { ...current, children: nextChildren };
  }

  return {
    ...current,
    label: patch.label ?? current.label,
    description: patch.description ?? current.description,
    status: asPlanNodeStatus(patch.status ?? current.status),
    estimatedDurationSec: patch.estimatedDurationSec ?? current.estimatedDurationSec,
    startedAt: patch.startedAt ?? current.startedAt,
    completedAt: patch.completedAt ?? current.completedAt,
    reasoningRefs: patch.reasoningRefs ? [...patch.reasoningRefs] : current.reasoningRefs,
    toolEventRefs: patch.toolEventRefs ? [...patch.toolEventRefs] : current.toolEventRefs,
    children: nextChildren,
  };
}

export function applyPlanReplannedDiff(
  currentTree: PlanNode | null,
  diff: PlanReplannedDiff,
): PlanNode | null {
  const removed = new Set(diff.removed);

  if (diff.newNodes.length > 0) {
    return buildTreeFromSnapshots(diff.newNodes, removed);
  }

  if (currentTree == null) {
    return null;
  }

  const modifiedById = new Map<string, PlanNodeSnapshot>();
  for (const id of diff.modified) {
    const snapshot = diff.oldNodes.find((node) => node.id === id);
    if (snapshot) {
      modifiedById.set(id, snapshot);
    }
  }

  return applyModifiedToTree(currentTree, modifiedById, removed);
}
