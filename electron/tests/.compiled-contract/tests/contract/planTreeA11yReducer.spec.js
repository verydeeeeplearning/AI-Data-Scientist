"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const planTreeKeyboardNav_1 = require("../../src/renderer/application/runtime/planTreeKeyboardNav");
/**
 * Test fixture: a small tree with one root, two parent stages, and one
 * leaf each — enough to cover horizontal AND vertical movement.
 *
 * root (parent)
 *   stage-a (parent)
 *     leaf-a1
 *   stage-b (leaf)
 */
function buildNodes() {
    return [
        { id: 'root', parentId: null, hasChildren: true },
        { id: 'stage-a', parentId: 'root', hasChildren: true },
        { id: 'leaf-a1', parentId: 'stage-a', hasChildren: false },
        { id: 'stage-b', parentId: 'root', hasChildren: false },
    ];
}
function emptyState(focusedId = 'root') {
    return { focusedId, collapsedIds: new Set() };
}
function run() {
    const nodes = buildNodes();
    // === Case 1: ArrowDown moves to next visible node ===
    {
        const state = emptyState('root');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowDown' });
        strict_1.default.equal(next.focusedId, 'stage-a');
    }
    // === Case 2: ArrowDown at the last visible node stays put (no wrap) ===
    {
        const state = emptyState('stage-b');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowDown' });
        strict_1.default.equal(next.focusedId, 'stage-b');
    }
    // === Case 3: ArrowUp moves to previous visible node ===
    {
        const state = emptyState('leaf-a1');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowUp' });
        strict_1.default.equal(next.focusedId, 'stage-a');
    }
    // === Case 4: ArrowUp at the very top stays put (no wrap) ===
    {
        const state = emptyState('root');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowUp' });
        strict_1.default.equal(next.focusedId, 'root');
    }
    // === Case 5: ArrowRight on a collapsed parent expands (focus stays) ===
    {
        const state = {
            focusedId: 'stage-a',
            collapsedIds: new Set(['stage-a']),
        };
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowRight' });
        strict_1.default.equal(next.focusedId, 'stage-a');
        strict_1.default.equal(next.collapsedIds.has('stage-a'), false);
    }
    // === Case 6: ArrowRight on an expanded parent moves to first child ===
    {
        const state = emptyState('stage-a');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowRight' });
        strict_1.default.equal(next.focusedId, 'leaf-a1');
    }
    // === Case 7: ArrowRight on a leaf is a no-op ===
    {
        const state = emptyState('stage-b');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowRight' });
        strict_1.default.equal(next.focusedId, 'stage-b');
        strict_1.default.equal(next.collapsedIds.size, 0);
    }
    // === Case 8: ArrowLeft on an expanded parent collapses (focus stays) ===
    {
        const state = emptyState('stage-a');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowLeft' });
        strict_1.default.equal(next.focusedId, 'stage-a');
        strict_1.default.equal(next.collapsedIds.has('stage-a'), true);
    }
    // === Case 9: ArrowLeft on a leaf moves focus to its parent ===
    {
        const state = emptyState('leaf-a1');
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowLeft' });
        strict_1.default.equal(next.focusedId, 'stage-a');
    }
    // === Case 10: ArrowLeft on a collapsed parent moves to its parent ===
    {
        const state = {
            focusedId: 'stage-a',
            collapsedIds: new Set(['stage-a']),
        };
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowLeft' });
        strict_1.default.equal(next.focusedId, 'root');
    }
    // === Case 11: ArrowLeft on root (no parent) is a no-op ===
    {
        const state = {
            focusedId: 'root',
            collapsedIds: new Set(['root']),
        };
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowLeft' });
        strict_1.default.equal(next.focusedId, 'root');
    }
    // === Case 12: Home / End jump to bounds ===
    {
        const state = emptyState('stage-a');
        const home = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'Home' });
        strict_1.default.equal(home.focusedId, 'root');
        const end = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'End' });
        strict_1.default.equal(end.focusedId, 'stage-b');
    }
    // === Case 13: computeVisibleIds hides descendants of collapsed parents ===
    {
        const collapsed = new Set(['stage-a']);
        const visible = (0, planTreeKeyboardNav_1.computeVisibleIds)(nodes, collapsed);
        strict_1.default.deepEqual(visible, ['root', 'stage-a', 'stage-b']);
        // Now a collapsed root should hide everything except itself.
        const collapsedRoot = new Set(['root']);
        const visibleRoot = (0, planTreeKeyboardNav_1.computeVisibleIds)(nodes, collapsedRoot);
        strict_1.default.deepEqual(visibleRoot, ['root']);
    }
    // === Case 14: ArrowDown skips children of collapsed parent ===
    {
        const state = {
            focusedId: 'stage-a',
            collapsedIds: new Set(['stage-a']),
        };
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes, state, key: 'ArrowDown' });
        strict_1.default.equal(next.focusedId, 'stage-b');
    }
    // === Case 15: flattenForKeyboardNav produces correct shape ===
    {
        const flat = (0, planTreeKeyboardNav_1.flattenForKeyboardNav)({
            id: 'root',
            children: [
                { id: 'stage-a', children: [{ id: 'leaf-a1', children: [] }] },
                { id: 'stage-b', children: [] },
            ],
        });
        strict_1.default.deepEqual(flat, [
            { id: 'root', parentId: null, hasChildren: true },
            { id: 'stage-a', parentId: 'root', hasChildren: true },
            { id: 'leaf-a1', parentId: 'stage-a', hasChildren: false },
            { id: 'stage-b', parentId: 'root', hasChildren: false },
        ]);
    }
    // === Case 16: empty tree is a safe no-op ===
    {
        const state = emptyState(null);
        const next = (0, planTreeKeyboardNav_1.planTreeKeyboardNav)({ nodes: [], state, key: 'ArrowDown' });
        strict_1.default.deepEqual(next, state);
    }
    console.log('[contract] PASS plan-tree-a11y-reducer (16 cases)');
}
run();
