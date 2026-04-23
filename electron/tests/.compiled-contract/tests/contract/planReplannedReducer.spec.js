"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const applyPlanReplannedDiff_1 = require("../../src/renderer/application/runtime/applyPlanReplannedDiff");
function makeNode(id, overrides = {}) {
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
function makeSnapshot(id, overrides = {}) {
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
function flattenIds(node) {
    if (!node)
        return [];
    const out = [node.id];
    for (const child of node.children) {
        out.push(...flattenIds(child));
    }
    return out;
}
function findNode(node, id) {
    if (!node)
        return null;
    if (node.id === id)
        return node;
    for (const child of node.children) {
        const found = findNode(child, id);
        if (found)
            return found;
    }
    return null;
}
function run() {
    // Common starting tree: root with stages A and B as children.
    function baseTree() {
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
        const newNodes = [
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
        const diff = {
            oldNodes: [],
            newNodes,
            added: ['stage-c'],
            removed: [],
            modified: [],
            reason: 'agent expanded plan',
        };
        const next = (0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(baseTree(), diff);
        const ids = flattenIds(next);
        strict_1.default.deepEqual(ids, ['root', 'stage-a', 'stage-b', 'stage-c']);
        const stageC = findNode(next, 'stage-c');
        strict_1.default.ok(stageC);
        strict_1.default.equal(stageC.label, 'Stage C');
        strict_1.default.equal(stageC.status, 'pending');
    }
    // === Case 2: removed-only — a stage drops out of the plan ===
    {
        const newNodes = [
            makeSnapshot('root', {
                status: 'running',
                children: [
                    makeSnapshot('stage-a', { parentId: 'root' }),
                ],
            }),
            makeSnapshot('stage-a', { parentId: 'root', label: 'Stage A', status: 'completed' }),
        ];
        const diff = {
            oldNodes: [],
            newNodes,
            added: [],
            removed: ['stage-b'],
            modified: [],
            reason: 'agent pruned plan',
        };
        const next = (0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(baseTree(), diff);
        const ids = flattenIds(next);
        strict_1.default.deepEqual(ids, ['root', 'stage-a']);
        strict_1.default.equal(findNode(next, 'stage-b'), null);
    }
    // === Case 3: modified-only — stage-b status flips, no structural change ===
    {
        const newNodes = [
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
        const diff = {
            oldNodes: [],
            newNodes,
            added: [],
            removed: [],
            modified: ['stage-b'],
            reason: 'stage-b retried after failure',
        };
        const next = (0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(baseTree(), diff);
        const stageB = findNode(next, 'stage-b');
        strict_1.default.ok(stageB);
        strict_1.default.equal(stageB.status, 'failed');
        strict_1.default.equal(stageB.label, 'Stage B (re-run)');
        // No structural changes.
        strict_1.default.deepEqual(flattenIds(next), ['root', 'stage-a', 'stage-b']);
    }
    // === Case 4: mixed — add, remove, AND modify in one diff ===
    {
        const newNodes = [
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
        const diff = {
            oldNodes: [],
            newNodes,
            added: ['stage-c'],
            removed: ['stage-b'],
            modified: ['stage-a'],
            reason: 'agent restructured plan after data review',
        };
        const next = (0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(baseTree(), diff);
        strict_1.default.deepEqual(flattenIds(next), ['root', 'stage-a', 'stage-c']);
        const stageA = findNode(next, 'stage-a');
        strict_1.default.ok(stageA);
        strict_1.default.equal(stageA.label, 'Stage A v2');
        strict_1.default.equal(stageA.status, 'running');
        strict_1.default.equal(findNode(next, 'stage-b'), null);
        const stageC = findNode(next, 'stage-c');
        strict_1.default.ok(stageC);
        strict_1.default.equal(stageC.label, 'Stage C (new)');
    }
    // === Case 5: empty newNodes + currentTree=null → returns null (no crash) ===
    {
        const diff = {
            oldNodes: [],
            newNodes: [],
            added: [],
            removed: [],
            modified: [],
            reason: 'noop',
        };
        strict_1.default.equal((0, applyPlanReplannedDiff_1.applyPlanReplannedDiff)(null, diff), null);
    }
    console.log('[contract] PASS plan-replanned-reducer (5 cases)');
}
run();
