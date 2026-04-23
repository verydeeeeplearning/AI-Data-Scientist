"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.computeVisibleIds = computeVisibleIds;
exports.planTreeKeyboardNav = planTreeKeyboardNav;
exports.flattenForKeyboardNav = flattenForKeyboardNav;
function indexById(nodes) {
    const out = new Map();
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
function computeVisibleIds(nodes, collapsedIds) {
    const byId = indexById(nodes);
    const visible = [];
    for (const node of nodes) {
        let cursor = byId.get(node.parentId ?? '');
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
function withCollapsed(current, id, collapsed) {
    const next = new Set(current);
    if (collapsed) {
        next.add(id);
    }
    else {
        next.delete(id);
    }
    return next;
}
function planTreeKeyboardNav(input) {
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
function flattenForKeyboardNav(root) {
    const out = [];
    if (!root)
        return out;
    function walk(node, parentId) {
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
