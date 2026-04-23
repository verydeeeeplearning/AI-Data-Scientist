import assert from 'node:assert/strict';

import { migrateLegacyRoute } from '../../src/renderer/application/navigation/migrateLegacyRoute';

function run(): void {
  {
    const result = migrateLegacyRoute('/workflow');
    assert.equal(result.newPath, '/mission');
    assert.equal(result.migratedFrom, '/workflow');
    assert.equal(result.showMigrationToast, true);
  }

  {
    const result = migrateLegacyRoute('/files');
    assert.equal(result.newPath, '/artifacts/files');
    assert.equal(result.showMigrationToast, true);
  }

  {
    const result = migrateLegacyRoute('/settings');
    assert.equal(result.newPath, '/admin/settings');
  }

  {
    const result = migrateLegacyRoute('/mission');
    assert.equal(result.newPath, '/mission');
    assert.equal(result.showMigrationToast, false);
  }

  console.log('[contract] PASS migrate-legacy-route (4 cases)');
}

run();
