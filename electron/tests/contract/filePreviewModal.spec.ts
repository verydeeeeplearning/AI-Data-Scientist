import assert from 'node:assert/strict';

import {
  buildPreviewRequest,
  clampHeaderRow,
} from '../../src/renderer/components/sidebar/FilePreviewModal';

function run(): void {
  assert.equal(clampHeaderRow('3'), 3);
  assert.equal(clampHeaderRow('0'), 1);
  assert.equal(clampHeaderRow('99'), 50);
  assert.equal(clampHeaderRow('abc'), 1);

  assert.deepEqual(
    buildPreviewRequest('workspace/data.csv', 2, null),
    {
      path: 'workspace/data.csv',
      rows: 50,
      headerRow: 2,
    },
  );

  assert.deepEqual(
    buildPreviewRequest('workspace/book.xlsx', 4, 'Revenue'),
    {
      path: 'workspace/book.xlsx',
      rows: 50,
      headerRow: 4,
      sheetName: 'Revenue',
    },
  );

  console.log('[contract] PASS file-preview-modal (2 cases)');
}

run();
