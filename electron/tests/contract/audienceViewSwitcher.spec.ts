import assert from 'node:assert/strict';

import {
  AUDIENCE_VIEW_IDS,
  AUDIENCE_VIEW_PROFILES,
  DEFAULT_AUDIENCE_VIEW,
  getAudienceViewProfile,
  isAudienceView,
  type AudienceView,
  type AudienceViewProfile,
  type EvidenceTabId,
} from '../../src/renderer/domain/workspace/audienceView';
import {
  applyAudienceViewToCard,
  applyAudienceViewToTabs,
  emphasisToDisplayMode,
  resolveActiveTabForAudience,
} from '../../src/renderer/application/workspace/applyAudienceView';
import { resolveCardDisplayMode } from '../../src/renderer/application/workspace/cardEmphasisAdopter';
import {
  WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY,
  __setAudienceViewStorageForTests,
  loadAudienceView,
  useWorkspaceStore,
  type AudienceViewStorageLike,
} from '../../src/renderer/stores/workspaceStore';

const ALL_TABS: ReadonlyArray<EvidenceTabId> = ['overview', 'export'];

function createFakeStorage(initial: Record<string, string> = {}): AudienceViewStorageLike & {
  store: Record<string, string>;
} {
  const store: Record<string, string> = { ...initial };
  return {
    store,
    getItem(key: string): string | null {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key: string, value: string): void {
      store[key] = value;
    },
  };
}

