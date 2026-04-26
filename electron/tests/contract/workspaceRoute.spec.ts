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

  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/files' }), 'overview');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/highlight/card/card-1' }), 'overview');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'workspace/not-a-tab' }), 'overview');
  assert.equal(normalizeEvidenceWorkspaceTab({ subPath: 'files' }), 'overview');
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
      tab: 'overview',
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

  assert.equal(buildEvidenceWorkspacePath('overview'), '/artifacts/workspace/overview');
  assert.equal(buildEvidenceWorkspacePath('export'), '/artifacts/workspace/export');
  assert.equal(
    buildEvidenceWorkspacePath('overview', {
      mode: 'detail',
      target: 'card',
      value: 'card-1',
    }),
    '/artifacts/workspace/overview/detail/card/card-1',
  );

  console.log('[contract] PASS workspace-route (13 cases)');
}

run();
