import assert from 'node:assert/strict';

import {
  buildThemeTokenMap,
  getNextTheme,
  loadStoredTheme,
} from '../../src/renderer/design-system/themes';

function run(): void {
  {
    const theme = loadStoredTheme(
      {
        getItem: () => 'high-contrast',
      },
    );
    assert.equal(theme, 'high-contrast');
  }

  {
    const theme = loadStoredTheme(
      {
        getItem: () => null,
      },
      () => ({ matches: true } as MediaQueryList),
    );
    assert.equal(theme, 'light');
  }

  {
    const dark = buildThemeTokenMap('dark');
    const light = buildThemeTokenMap('light');
    assert.ok(dark['--ds-space-4']);
    assert.ok(dark['--ds-font-size-sm']);
    assert.ok(dark['--ds-color-bg']);
    assert.notEqual(dark['--ds-color-bg'], light['--ds-color-bg']);
  }

  {
    assert.equal(getNextTheme('dark'), 'light');
    assert.equal(getNextTheme('light'), 'high-contrast');
    assert.equal(getNextTheme('high-contrast'), 'dark');
  }

  console.log('[contract] PASS design-system-theme (4 cases)');
}

run();

