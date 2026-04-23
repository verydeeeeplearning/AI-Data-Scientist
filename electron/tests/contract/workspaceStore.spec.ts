import assert from 'node:assert/strict';
import type { FileEntry, PlotEntry } from '../../src/renderer/stores/filesStore';
import type { WorkspacePinnedCardInput } from '../../src/renderer/stores/workspaceStore';
import { __test, useWorkspaceStore } from '../../src/renderer/stores/workspaceStore';

function run(): void {
  const files: FileEntry[] = [
    {
      name: 'model_report.md',
      path: 'reports/model_report.md',
      size: 2_048,
      type: 'md',
      modifiedAt: 2_000,
    },
    {
      name: 'metrics.csv',
      path: 'tables/metrics.csv',
      size: 4_096,
      type: 'csv',
      modifiedAt: 3_000,
    },
    {
      name: 'roc_curve.png',
      path: 'plots/roc_curve.png',
      size: 8_192,
      type: 'png',
      modifiedAt: 1_000,
    },
  ];
  const plots: PlotEntry[] = [
    {
      name: 'roc_curve.png',
      path: 'plots/roc_curve.png',
      size: 8_192,
      addedAt: 1_500,
      modifiedAt: 1_000,
    },
  ];
  const pinnedCards: WorkspacePinnedCardInput[] = [
    {
      cardId: 'card-1',
      resultId: 'result-1',
      type: 'insight',
      createdAt: 1_000,
      source: {
        messageId: 'msg-assistant-1',
        runId: 'run-1',
      },
      pinned: true,
      archived: false,
      title: 'Retention drivers',
      summary: 'Top cohorts show stable retention after week four.',
    },
    {
      cardId: 'card-2',
      resultId: 'result-2',
      type: 'artifact',
      createdAt: 2_000,
      source: {
        messageId: 'msg-assistant-2',
        runId: 'run-1',
        toolCallId: 'tool-7',
      },
      pinned: true,
      archived: false,
      path: 'reports/roc_curve.png',
    },
    {
      cardId: 'card-3',
      resultId: 'result-3',
      type: 'risk',
      createdAt: 3_000,
      source: {
        messageId: 'msg-assistant-3',
        runId: 'run-2',
      },
      pinned: false,
      archived: false,
      title: 'Do not project',
    },
  ];

  const pinnedProjection = __test.buildWorkspacePinnedProjection({
    items: pinnedCards,
    fallbackCount: 5,
  });

  assert.equal(pinnedProjection.status, 'ready');
  assert.equal(pinnedProjection.count, 2);
  assert.equal(pinnedProjection.items[0]?.cardId, 'card-2');
  assert.equal(pinnedProjection.items[0]?.artifactPath, 'reports/roc_curve.png');
  assert.equal(pinnedProjection.items[1]?.summary, 'Top cohorts show stable retention after week four.');
  assert.equal(
    __test.findWorkspacePinnedItem(pinnedProjection.items, 'result', 'result-2')?.cardId,
    'card-2',
  );
  assert.equal(
    __test.matchesWorkspacePinnedItem(pinnedProjection.items[1], 'message', 'msg-assistant-1'),
    true,
  );

  const countOnlyProjection = __test.buildWorkspacePinnedProjection({
    items: [],
    fallbackCount: 2,
  });

  assert.equal(countOnlyProjection.status, 'count_only');
  assert.equal(countOnlyProjection.count, 2);

  const readModel = __test.buildWorkspaceReadModel(
    { files, plots, loading: false },
    { items: pinnedCards, fallbackCount: 0 },
  );

  assert.equal(readModel.status, 'ready');
  assert.equal(readModel.nonPlotFileCount, 2);
  assert.equal(readModel.plotCount, 1);
  assert.equal(readModel.tableCount, 1);
  assert.equal(readModel.pinnedCardCount, 2);
  assert.equal(readModel.pinnedProjectionStatus, 'ready');
  assert.equal(readModel.exportCandidateCount, 3);
  assert.deepEqual(
    readModel.exportCandidates.map((candidate) => ({
      id: candidate.id,
      name: candidate.name,
      path: candidate.path,
      type: candidate.type,
      formats: [...candidate.formats],
      sourceKind: candidate.sourceKind,
    })),
    [
      {
        id: 'plots/roc_curve.png',
        name: 'roc_curve.png',
        path: 'plots/roc_curve.png',
        type: 'png',
        formats: ['png'],
        sourceKind: 'file',
      },
      {
        id: 'reports/model_report.md',
        name: 'model_report.md',
        path: 'reports/model_report.md',
        type: 'md',
        formats: ['docx', 'html', 'pdf'],
        sourceKind: 'file',
      },
      {
        id: 'tables/metrics.csv',
        name: 'metrics.csv',
        path: 'tables/metrics.csv',
        type: 'csv',
        formats: ['html', 'xlsx'],
        sourceKind: 'file',
      },
    ],
  );
  assert.equal(readModel.sections.find((section) => section.id === 'summary')?.itemCount, 3);
  assert.equal(readModel.recentFiles[0]?.path, 'tables/metrics.csv');
  assert.equal(readModel.pinnedItems[0]?.cardId, 'card-2');

  useWorkspaceStore.getState().reset();
  useWorkspaceStore.getState().setPinnedCardCount(2);

  assert.equal(useWorkspaceStore.getState().readModel.pinnedProjectionStatus, 'count_only');
  assert.equal(useWorkspaceStore.getState().readModel.pinnedCardCount, 2);

  useWorkspaceStore.getState().syncPinnedItems([pinnedCards[0]]);

  assert.equal(useWorkspaceStore.getState().readModel.pinnedProjectionStatus, 'ready');
  assert.equal(useWorkspaceStore.getState().readModel.pinnedCardCount, 1);
  assert.equal(useWorkspaceStore.getState().readModel.pinnedItems[0]?.cardId, 'card-1');

  useWorkspaceStore.getState().syncFromArtifacts({
    files: [],
    plots: [],
    loading: true,
  });

  assert.equal(useWorkspaceStore.getState().readModel.status, 'loading');

  useWorkspaceStore.getState().syncFromArtifacts({
    files: [
      {
        name: 'summary.html',
        path: 'reports/summary.html',
        size: 512,
        type: 'html',
        modifiedAt: 5_000,
      },
    ],
    plots: [],
    loading: false,
  });

  assert.equal(useWorkspaceStore.getState().readModel.status, 'ready');
  assert.equal(useWorkspaceStore.getState().readModel.exportCandidateCount, 1);
  assert.deepEqual(useWorkspaceStore.getState().readModel.exportCandidates.map((candidate) => ({
    id: candidate.id,
    name: candidate.name,
    path: candidate.path,
    type: candidate.type,
    formats: [...candidate.formats],
    sourceKind: candidate.sourceKind,
  })), [
    {
      id: 'reports/summary.html',
      name: 'summary.html',
      path: 'reports/summary.html',
      type: 'html',
      formats: ['html', 'pdf'],
      sourceKind: 'file',
    },
  ]);
  assert.equal(useWorkspaceStore.getState().readModel.pinnedCardCount, 1);

  useWorkspaceStore.getState().reset();

  console.log('[contract] PASS workspace-store (20 cases)');
}

run();
