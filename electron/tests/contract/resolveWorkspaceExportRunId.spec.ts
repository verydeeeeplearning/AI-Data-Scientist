import assert from 'node:assert/strict';
import { resolveWorkspaceExportRunId } from '../../src/renderer/application/workspace/resolveWorkspaceExportRunId';

function run(): void {
  const runtimeRuns = [
    { runId: 'run-old', sessionId: 'session-a', startedAt: 10 },
    { runId: 'run-current', sessionId: 'session-a', startedAt: 30 },
    { runId: 'run-other-session', sessionId: 'session-b', startedAt: 40 },
  ];

  assert.equal(
    resolveWorkspaceExportRunId({
      focus: {
        mode: 'detail',
        target: 'result',
        value: 'result-focused',
      },
      sessionId: 'session-a',
      selectedRunId: 'run-old',
      reasoningRunId: 'run-old',
      runtimeRuns,
      cards: [
        {
          resultId: 'result-focused',
          runId: 'run-current',
        },
      ],
      pinnedItems: [],
    }),
    'run-current',
  );

  assert.equal(
    resolveWorkspaceExportRunId({
      sessionId: 'session-a',
      selectedRunId: 'run-current',
      reasoningRunId: 'run-old',
      runtimeRuns,
      cards: [],
      pinnedItems: [],
    }),
    'run-current',
  );

  assert.equal(
    resolveWorkspaceExportRunId({
      sessionId: 'session-a',
      selectedRunId: 'run-missing',
      reasoningRunId: 'run-old',
      runtimeRuns,
      cards: [],
      pinnedItems: [],
    }),
    'run-old',
  );

  assert.equal(
    resolveWorkspaceExportRunId({
      sessionId: 'session-a',
      selectedRunId: null,
      reasoningRunId: null,
      runtimeRuns,
      cards: [],
      pinnedItems: [{ runId: 'run-old' }],
    }),
    'run-old',
  );

  assert.equal(
    resolveWorkspaceExportRunId({
      sessionId: 'session-a',
      selectedRunId: null,
      reasoningRunId: null,
      runtimeRuns,
      cards: [],
      pinnedItems: [],
    }),
    'run-current',
  );

  assert.equal(
    resolveWorkspaceExportRunId({
      sessionId: 'missing-session',
      selectedRunId: 'run-current',
      reasoningRunId: 'run-old',
      runtimeRuns,
      cards: [],
      pinnedItems: [{ runId: 'run-old' }],
    }),
    null,
  );

  console.log('[contract] PASS resolve-workspace-export-run-id (6 cases)');
}

run();
