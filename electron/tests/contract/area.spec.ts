import assert from 'node:assert/strict';

import {
  ADMIN_SECTION_DESCRIPTORS,
  AREA_DESCRIPTORS,
  DEFAULT_AREA_PATH,
  getAdminSectionDescriptor,
  getAreaDescriptor,
  isAdminSectionId,
  isAreaId,
} from '../../src/renderer/domain/navigation/area';

function run(): void {
  assert.equal(DEFAULT_AREA_PATH, '/mission');
  assert.equal(AREA_DESCRIPTORS.length, 6);
  assert.equal(ADMIN_SECTION_DESCRIPTORS.length, 4);

  assert.equal(isAreaId('mission'), true);
  assert.equal(isAreaId('unknown'), false);
  assert.equal(isAdminSectionId('models'), true);
  assert.equal(isAdminSectionId('review'), false);

  assert.equal(getAreaDescriptor('artifacts').defaultPath, '/artifacts/files');
  assert.equal(getAreaDescriptor('admin').shortcut, 'mod+,');
  assert.equal(getAdminSectionDescriptor('connectors').defaultPath, '/admin/connectors');

  console.log('[contract] PASS area (8 cases)');
}

run();
