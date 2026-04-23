"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const react_1 = require("react");
const server_1 = require("react-dom/server");
const lucide_react_1 = require("lucide-react");
const sidebarLayout_1 = require("../../src/renderer/utils/sidebarLayout");
const SidebarItem_1 = require("../../src/renderer/components/sidebar/SidebarItem");
const keyboardShortcut_1 = require("../../src/renderer/utils/keyboardShortcut");
function run() {
    {
        const state = (0, sidebarLayout_1.createInitialSidebarLayoutState)(1280);
        strict_1.default.equal(state.collapsed, false);
        strict_1.default.equal(state.collapsedByUser, false);
    }
    {
        const state = (0, sidebarLayout_1.createInitialSidebarLayoutState)(sidebarLayout_1.SIDEBAR_BREAKPOINT - 1);
        strict_1.default.equal(state.collapsed, true);
        strict_1.default.equal(state.collapsedByUser, false);
    }
    {
        const state = (0, sidebarLayout_1.toggleSidebarLayoutState)({ collapsed: false, collapsedByUser: false });
        strict_1.default.deepEqual(state, { collapsed: true, collapsedByUser: true });
    }
    {
        const state = (0, sidebarLayout_1.resolveResponsiveSidebarLayoutState)({ collapsed: false, collapsedByUser: false }, sidebarLayout_1.SIDEBAR_BREAKPOINT - 1);
        strict_1.default.deepEqual(state, { collapsed: true, collapsedByUser: false });
    }
    {
        const state = (0, sidebarLayout_1.resolveResponsiveSidebarLayoutState)({ collapsed: false, collapsedByUser: true }, sidebarLayout_1.SIDEBAR_BREAKPOINT - 1);
        strict_1.default.deepEqual(state, { collapsed: false, collapsedByUser: true });
    }
    {
        const encoded = (0, sidebarLayout_1.serializeSidebarLayoutState)({ collapsed: true, collapsedByUser: true });
        const parsed = (0, sidebarLayout_1.parseStoredSidebarLayoutState)(encoded);
        strict_1.default.deepEqual(parsed, { collapsed: true, collapsedByUser: true });
    }
    {
        strict_1.default.equal((0, sidebarLayout_1.parseStoredSidebarLayoutState)('{"collapsed":true}'), null);
        strict_1.default.equal((0, sidebarLayout_1.parseStoredSidebarLayoutState)('not-json'), null);
    }
    {
        const event = { key: '\\', ctrlKey: true, metaKey: false, altKey: false, shiftKey: false };
        strict_1.default.equal((0, keyboardShortcut_1.matchesShortcut)(event, 'ctrl+\\'), true);
        strict_1.default.equal((0, keyboardShortcut_1.matchesShortcut)(event, 'ctrl+m'), false);
    }
    {
        const event = { key: '\\', ctrlKey: false, metaKey: true, altKey: false, shiftKey: false };
        strict_1.default.equal((0, keyboardShortcut_1.matchesShortcut)(event, 'meta+\\'), true);
    }
    {
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(SidebarItem_1.SidebarItem, {
            icon: lucide_react_1.FolderOpen,
            label: 'Files',
            collapsed: true,
            onClick: () => undefined,
        }));
        strict_1.default.match(html, /data-state="closed"/);
        strict_1.default.match(html, /aria-label="Files"/);
        strict_1.default.doesNotMatch(html, /title="Files"/);
    }
    console.log('[contract] PASS sidebar-collapse (10 cases)');
}
run();
