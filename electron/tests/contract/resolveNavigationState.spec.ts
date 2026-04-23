import assert from 'node:assert/strict';

import {
  buildNavigationHash,
  normalizeNavigationPath,
  parseAreaSelection,
  resolveNavigationState,
} from '../../src/renderer/application/navigation/resolveNavigationState';

function run(): void {
  assert.equal(normalizeNavigationPath(''), '/mission');
  assert.equal(normalizeNavigationPath('#artifacts/files'), '/artifacts/files');
  assert.equal(buildNavigationHash('/runs'), '#/runs');

  {
    const selection = parseAreaSelection('/admin');
    assert.equal(selection.areaId, 'admin');
    assert.equal(selection.path, '/admin/models');
    assert.equal(selection.adminSectionId, 'models');
  }

  {
    const selection = parseAreaSelection('/memory/learning');
    assert.equal(selection.areaId, 'memory');
    assert.equal(selection.subPath, 'learning');
  }

  {
    const selection = parseAreaSelection('/governance/approvals/appr-77');
    assert.equal(selection.areaId, 'governance');
    assert.equal(selection.path, '/governance/approvals/appr-77');
    assert.equal(selection.subPath, 'approvals/appr-77');
  }

  {
    const state = resolveNavigationState('#/workflow');
    assert.equal(state.path, '/mission');
    assert.equal(state.selection.areaId, 'mission');
    assert.equal(state.migration.migratedFrom, '/workflow');
  }

  console.log('[contract] PASS resolve-navigation-state (7 cases)');
}

run();