function run(): void {
  let cases = 0;

  // === applyAudienceViewToTabs returns the correct visible-tab subset for each profile ===
  {
    const dsTabs = applyAudienceViewToTabs(ALL_TABS, AUDIENCE_VIEW_PROFILES.ds);
    assert.deepEqual(dsTabs, ['overview', 'export']);
    cases += 1;

    const execTabs = applyAudienceViewToTabs(ALL_TABS, AUDIENCE_VIEW_PROFILES.exec);
    assert.deepEqual(execTabs, ['overview', 'export']);
    cases += 1;

    const mlTabs = applyAudienceViewToTabs(ALL_TABS, AUDIENCE_VIEW_PROFILES.ml);
    assert.deepEqual(mlTabs, ['overview', 'export']);
    cases += 1;

    // Order is preserved: feed a permuted input and expect the same permutation back, filtered.
    const permuted: ReadonlyArray<EvidenceTabId> = ['export', 'overview'];
    const execPermuted = applyAudienceViewToTabs(permuted, AUDIENCE_VIEW_PROFILES.exec);
    assert.deepEqual(execPermuted, ['export', 'overview']);
    cases += 1;
  }

  // === resolveActiveTabForAudience: in-profile vs filtered-out vs empty ===
  {
    // In-profile active tab is preserved
    assert.equal(
      resolveActiveTabForAudience('export', ALL_TABS, AUDIENCE_VIEW_PROFILES.exec),
      'export',
    );
    cases += 1;

    // Active tab filtered out by a constrained profile falls back to first visible (`export`).
    const exportOnlyProfile: AudienceViewProfile = {
      id: 'exec',
      label: 'Export only (test)',
      description: 'Synthetic profile with a constrained tab set.',
      visibleTabs: ['export'],
      emphasis: 'summary',
    };
    assert.equal(
      resolveActiveTabForAudience('overview', ALL_TABS, exportOnlyProfile),
      'export',
    );
    cases += 1;

    // Active tab filtered out, fallback respects the order of `allTabs` (not profile order).
    const reordered: ReadonlyArray<EvidenceTabId> = ['export', 'overview'];
    assert.equal(
      resolveActiveTabForAudience('overview', reordered, exportOnlyProfile),
      'export',
    );
    cases += 1;

    // Empty visible-tab set returns null. Construct a synthetic profile to hit that branch
    // (shipped profiles all have non-empty visibleTabs).
    const emptyProfile: AudienceViewProfile = {
      id: 'ds',
      label: 'Empty (test only)',
      description: 'Synthetic profile with no visible tabs.',
      visibleTabs: [],
      emphasis: 'detail',
    };
    assert.equal(
      resolveActiveTabForAudience('overview', ALL_TABS, emptyProfile),
      null,
    );
    cases += 1;
  }

  // === AUDIENCE_VIEW_PROFILES integrity ===
  {
    assert.deepEqual([...AUDIENCE_VIEW_IDS], ['ds', 'exec', 'ml']);
    cases += 1;

    for (const id of AUDIENCE_VIEW_IDS) {
      const profile = AUDIENCE_VIEW_PROFILES[id];
      assert.ok(profile, `profile must exist for id ${id}`);
      assert.equal(profile.id, id, `profile.id must match key ${id}`);
      assert.equal(typeof profile.label, 'string');
      assert.ok(profile.label.length > 0, `profile ${id} must have a non-empty label`);
      assert.equal(typeof profile.description, 'string');
      assert.ok(profile.description.length > 0, `profile ${id} must have a non-empty description`);
      assert.ok(Array.isArray(profile.visibleTabs), `profile ${id} visibleTabs must be array`);
      assert.ok(profile.visibleTabs.length > 0, `profile ${id} must ship with non-empty visibleTabs`);
      assert.ok(
        profile.emphasis === 'detail' || profile.emphasis === 'summary',
        `profile ${id} emphasis must be 'detail' or 'summary'`,
      );
      cases += 1;
    }

    // getAudienceViewProfile returns the same instance as the lookup table.
    assert.equal(getAudienceViewProfile('exec'), AUDIENCE_VIEW_PROFILES.exec);
    cases += 1;

    // DEFAULT_AUDIENCE_VIEW is itself a valid id.
    assert.ok(isAudienceView(DEFAULT_AUDIENCE_VIEW));
    cases += 1;
  }

  // === isAudienceView accepts known ids and rejects everything else ===
  {
    assert.equal(isAudienceView('ds'), true);
    assert.equal(isAudienceView('exec'), true);
    assert.equal(isAudienceView('ml'), true);
    assert.equal(isAudienceView(''), false);
    assert.equal(isAudienceView('analyst'), false);
    assert.equal(isAudienceView(0), false);
    assert.equal(isAudienceView(null), false);
    assert.equal(isAudienceView(undefined), false);
    cases += 8;
  }

  // === applyAudienceViewToCard: forceExpanded > forceCollapsed > emphasis mapping ===
  {
    // forceExpanded wins over emphasis 'summary' (Exec).
    assert.equal(
      applyAudienceViewToCard({ forceExpanded: true }, AUDIENCE_VIEW_PROFILES.exec),
      'expanded',
    );
    cases += 1;

    // forceCollapsed wins over emphasis 'detail' (DS).
    assert.equal(
      applyAudienceViewToCard({ forceCollapsed: true }, AUDIENCE_VIEW_PROFILES.ds),
      'collapsed',
    );
    cases += 1;

    // forceExpanded beats forceCollapsed when both are set.
    assert.equal(
      applyAudienceViewToCard(
        { forceExpanded: true, forceCollapsed: true },
        AUDIENCE_VIEW_PROFILES.exec,
      ),
      'expanded',
    );
    cases += 1;

    // No overrides: emphasis 'detail' → 'expanded', 'summary' → 'collapsed'.
    assert.equal(applyAudienceViewToCard({}, AUDIENCE_VIEW_PROFILES.ds), 'expanded');
    assert.equal(applyAudienceViewToCard({}, AUDIENCE_VIEW_PROFILES.exec), 'collapsed');
    assert.equal(applyAudienceViewToCard({}, AUDIENCE_VIEW_PROFILES.ml), 'expanded');
    cases += 3;

    // emphasisToDisplayMode is the same mapping standalone.
    assert.equal(emphasisToDisplayMode('detail'), 'expanded');
    assert.equal(emphasisToDisplayMode('summary'), 'collapsed');
    cases += 2;
  }

  // === localStorage round-trip via reducer + loadAudienceView fallback on invalid value ===
  {
    const fakeStorage = createFakeStorage();
    __setAudienceViewStorageForTests(fakeStorage);
    try {
      // setAudienceView writes to storage and updates state.
      useWorkspaceStore.getState().setAudienceView('exec');
      assert.equal(useWorkspaceStore.getState().audienceView, 'exec');
      assert.equal(fakeStorage.store[WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY], 'exec');
      cases += 2;

      // loadAudienceView reads what we wrote.
      assert.equal(loadAudienceView(), 'exec');
      cases += 1;

      // Switching to another valid view persists again.
      useWorkspaceStore.getState().setAudienceView('ml');
      assert.equal(fakeStorage.store[WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY], 'ml');
      assert.equal(loadAudienceView(), 'ml');
      cases += 2;

      // Invalid stored value falls back to DEFAULT_AUDIENCE_VIEW; bad input to setter is ignored.
      const corruptedStorage = createFakeStorage({
        [WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY]: 'analyst',
      });
      __setAudienceViewStorageForTests(corruptedStorage);
      assert.equal(loadAudienceView(), DEFAULT_AUDIENCE_VIEW);
      cases += 1;

      // Reducer ignores invalid input: state unchanged AND storage value not touched by setter.
      const cleanStorage = createFakeStorage();
      __setAudienceViewStorageForTests(cleanStorage);
      const before = useWorkspaceStore.getState().audienceView;
      useWorkspaceStore.getState().setAudienceView('analyst' as unknown as AudienceView);
      assert.equal(useWorkspaceStore.getState().audienceView, before);
      assert.equal(
        cleanStorage.store[WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY],
        undefined,
        'invalid input must not be persisted by the reducer',
      );
      cases += 2;
    } finally {
      __setAudienceViewStorageForTests(null);
      useWorkspaceStore.getState().reset();
    }
  }

  // === integration: applyAudienceViewToCard and resolveCardDisplayMode agree ===
  // With no per-card overrides and no userExpanded override, the per-card
  // emphasis adopter must converge on the same display mode the audience
  // profile would yield through applyAudienceViewToCard. This is the contract
  // that lets ResultCard swap to the precedence helper without changing the
  // observed default behavior under any audience.
  {
    for (const id of AUDIENCE_VIEW_IDS) {
      const profile = AUDIENCE_VIEW_PROFILES[id];
      const fromHelper = applyAudienceViewToCard({}, profile);
      const fromAdopter = resolveCardDisplayMode({}, id);
      assert.equal(
        fromAdopter,
        fromHelper,
        `default display mode must match for audience ${id}`,
      );
      cases += 1;
    }
  }

  console.log(`[contract] PASS audience-view-switcher (${cases} cases)`);
}

run();
