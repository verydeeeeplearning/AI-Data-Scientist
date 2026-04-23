import assert from 'node:assert/strict';

import {
  computeVisibleIds,
  flattenForKeyboardNav,
  planTreeKeyboardNav,
  type PlanTreeKeyboardNode,
  type PlanTreeKeyboardState,
} from '../../src/renderer/application/runtime/planTreeKeyboardNav';

/**
 * Test fixture: a small tree with one root, two parent stages, and one
 * leaf each — enough to cover horizontal AND vertical movement.
 *
 * root (parent)
 *   stage-a (parent)
 *     leaf-a1
 *   stage-b (leaf)
 */
function buildNodes(): PlanTreeKeyboardNode[] {
  return [
    { id: 'root', parentId: null, hasChildren: true },
    { id: 'stage-a', parentId: 'root', hasChildren: true },
    { id: 'leaf-a1', parentId: 'stage-a', hasChildren: false },
    { id: 'stage-b', parentId: 'root', hasChildren: false },
  ];
}

function emptyState(focusedId: string | null = 'root'): PlanTreeKeyboardState {
  return { focusedId, collapsedIds: new Set<string>() };
}

function run(): void {
  const nodes = buildNodes();

  // === Case 1: ArrowDown moves to next visible node ===
  {
    const state = emptyState('root');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowDown' });
    assert.equal(next.focusedId, 'stage-a');
  }

  // === Case 2: ArrowDown at the last visible node stays put (no wrap) ===
  {
    const state = emptyState('stage-b');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowDown' });
    assert.equal(next.focusedId, 'stage-b');
  }

  // === Case 3: ArrowUp moves to previous visible node ===
  {
    const state = emptyState('leaf-a1');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowUp' });
    assert.equal(next.focusedId, 'stage-a');
  }

  // === Case 4: ArrowUp at the very top stays put (no wrap) ===
  {
    const state = emptyState('root');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowUp' });
    assert.equal(next.focusedId, 'root');
  }

  // === Case 5: ArrowRight on a collapsed parent expands (focus stays) ===
  {
    const state: PlanTreeKeyboardState = {
      focusedId: 'stage-a',
      collapsedIds: new Set(['stage-a']),
    };
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowRight' });
    assert.equal(next.focusedId, 'stage-a');
    assert.equal(next.collapsedIds.has('stage-a'), false);
  }

  // === Case 6: ArrowRight on an expanded parent moves to first child ===
  {
    const state = emptyState('stage-a');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowRight' });
    assert.equal(next.focusedId, 'leaf-a1');
  }

  // === Case 7: ArrowRight on a leaf is a no-op ===
  {
    const state = emptyState('stage-b');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowRight' });
    assert.equal(next.focusedId, 'stage-b');
    assert.equal(next.collapsedIds.size, 0);
  }

  // === Case 8: ArrowLeft on an expanded parent collapses (focus stays) ===
  {
    const state = emptyState('stage-a');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowLeft' });
    assert.equal(next.focusedId, 'stage-a');
    assert.equal(next.collapsedIds.has('stage-a'), true);
  }

  // === Case 9: ArrowLeft on a leaf moves focus to its parent ===
  {
    const state = emptyState('leaf-a1');
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowLeft' });
    assert.equal(next.focusedId, 'stage-a');
  }

  // === Case 10: ArrowLeft on a collapsed parent moves to its parent ===
  {
    const state: PlanTreeKeyboardState = {
      focusedId: 'stage-a',
      collapsedIds: new Set(['stage-a']),
    };
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowLeft' });
    assert.equal(next.focusedId, 'root');
  }

  // === Case 11: ArrowLeft on root (no parent) is a no-op ===
  {
    const state: PlanTreeKeyboardState = {
      focusedId: 'root',
      collapsedIds: new Set(['root']),
    };
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowLeft' });
    assert.equal(next.focusedId, 'root');
  }

  // === Case 12: Home / End jump to bounds ===
  {
    const state = emptyState('stage-a');
    const home = planTreeKeyboardNav({ nodes, state, key: 'Home' });
    assert.equal(home.focusedId, 'root');
    const end = planTreeKeyboardNav({ nodes, state, key: 'End' });
    assert.equal(end.focusedId, 'stage-b');
  }

  // === Case 13: computeVisibleIds hides descendants of collapsed parents ===
  {
    const collapsed = new Set(['stage-a']);
    const visible = computeVisibleIds(nodes, collapsed);
    assert.deepEqual(visible, ['root', 'stage-a', 'stage-b']);
    // Now a collapsed root should hide everything except itself.
    const collapsedRoot = new Set(['root']);
    const visibleRoot = computeVisibleIds(nodes, collapsedRoot);
    assert.deepEqual(visibleRoot, ['root']);
  }

  // === Case 14: ArrowDown skips children of collapsed parent ===
  {
    const state: PlanTreeKeyboardState = {
      focusedId: 'stage-a',
      collapsedIds: new Set(['stage-a']),
    };
    const next = planTreeKeyboardNav({ nodes, state, key: 'ArrowDown' });
    assert.equal(next.focusedId, 'stage-b');
  }

  // === Case 15: flattenForKeyboardNav produces correct shape ===
  {
    const flat = flattenForKeyboardNav({
      id: 'root',
      children: [
        { id: 'stage-a', children: [{ id: 'leaf-a1', children: [] }] },
        { id: 'stage-b', children: [] },
      ],
    });
    assert.deepEqual(flat, [
      { id: 'root', parentId: null, hasChildren: true },
      { id: 'stage-a', parentId: 'root', hasChildren: true },
      { id: 'leaf-a1', parentId: 'stage-a', hasChildren: false },
      { id: 'stage-b', parentId: 'root', hasChildren: false },
    ]);
  }

  // === Case 16: empty tree is a safe no-op ===
  {
    const state = emptyState(null);
    const next = planTreeKeyboardNav({ nodes: [], state, key: 'ArrowDown' });
    assert.deepEqual(next, state);
  }

  console.log('[contract] PASS plan-tree-a11y-reducer (16 cases)');
}

run();
