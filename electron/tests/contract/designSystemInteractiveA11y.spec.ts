import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement, type ReactElement } from 'react';

import {
  DrawerShell,
  Popover,
  Select,
  Tabs,
  Tooltip,
  type TabsItem,
} from '../../src/renderer/design-system/primitives';

function run(): void {
  // === Select generates a stable fallback control id when none is provided ===
  {
    const html = renderToStaticMarkup(
      createElement(Select, {
        label: 'Sort',
        options: [
          { value: 'newest', label: 'Newest first' },
          { value: 'oldest', label: 'Oldest first' },
        ],
        value: 'newest',
        onChange: () => undefined,
      }),
    );

    const labelMatch = html.match(/<label for="(ds-select-[^"]+)"/);
    const selectMatch = html.match(/<select id="(ds-select-[^"]+)"/);

    assert.ok(labelMatch, 'expected select label to reference generated id');
    assert.ok(selectMatch, 'expected select element to expose generated id');
    assert.equal(labelMatch?.[1], selectMatch?.[1]);
  }

  // === DrawerShell exposes dialog semantics and dismiss label ===
  {
    const html = renderToStaticMarkup(
      createElement(
        DrawerShell,
        {
          open: true,
          title: 'Inspector',
          description: 'Inspect run metadata.',
          dismissLabel: 'Close inspector',
          onDismiss: () => undefined,
        },
        createElement('div', null, 'Body'),
      ),
    );

    assert.match(html, /role="dialog"/);
    assert.match(html, /aria-modal="true"/);
    assert.match(html, /aria-labelledby="ds-drawer-[^"]+-title"/);
    assert.match(html, /aria-describedby="ds-drawer-[^"]+-description"/);
    assert.match(html, /aria-label="Close inspector"/);
  }

  // === Tabs render tablist, selected tab, and panel wiring ===
  {
    const items: TabsItem[] = [
      { value: 'summary', label: 'Summary', content: 'Summary panel' },
      { value: 'details', label: 'Details', content: 'Details panel' },
    ];

    const html = renderToStaticMarkup(
      createElement(Tabs, {
        value: 'details',
        onValueChange: () => undefined,
        items,
      }),
    );

    assert.match(html, /role="tablist"/);
    assert.match(html, /role="tab"[^>]*aria-selected="false"/);
    assert.match(html, /role="tab"[^>]*aria-selected="true"/);
    assert.match(html, /role="tabpanel"/);
    assert.match(html, /aria-controls="ds-tabs-[^"]+-panel-details"/);
    assert.match(html, /aria-labelledby="ds-tabs-[^"]+-tab-details"/);
  }

  // === Tooltip wires describedby and tooltip semantics when open ===
  {
    const tooltipTrigger = createElement('button', { type: 'button' }, 'Trigger') as ReactElement;
    const html = renderToStaticMarkup(
      createElement(Tooltip, {
        content: 'Open workflow settings',
        open: true,
        delayMs: 0,
        children: tooltipTrigger,
      }),
    );

    assert.match(html, /role="tooltip"/);
    assert.match(html, /id="ds-tooltip-[^"]+"/);
    assert.match(html, /aria-describedby="ds-tooltip-[^"]+"/);
  }

  // === Popover exposes dialog trigger wiring and panel semantics when open ===
  {
    const popoverTrigger = createElement('button', { type: 'button' }, 'Open') as ReactElement;
    const html = renderToStaticMarkup(
      createElement(Popover, {
        open: true,
        title: 'Respond',
        description: 'Provide an approval response.',
        trigger: popoverTrigger,
        children: createElement('div', null, 'Body'),
      }),
    );

    assert.match(html, /aria-haspopup="dialog"/);
    assert.match(html, /aria-expanded="true"/);
    assert.match(html, /aria-controls="ds-popover-[^"]+"/);
    assert.match(html, /role="dialog"/);
    assert.match(html, /aria-modal="false"/);
    assert.match(html, /aria-labelledby="ds-popover-[^"]+-title"/);
    assert.match(html, /aria-describedby="ds-popover-[^"]+-description"/);
  }

  console.log('[contract] PASS design-system-interactive-a11y (5 cases)');
}

run();
