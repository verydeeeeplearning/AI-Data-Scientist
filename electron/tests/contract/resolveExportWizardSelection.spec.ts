import assert from 'node:assert/strict';

import { parseEvidenceWorkspaceRoute } from '../../src/renderer/application/workspace/workspaceRoute';
import {
  prioritizeExportWizardCandidates,
  resolveExportWizardSelection,
} from '../../src/renderer/application/workspace/resolveExportWizardSelection';

function run(): void {
  const route = parseEvidenceWorkspaceRoute({
    subPath: 'workspace/export/detail/result/result-42',
  });

  assert.deepEqual(route, {
    tab: 'export',
    focus: {
      mode: 'detail',
      target: 'result',
      value: 'result-42',
    },
  });

  const candidates = [
    {
      id: 'tables/metrics.csv',
      name: 'metrics.csv',
      path: 'tables/metrics.csv',
    },
    {
      id: 'reports/model_report.md',
      name: 'model_report.md',
      path: 'reports/model_report.md',
    },
    {
      id: 'plots/roc_curve.png',
      name: 'roc_curve.png',
      path: 'plots/roc_curve.png',
    },
  ] as const;

  const selection = resolveExportWizardSelection({
    focus: route.focus,
    candidates,
    cards: [
      {
        cardId: 'card-1',
        resultId: 'result-42',
        artifactPath: 'reports/model_report.md',
      },
    ],
    pinnedItems: [],
  });

  assert.equal(selection.shouldAutoOpen, true);
  assert.equal(selection.preferredCandidateId, 'reports/model_report.md');
  assert.deepEqual(
    prioritizeExportWizardCandidates(candidates, selection.preferredCandidateId).map((candidate) => candidate.id),
    ['reports/model_report.md', 'tables/metrics.csv', 'plots/roc_curve.png'],
  );

  const pinnedSelection = resolveExportWizardSelection({
    focus: {
      mode: 'detail',
      target: 'result',
      value: 'result-99',
    },
    candidates,
    cards: [],
    pinnedItems: [
      {
        cardId: 'card-9',
        resultId: 'result-99',
        artifactPath: 'plots/roc_curve.png',
      },
    ],
  });

  assert.equal(pinnedSelection.shouldAutoOpen, true);
  assert.equal(pinnedSelection.preferredCandidateId, 'plots/roc_curve.png');

  const noMatchSelection = resolveExportWizardSelection({
    focus: {
      mode: 'detail',
      target: 'result',
      value: 'result-100',
    },
    candidates,
    cards: [
      {
        cardId: 'card-2',
        resultId: 'result-100',
      },
    ],
    pinnedItems: [],
  });

  assert.equal(noMatchSelection.shouldAutoOpen, true);
  assert.equal(noMatchSelection.preferredCandidateId, null);
  assert.deepEqual(
    prioritizeExportWizardCandidates(candidates, noMatchSelection.preferredCandidateId).map((candidate) => candidate.id),
    ['tables/metrics.csv', 'reports/model_report.md', 'plots/roc_curve.png'],
  );

  const passiveSelection = resolveExportWizardSelection({
    focus: {
      mode: 'highlight',
      target: 'result',
      value: 'result-42',
    },
    candidates,
    cards: [
      {
        cardId: 'card-1',
        resultId: 'result-42',
        artifactPath: 'reports/model_report.md',
      },
    ],
    pinnedItems: [],
  });

  assert.equal(passiveSelection.shouldAutoOpen, false);
  assert.equal(passiveSelection.preferredCandidateId, null);

  console.log('[contract] PASS resolve-export-wizard-selection (5 cases)');
}

run();
