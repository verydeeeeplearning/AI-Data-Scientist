import assert from 'node:assert/strict';

import { applyDensityScale } from '../../src/renderer/application/layout/applyDensityScale';
import {
  DEFAULT_DENSITY_MODE,
  DENSITY_MODES,
  getDensityScale,
  isDensityMode,
} from '../../src/renderer/domain/layout/density';

function run(): void {
  // domain invariants
  assert.deepEqual([...DENSITY_MODES].sort(), ['comfortable', 'compact', 'spacious']);
  assert.equal(DEFAULT_DENSITY_MODE, 'comfortable');
  assert.equal(isDensityMode('compact'), true);
  assert.equal(isDensityMode('cozy'), false);
  assert.equal(isDensityMode(undefined), false);

  // scale table
  assert.deepEqual(getDensityScale('compact'), { spacing: 0.75, font: 0.9 });
  assert.deepEqual(getDensityScale('comfortable'), { spacing: 1, font: 1 });
  assert.deepEqual(getDensityScale('spacious'), { spacing: 1.25, font: 1.1 });

  // application: comfortable mode preserves base values
  const comfortable = applyDensityScale('comfortable');
  assert.equal(comfortable['--ds-space-4'], '1rem');
  assert.equal(comfortable['--ds-font-size-md'], '1rem');
  assert.equal(comfortable['--ds-space-1'], '0.25rem');

  // application: compact mode shrinks both axes
  const compact = applyDensityScale('compact');
  assert.equal(compact['--ds-space-4'], '0.75rem');
  assert.equal(compact['--ds-font-size-md'], '0.9rem');

  // application: spacious mode enlarges both axes
  const spacious = applyDensityScale('spacious');
  assert.equal(spacious['--ds-space-4'], '1.25rem');
  assert.equal(spacious['--ds-font-size-md'], '1.1rem');

  // application emits both spacing and font variables in a single call
  const overrideKeys = Object.keys(applyDensityScale('compact'));
  assert.ok(overrideKeys.some((key) => key.startsWith('--ds-space-')));
  assert.ok(overrideKeys.some((key) => key.startsWith('--ds-font-size-')));

  // pure function: same input → same output
  const a = applyDensityScale('spacious');
  const b = applyDensityScale('spacious');
  assert.deepEqual(a, b);

  console.log('[contract] PASS apply-density-scale (8 cases)');
}

run();
