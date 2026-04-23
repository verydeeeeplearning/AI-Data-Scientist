import assert from 'node:assert/strict';
import {
  buildEvidenceWorkspacePath,
  normalizeArtifactsView,
  normalizeEvidenceWorkspaceFocus,
  normalizeEvidenceWorkspaceTab,
  parseEvidenceWorkspaceRoute,
} from '../../src/renderer/application/workspace/workspaceRoute';

function run(): void {
  assert.equal(normalizeArtifactsView({ subPath: 'workspace/charts' }), 'workspace');
  assert.equal(normalizeArtifactsView({ subPath: 'workspace' }), 'workspace');
  assert.equal(normalizeArtifactsView({ subPath: 'unknown' }), 'files');

  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/files' }), 'files');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/highlight/card/card-1' }), 'summary');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/not-a-tab' }), 'summary');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'files' }), 'summary');
  assert.equal(normalizeEvidenceWorkspaceFocus({ subPath: 'workspace/files' }), null);
  assert.deepEqual(
    normalizeEvidenceWorkspaceFocus({ subPath: 'workspace/highlight/card/card-1' }),
    {
      mode: 'highlight',
      target: 'card',
      value: 'card-1',
    },
  );
  assert.deepEqual(
    parseEvidenceWorkspaceRoute({ subPath: 'workspace/export/detail/result/result%2Fwith%2Fslash' }),
    {
      tab: 'export',
      focus: {
        mode: 'detail',
        target: 'result',
        value: 'result/with/slash',
      },
    },
  );
  assert.deepEqual(
    parseEvidenceWorkspaceRoute({ subPath: 'workspace/detail/message/msg-7' }),
    {
      tab: 'summary',
      focus: {
        mode: 'detail',
        target: 'message',
        value: 'msg-7',
      },
    },
  );
  assert.equal(
    normalizeEvidenceWorkspaceFocus({ subPath: 'workspace/summary/highlight/unknown/card-1' }),
    null,
  );

  assert.equal(buildEvidenceWorkspacePath('summary'), '/artifacts/workspace');
  assert.equal(buildEvidenceWorkspacePath('export'), '/artifacts/workspace/export');
  assert.equal(
    buildEvidenceWorkspacePath('summary', {
      mode: 'detail',
      target: 'card',
      value: 'card-1',
    }),
    '/artifacts/workspace/detail/card/card-1',
  );
  assert.equal(
    buildEvidenceWorkspacePath('tables', {
      mode: 'highlight',
      target: 'result',
      value: 'result/with/slash',
    }),
    '/artifacts/workspace/tables/highlight/result/result%2Fwith%2Fslash',
  );

  console.log('[contract] PASS workspace-route (14 cases)');
}

run();
