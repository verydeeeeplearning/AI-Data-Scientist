import assert from 'node:assert/strict';

import {
  POLICY_STUDIO_PRESETS,
  buildLegacyModeMigrationPreview,
} from '../../src/renderer/components/settings/policyStudioCatalog';

function run(): void {
  assert.equal(POLICY_STUDIO_PRESETS.length, 4);
  assert.deepEqual(
    POLICY_STUDIO_PRESETS.map((preset) => preset.id),
    ['delegate-peer', 'executive-review', 'audit-guard', 'mentor-walkthrough'],
  );
  assert.deepEqual(
    POLICY_STUDIO_PRESETS.find((preset) => preset.id === 'executive-review'),
    {
      id: 'executive-review',
      label: 'settings.policyStudio.preset.executiveReview.label',
      authority: 'supervised',
      audience: 'executive',
      summary: 'settings.policyStudio.preset.executiveReview.summary',
    },
  );

  const exact = buildLegacyModeMigrationPreview('supervised');
  assert.equal(exact.legacyMode, 'supervised');
  assert.equal(exact.exactMatch, true);
  assert.equal(exact.authority, 'supervised');
  assert.equal(exact.audience, 'peer_ds');

  const approximate = buildLegacyModeMigrationPreview('step-by-step');
  assert.equal(approximate.legacyMode, 'step-by-step');
  assert.equal(approximate.exactMatch, false);
  assert.equal(approximate.authority, 'supervised');
  assert.equal(approximate.audience, 'junior_mentor');

  console.log('[contract] PASS policy-studio catalog');
}

run();
