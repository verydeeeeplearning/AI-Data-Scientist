"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SIDEBAR_COLLAPSED_WIDTH = exports.SIDEBAR_EXPANDED_WIDTH = exports.SIDEBAR_BREAKPOINT = exports.SIDEBAR_STORAGE_KEY = void 0;
exports.createInitialSidebarLayoutState = createInitialSidebarLayoutState;
exports.toggleSidebarLayoutState = toggleSidebarLayoutState;
exports.resolveResponsiveSidebarLayoutState = resolveResponsiveSidebarLayoutState;
exports.serializeSidebarLayoutState = serializeSidebarLayoutState;
exports.parseStoredSidebarLayoutState = parseStoredSidebarLayoutState;
exports.SIDEBAR_STORAGE_KEY = 'ds-agent-sidebar-layout';
exports.SIDEBAR_BREAKPOINT = 768;
exports.SIDEBAR_EXPANDED_WIDTH = 240;
exports.SIDEBAR_COLLAPSED_WIDTH = 56;
function createInitialSidebarLayoutState(viewportWidth) {
    return {
        collapsed: viewportWidth < exports.SIDEBAR_BREAKPOINT,
        collapsedByUser: false,
    };
}
function toggleSidebarLayoutState(state) {
    return {
        collapsed: !state.collapsed,
        collapsedByUser: true,
    };
}
function resolveResponsiveSidebarLayoutState(state, viewportWidth) {
    if (state.collapsedByUser) {
        return state;
    }
    return createInitialSidebarLayoutState(viewportWidth);
}
function serializeSidebarLayoutState(state) {
    return JSON.stringify(state);
}
function parseStoredSidebarLayoutState(raw) {
    if (!raw) {
        return null;
    }
    try {
        const parsed = JSON.parse(raw);
        if (typeof parsed.collapsed !== 'boolean' || typeof parsed.collapsedByUser !== 'boolean') {
            return null;
        }
        return {
            collapsed: parsed.collapsed,
            collapsedByUser: parsed.collapsedByUser,
        };
    }
    catch {
        return null;
    }
}
