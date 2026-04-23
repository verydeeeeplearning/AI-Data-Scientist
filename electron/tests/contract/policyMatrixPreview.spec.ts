import assert from 'node:assert/strict';

import { loadRiskTierMatrix } from '../../src/renderer/application/policy/loadRiskTierMatrix';
import { saveRiskTierMatrix } from '../../src/renderer/application/policy/saveRiskTierMatrix';
import {
  countMatrixCellDiff,
  formatLastSavedLabel,
  mergeImpactPreview,
  previewMatrixImpact,
} from '../../src/renderer/application/policy/previewMatrixImpact';
import type {
  LoadRiskTierMatrixPort,
  PreviewMatrixImpactInput,
  PreviewMatrixImpactPort,
  PreviewMatrixImpactResult,
  RiskTierMatrixSnapshot,
  SaveRiskTierMatrixInput,
  SaveRiskTierMatrixPort,
} from '../../src/renderer/application/policy/matrixPort';

interface PreviewCall {
  readonly input: PreviewMatrixImpactInput;
}

interface SaveCall {
  readonly input: SaveRiskTierMatrixInput;
}

function makePreviewPort(result: PreviewMatrixImpactResult): {
  port: PreviewMatrixImpactPort;
  calls: PreviewCall[];
} {
  const calls: PreviewCall[] = [];
  const port: PreviewMatrixImpactPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

function makeLoadPort(result: {
  matrix: Record<string, Record<string, string>>;
  history: RiskTierMatrixSnapshot[];
}): LoadRiskTierMatrixPort {
  return async () => result;
}

function makeSavePort(snapshot: RiskTierMatrixSnapshot): {
  port: SaveRiskTierMatrixPort;
  calls: SaveCall[];
} {
  const calls: SaveCall[] = [];
  const port: SaveRiskTierMatrixPort = async (input) => {
    calls.push({ input });
    return snapshot;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === previewMatrixImpact forwards candidate matrix to the port verbatim ===
  {
    const { port, calls } = makePreviewPort({
      addedRows: ['prod_deploy'],
      removedRows: [],
      modifiedRows: ['data_loader'],
      historicalCounts: { 'data_loader.supervised=T1': 4 },
    });

    const result = await previewMatrixImpact(port, {
      candidateMatrix: { data_loader: { supervised: 'T2' } },
    });

    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0]?.input.candidateMatrix, {
      data_loader: { supervised: 'T2' },
    });
    assert.deepEqual(result.addedRows, ['prod_deploy']);
    assert.equal(result.historicalCounts['data_loader.supervised=T1'], 4);
  }

  // === previewMatrixImpact rejects null/undefined candidateMatrix ===
  {
    const { port, calls } = makePreviewPort({
      addedRows: [],
      removedRows: [],
      modifiedRows: [],
      historicalCounts: {},
    });

    await assert.rejects(
      // @ts-expect-error intentionally bad input for the contract test
      () => previewMatrixImpact(port, { candidateMatrix: null }),
      /candidateMatrix is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === saveRiskTierMatrix rejects matrix with empty cell tier ===
  {
    const { port, calls } = makeSavePort({
      savedAt: 1.0,
      matrix: {},
      savedBy: null,
    });

    await assert.rejects(
      () =>
        saveRiskTierMatrix(port, {
          matrix: { data_loader: { supervised: '' } },
        }),
      /invalid cell/,
    );
    assert.equal(calls.length, 0);
  }

  // === loadRiskTierMatrix forwards to the port and returns the payload ===
  {
    const port = makeLoadPort({
      matrix: { data_loader: { supervised: 'T1' } },
      history: [
        {
          savedAt: 100.0,
          matrix: { data_loader: { supervised: 'T1' } },
          savedBy: 'op@example.com',
        },
      ],
    });

    const result = await loadRiskTierMatrix(port);
    assert.deepEqual(result.matrix, { data_loader: { supervised: 'T1' } });
    assert.equal(result.history.length, 1);
    assert.equal(result.history[0]?.savedBy, 'op@example.com');
  }

  // === mergeImpactPreview overlays heuristic count without dropping fields ===
  {
    const merged = mergeImpactPreview(
      {
        addedRows: ['a'],
        removedRows: ['b'],
        modifiedRows: ['c'],
        historicalCounts: { 'a.supervised=T1': 7 },
      },
      3.7,
    );
    assert.deepEqual(merged.addedRows, ['a']);
    assert.deepEqual(merged.removedRows, ['b']);
    assert.deepEqual(merged.modifiedRows, ['c']);
    assert.equal(merged.historicalCounts['a.supervised=T1'], 7);
    // Heuristic count is floored to a non-negative integer.
    assert.equal(merged.heuristicChangedCells, 3);

    const negative = mergeImpactPreview(
      {
        addedRows: [],
        removedRows: [],
        modifiedRows: [],
        historicalCounts: {},
      },
      -2,
    );
    assert.equal(negative.heuristicChangedCells, 0);
  }

  // === formatLastSavedLabel handles missing snapshot + missing savedBy ===
  {
    assert.equal(formatLastSavedLabel(null), null);
    assert.equal(formatLastSavedLabel(undefined), null);
    assert.equal(
      formatLastSavedLabel({
        savedAt: 0,
        matrix: {},
        savedBy: null,
      }),
      null,
    );

    const labelNoActor = formatLastSavedLabel({
      savedAt: 1700000000,
      matrix: {},
      savedBy: null,
    });
    assert.ok(labelNoActor && labelNoActor.startsWith('Last saved: '));
    assert.ok(labelNoActor && !labelNoActor.includes(' by '));

    const labelWithActor = formatLastSavedLabel({
      savedAt: 1700000000,
      matrix: {},
      savedBy: 'op@example.com',
    });
    assert.ok(labelWithActor && labelWithActor.endsWith(' by op@example.com'));
  }

  // === countMatrixCellDiff counts per-cell differences across both matrices ===
  {
    const diff = countMatrixCellDiff(
      { data_loader: { supervised: 'T1' } },
      {
        data_loader: { supervised: 'T2', delegate: 'T0' },
        prod_deploy: { delegate: 'T3' },
      },
    );
    // data_loader.supervised changed (T1->T2) + data_loader.delegate added
    // + prod_deploy.delegate added = 3 cells.
    assert.equal(diff, 3);

    assert.equal(countMatrixCellDiff({}, {}), 0);
  }

  console.log('[contract] PASS policy-matrix-preview (7 cases)');
}

void run();
