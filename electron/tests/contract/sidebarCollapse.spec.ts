import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { FolderOpen } from 'lucide-react';

import {
  SIDEBAR_BREAKPOINT,
  createInitialSidebarLayoutState,
  resolveResponsiveSidebarLayoutState,
  toggleSidebarLayoutState,
  parseStoredSidebarLayoutState,
  serializeSidebarLayoutState,
} from '../../src/renderer/utils/sidebarLayout';
import { SidebarItem } from '../../src/renderer/components/sidebar/SidebarItem';
import { matchesShortcut } from '../../src/renderer/utils/keyboardShortcut';

function run(): void {
  {
    const state = createInitialSidebarLayoutState(1280);
    assert.equal(state.collapsed, false);
    assert.equal(state.collapsedByUser, false);
  }

  {
    const state = createInitialSidebarLayoutState(SIDEBAR_BREAKPOINT - 1);
    assert.equal(state.collapsed, true);
    assert.equal(state.collapsedByUser, false);
  }

  {
    const state = toggleSidebarLayoutState({ collapsed: false, collapsedByUser: false });
    assert.deepEqual(state, { collapsed: true, collapsedByUser: true });
  }

  {
    const state = resolveResponsiveSidebarLayoutState(
      { collapsed: false, collapsedByUser: false },
      SIDEBAR_BREAKPOINT - 1,
    );
    assert.deepEqual(state, { collapsed: true, collapsedByUser: false });
  }

  {
    const state = resolveResponsiveSidebarLayoutState(
      { collapsed: false, collapsedByUser: true },
      SIDEBAR_BREAKPOINT - 1,
    );
    assert.deepEqual(state, { collapsed: false, collapsedByUser: true });
  }

  {
    const encoded = serializeSidebarLayoutState({ collapsed: true, collapsedByUser: true });
    const parsed = parseStoredSidebarLayoutState(encoded);
    assert.deepEqual(parsed, { collapsed: true, collapsedByUser: true });
  }

  {
    assert.equal(parseStoredSidebarLayoutState('{"collapsed":true}'), null);
    assert.equal(parseStoredSidebarLayoutState('not-json'), null);
  }

  {
    const event = { key: '\\', ctrlKey: true, metaKey: false, altKey: false, shiftKey: false };
    assert.equal(matchesShortcut(event, 'ctrl+\\'), true);
    assert.equal(matchesShortcut(event, 'ctrl+m'), false);
  }

  {
    const event = { key: '\\', ctrlKey: false, metaKey: true, altKey: false, shiftKey: false };
    assert.equal(matchesShortcut(event, 'meta+\\'), true);
  }

  {
    const html = renderToStaticMarkup(
      createElement(SidebarItem, {
        icon: FolderOpen,
        label: 'Files',
        collapsed: true,
        onClick: () => undefined,
      }),
    );

    assert.match(html, /data-state="closed"/);
    assert.match(html, /aria-label="Files"/);
    assert.doesNotMatch(html, /title="Files"/);
  }

  console.log('[contract] PASS sidebar-collapse (10 cases)');
}

run();
