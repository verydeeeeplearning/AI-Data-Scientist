import assert from 'node:assert/strict';
import { listRunExportArtifacts } from '../../src/renderer/application/workspace/listRunExportArtifacts';
import type { ListRunExportArtifactsPort } from '../../src/renderer/application/workspace/listRunExportArtifactsPort';

async function run(): Promise<void> {
  const portCalls: string[] = [];
  const port: ListRunExportArtifactsPort = async ({ runId }) => {
    portCalls.push(runId);
    return {
      runId,
      sessionId: 'session-1',
      files: [
        {
          name: 'report.md',
          path: 'report.md',
          size: 256,
          type: 'md',
          modifiedAt: 1_000,
        },
      ],
      exportCandidates: [
        {
          name: 'report.md',
          path: 'report.md',
          type: 'md',
          formats: ['docx', 'html', 'pdf'],
        },
      ],
    };
  };

  const result = await listRunExportArtifacts(port, { runId: '  run-123  ' });

  assert.equal(portCalls[0], 'run-123');
  assert.equal(result.sessionId, 'session-1');
  assert.equal(result.exportCandidates[0]?.path, 'report.md');
  assert.deepEqual(result.exportCandidates[0]?.formats, ['docx', 'html', 'pdf']);

  await assert.rejects(
    () => listRunExportArtifacts(port, { runId: '   ' }),
    /runId is required/,
  );

  console.log('[contract] PASS list-run-export-artifacts (5 cases)');
}

void run();
