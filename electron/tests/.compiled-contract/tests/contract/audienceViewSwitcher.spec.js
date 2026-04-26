"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const audienceView_1 = require("../../src/renderer/domain/workspace/audienceView");
const applyAudienceView_1 = require("../../src/renderer/application/workspace/applyAudienceView");
const cardEmphasisAdopter_1 = require("../../src/renderer/application/workspace/cardEmphasisAdopter");
const workspaceStore_1 = require("../../src/renderer/stores/workspaceStore");
const ALL_TABS = ['overview', 'export'];
function createFakeStorage(initial = {}) {
    const store = { ...initial };
    return {
        store,
        getItem(key) {
            return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
        },
        setItem(key, value) {
            store[key] = value;
        },
    };
}
function run() {
    let cases = 0;
    // === applyAudienceViewToTabs returns the correct visible-tab subset for each profile ===
    {
        const dsTabs = (0, applyAudienceView_1.applyAudienceViewToTabs)(ALL_TABS, audienceView_1.AUDIENCE_VIEW_PROFILES.ds);
        strict_1.default.deepEqual(dsTabs, ['overview', 'export']);
        cases += 1;
        const execTabs = (0, applyAudienceView_1.applyAudienceViewToTabs)(ALL_TABS, audienceView_1.AUDIENCE_VIEW_PROFILES.exec);
        strict_1.default.deepEqual(execTabs, ['overview', 'export']);
        cases += 1;
        const mlTabs = (0, applyAudienceView_1.applyAudienceViewToTabs)(ALL_TABS, audienceView_1.AUDIENCE_VIEW_PROFILES.ml);
        strict_1.default.deepEqual(mlTabs, ['overview', 'export']);
        cases += 1;
        // Order is preserved: feed a permuted input and expect the same permutation back, filtered.
        const permuted = ['export', 'overview'];
        const execPermuted = (0, applyAudienceView_1.applyAudienceViewToTabs)(permuted, audienceView_1.AUDIENCE_VIEW_PROFILES.exec);
        strict_1.default.deepEqual(execPermuted, ['export', 'overview']);
        cases += 1;
    }
    // === resolveActiveTabForAudience: in-profile vs filtered-out vs empty ===
    {
        // In-profile active tab is preserved
        strict_1.default.equal((0, applyAudienceView_1.resolveActiveTabForAudience)('export', ALL_TABS, audienceView_1.AUDIENCE_VIEW_PROFILES.exec), 'export');
        cases += 1;
        // Active tab filtered out by a constrained profile falls back to first visible (`export`).
        const exportOnlyProfile = {
            id: 'exec',
            label: 'Export only (test)',
            description: 'Synthetic profile with a constrained tab set.',
            visibleTabs: ['export'],
            emphasis: 'summary',
        };
        strict_1.default.equal((0, applyAudienceView_1.resolveActiveTabForAudience)('overview', ALL_TABS, exportOnlyProfile), 'export');
        cases += 1;
        // Active tab filtered out, fallback respects the order of `allTabs` (not profile order).
        const reordered = ['export', 'overview'];
        strict_1.default.equal((0, applyAudienceView_1.resolveActiveTabForAudience)('overview', reordered, exportOnlyProfile), 'export');
        cases += 1;
        // Empty visible-tab set returns null. Construct a synthetic profile to hit that branch
        // (shipped profiles all have non-empty visibleTabs).
        const emptyProfile = {
            id: 'ds',
            label: 'Empty (test only)',
            description: 'Synthetic profile with no visible tabs.',
            visibleTabs: [],
            emphasis: 'detail',
        };
        strict_1.default.equal((0, applyAudienceView_1.resolveActiveTabForAudience)('overview', ALL_TABS, emptyProfile), null);
        cases += 1;
    }
    // === AUDIENCE_VIEW_PROFILES integrity ===
    {
        strict_1.default.deepEqual([...audienceView_1.AUDIENCE_VIEW_IDS], ['ds', 'exec', 'ml']);
        cases += 1;
        for (const id of audienceView_1.AUDIENCE_VIEW_IDS) {
            const profile = audienceView_1.AUDIENCE_VIEW_PROFILES[id];
            strict_1.default.ok(profile, `profile must exist for id ${id}`);
            strict_1.default.equal(profile.id, id, `profile.id must match key ${id}`);
            strict_1.default.equal(typeof profile.label, 'string');
            strict_1.default.ok(profile.label.length > 0, `profile ${id} must have a non-empty label`);
            strict_1.default.equal(typeof profile.description, 'string');
            strict_1.default.ok(profile.description.length > 0, `profile ${id} must have a non-empty description`);
            strict_1.default.ok(Array.isArray(profile.visibleTabs), `profile ${id} visibleTabs must be array`);
            strict_1.default.ok(profile.visibleTabs.length > 0, `profile ${id} must ship with non-empty visibleTabs`);
            strict_1.default.ok(profile.emphasis === 'detail' || profile.emphasis === 'summary', `profile ${id} emphasis must be 'detail' or 'summary'`);
            cases += 1;
        }
        // getAudienceViewProfile returns the same instance as the lookup table.
        strict_1.default.equal((0, audienceView_1.getAudienceViewProfile)('exec'), audienceView_1.AUDIENCE_VIEW_PROFILES.exec);
        cases += 1;
        // DEFAULT_AUDIENCE_VIEW is itself a valid id.
        strict_1.default.ok((0, audienceView_1.isAudienceView)(audienceView_1.DEFAULT_AUDIENCE_VIEW));
        cases += 1;
    }
    // === isAudienceView accepts known ids and rejects everything else ===
    {
        strict_1.default.equal((0, audienceView_1.isAudienceView)('ds'), true);
        strict_1.default.equal((0, audienceView_1.isAudienceView)('exec'), true);
        strict_1.default.equal((0, audienceView_1.isAudienceView)('ml'), true);
        strict_1.default.equal((0, audienceView_1.isAudienceView)(''), false);
        strict_1.default.equal((0, audienceView_1.isAudienceView)('analyst'), false);
        strict_1.default.equal((0, audienceView_1.isAudienceView)(0), false);
        strict_1.default.equal((0, audienceView_1.isAudienceView)(null), false);
        strict_1.default.equal((0, audienceView_1.isAudienceView)(undefined), false);
        cases += 8;
    }
    // === applyAudienceViewToCard: forceExpanded > forceCollapsed > emphasis mapping ===
    {
        // forceExpanded wins over emphasis 'summary' (Exec).
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({ forceExpanded: true }, audienceView_1.AUDIENCE_VIEW_PROFILES.exec), 'expanded');
        cases += 1;
        // forceCollapsed wins over emphasis 'detail' (DS).
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({ forceCollapsed: true }, audienceView_1.AUDIENCE_VIEW_PROFILES.ds), 'collapsed');
        cases += 1;
        // forceExpanded beats forceCollapsed when both are set.
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({ forceExpanded: true, forceCollapsed: true }, audienceView_1.AUDIENCE_VIEW_PROFILES.exec), 'expanded');
        cases += 1;
        // No overrides: emphasis 'detail' → 'expanded', 'summary' → 'collapsed'.
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({}, audienceView_1.AUDIENCE_VIEW_PROFILES.ds), 'expanded');
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({}, audienceView_1.AUDIENCE_VIEW_PROFILES.exec), 'collapsed');
        strict_1.default.equal((0, applyAudienceView_1.applyAudienceViewToCard)({}, audienceView_1.AUDIENCE_VIEW_PROFILES.ml), 'expanded');
        cases += 3;
        // emphasisToDisplayMode is the same mapping standalone.
        strict_1.default.equal((0, applyAudienceView_1.emphasisToDisplayMode)('detail'), 'expanded');
        strict_1.default.equal((0, applyAudienceView_1.emphasisToDisplayMode)('summary'), 'collapsed');
        cases += 2;
    }
    // === localStorage round-trip via reducer + loadAudienceView fallback on invalid value ===
    {
        const fakeStorage = createFakeStorage();
        (0, workspaceStore_1.__setAudienceViewStorageForTests)(fakeStorage);
        try {
            // setAudienceView writes to storage and updates state.
            workspaceStore_1.useWorkspaceStore.getState().setAudienceView('exec');
            strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().audienceView, 'exec');
            strict_1.default.equal(fakeStorage.store[workspaceStore_1.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY], 'exec');
            cases += 2;
            // loadAudienceView reads what we wrote.
            strict_1.default.equal((0, workspaceStore_1.loadAudienceView)(), 'exec');
            cases += 1;
            // Switching to another valid view persists again.
            workspaceStore_1.useWorkspaceStore.getState().setAudienceView('ml');
            strict_1.default.equal(fakeStorage.store[workspaceStore_1.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY], 'ml');
            strict_1.default.equal((0, workspaceStore_1.loadAudienceView)(), 'ml');
            cases += 2;
            // Invalid stored value falls back to DEFAULT_AUDIENCE_VIEW; bad input to setter is ignored.
            const corruptedStorage = createFakeStorage({
                [workspaceStore_1.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY]: 'analyst',
            });
            (0, workspaceStore_1.__setAudienceViewStorageForTests)(corruptedStorage);
            strict_1.default.equal((0, workspaceStore_1.loadAudienceView)(), audienceView_1.DEFAULT_AUDIENCE_VIEW);
            cases += 1;
            // Reducer ignores invalid input: state unchanged AND storage value not touched by setter.
            const cleanStorage = createFakeStorage();
            (0, workspaceStore_1.__setAudienceViewStorageForTests)(cleanStorage);
            const before = workspaceStore_1.useWorkspaceStore.getState().audienceView;
            workspaceStore_1.useWorkspaceStore.getState().setAudienceView('analyst');
            strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().audienceView, before);
            strict_1.default.equal(cleanStorage.store[workspaceStore_1.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY], undefined, 'invalid input must not be persisted by the reducer');
            cases += 2;
        }
        finally {
            (0, workspaceStore_1.__setAudienceViewStorageForTests)(null);
            workspaceStore_1.useWorkspaceStore.getState().reset();
        }
    }
    // === integration: applyAudienceViewToCard and resolveCardDisplayMode agree ===
    // With no per-card overrides and no userExpanded override, the per-card
    // emphasis adopter must converge on the same display mode the audience
    // profile would yield through applyAudienceViewToCard. This is the contract
    // that lets ResultCard swap to the precedence helper without changing the
    // observed default behavior under any audience.
    {
        for (const id of audienceView_1.AUDIENCE_VIEW_IDS) {
            const profile = audienceView_1.AUDIENCE_VIEW_PROFILES[id];
            const fromHelper = (0, applyAudienceView_1.applyAudienceViewToCard)({}, profile);
            const fromAdopter = (0, cardEmphasisAdopter_1.resolveCardDisplayMode)({}, id);
            strict_1.default.equal(fromAdopter, fromHelper, `default display mode must match for audience ${id}`);
            cases += 1;
        }
    }
    console.log(`[contract] PASS audience-view-switcher (${cases} cases)`);
}
run();
