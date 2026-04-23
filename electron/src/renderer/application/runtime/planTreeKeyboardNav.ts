/**
 * Pure reducer for the Plan Tree keyboard-navigation state.
 *
 * The component owns visible state (focused id + which parents are
 * collapsed) and delegates every key press to ``planTreeKeyboardNav`` so
 * the transitions can be exercised by node-only contract specs. No React,
 * no DOM, no zustand here.
 *
 * Behavior summary (matches WAI-ARIA 1.2 Tree Pattern, simplified):
 *  - ``ArrowDown``: move focus to next visible node (no wrap at end).
 *  - ``ArrowUp``  : move focus to previous visible node (no wrap at top).
 *  - ``ArrowRight``:
 *      - on a collapsed parent → expand (focus stays).
 *      - on an expanded parent → move focus to first visible child.
 *      - on a leaf → no-op.
 *  - ``ArrowLeft``:
 *      - on an expanded parent → collapse (focus stays).
 *      - on a collapsed parent OR a leaf → move focus to parent (if any),
 *        else no-op.
 *  - ``Home`` / ``End``: first / last visible node.
 *
 * This module is intentionally framework-free and side-effect free; the
 * component layer translates the returned state into focus calls.
 */

export interface PlanTreeKeyboardNode {
  readonly id: string;
  readonly parentId: string | null;
  /**
   * Whether this node has children in the underlying plan tree. Stored
   * separately from ``expanded`` so the reducer can tell parents from
   * leaves even when fully collapsed.
   */
  readonly hasChildren: boolean;
}

export interface PlanTreeKeyboardState {
  readonly focusedId: string | null;
  /** Collapsed parent ids. Anything not in this set is considered expanded. */
  readonly collapsedIds: ReadonlySet<string>;
}

export type PlanTreeKeyboardKey =
  | 'ArrowDown'
  | 'ArrowUp'
  | 'ArrowRight'
  | 'ArrowLeft'
  | 'Home'
  | 'End';

export interface PlanTreeKeyboardInput {
  readonly nodes: ReadonlyArray<PlanTreeKeyboardNode>;
  readonly state: PlanTreeKeyboardState;
  readonly key: PlanTreeKeyboardKey;
}

function indexById(
  nodes: ReadonlyArray<PlanTreeKeyboardNode>,
): Map<string, PlanTreeKeyboardNode> {
  const out = new Map<string, PlanTreeKeyboardNode>();
  for (const node of nodes) {
    out.set(node.id, node);
  }
  return out;
}

/**
 * Compute the visible (currently rendered) node ids in DOM order, taking
 * the collapsed-set into account. A node is visible iff none of its
 * ancestors are collapsed.
 */
export function computeVisibleIds(
  nodes: ReadonlyArray<PlanTreeKeyboardNode>,
  collapsedIds: ReadonlySet<string>,
): string[] {
  const byId = indexById(nodes);
  const visible: string[] = [];
  for (const node of nodes) {
    let cursor: PlanTreeKeyboardNode | undefined = byId.get(node.parentId ?? '');
    let hidden = false;
    while (cursor) {
      if (collapsedIds.has(cursor.id)) {
        hidden = true;
        break;
      }
      cursor = byId.get(cursor.parentId ?? '');
    }
    if (!hidden) {
      visible.push(node.id);
    }
  }
  return visible;
}

function withCollapsed(
  current: ReadonlySet<string>,
  id: string,
  collapsed: boolean,
): ReadonlySet<string> {
  const next = new Set(current);
  if (collapsed) {
    next.add(id);
  } else {
    next.delete(id);
  }
  return next;
}

export function planTreeKeyboardNav(
  input: PlanTreeKeyboardInput,
): PlanTreeKeyboardState {
  const { nodes, state, key } = input;
  if (nodes.length === 0) {
    return state;
  }

  const byId = indexById(nodes);
  const visible = computeVisibleIds(nodes, state.collapsedIds);
  if (visible.length === 0) {
    return state;
  }

  const focusedId = state.focusedId && byId.has(state.focusedId)
    ? state.focusedId
    : visible[0];
  const focusedNode = byId.get(focusedId);
  if (!focusedNode) {
    return state;
  }

  const visibleIndex = visible.indexOf(focusedId);

  switch (key) {
    case 'ArrowDown': {
      if (visibleIndex < 0) {
        return { ...state, focusedId: visible[0] };
      }
      if (visibleIndex >= visible.length - 1) {
        // No wrap — stay put.
        return { ...state, focusedId };
      }
      return { ...state, focusedId: visible[visibleIndex + 1] };
    }
    case 'ArrowUp': {
      if (visibleIndex <= 0) {
        return { ...state, focusedId: visible[0] };
      }
      return { ...state, focusedId: visible[visibleIndex - 1] };
    }
    case 'Home': {
      return { ...state, focusedId: visible[0] };
    }
    case 'End': {
      return { ...state, focusedId: visible[visible.length - 1] };
    }
    case 'ArrowRight': {
      if (!focusedNode.hasChildren) {
        // Leaf → no-op.
        return { ...state, focusedId };
      }
      if (state.collapsedIds.has(focusedId)) {
        // Collapsed parent → expand (focus stays).
        return {
          focusedId,
          collapsedIds: withCollapsed(state.collapsedIds, focusedId, false),
        };
      }
      // Expanded parent → move to first visible child.
      const childId = nodes.find((node) => node.parentId === focusedId)?.id;
      if (!childId) {
        return { ...state, focusedId };
      }
      return { ...state, focusedId: childId };
    }
    case 'ArrowLeft': {
      if (focusedNode.hasChildren && !state.collapsedIds.has(focusedId)) {
        // Expanded parent → collapse (focus stays).
        return {
          focusedId,
          collapsedIds: withCollapsed(state.collapsedIds, focusedId, true),
        };
      }
      // Leaf or collapsed parent → move to parent if any.
      if (focusedNode.parentId && byId.has(focusedNode.parentId)) {
        return { ...state, focusedId: focusedNode.parentId };
      }
      return { ...state, focusedId };
    }
    default:
      return state;
  }
}

/**
 * Helper used by the renderer to flatten a ``PlanNode`` tree into the
 * ``PlanTreeKeyboardNode`` list this reducer expects. Kept here so tests
 * can stay framework-free without importing the events module.
 */
export interface FlattenablePlanNode {
  readonly id: string;
  readonly children: ReadonlyArray<FlattenablePlanNode>;
}

export function flattenForKeyboardNav(
  root: FlattenablePlanNode | null,
): PlanTreeKeyboardNode[] {
  const out: PlanTreeKeyboardNode[] = [];
  if (!root) return out;
  function walk(node: FlattenablePlanNode, parentId: string | null): void {
    out.push({
      id: node.id,
      parentId,
      hasChildren: node.children.length > 0,
    });
    for (const child of node.children) {
      walk(child, node.id);
    }
  }
  walk(root, null);
  return out;
}
