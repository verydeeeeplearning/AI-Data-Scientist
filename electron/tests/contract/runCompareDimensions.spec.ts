import assert from 'node:assert/strict';

import type { RuntimeRunEntry } from '../../src/renderer/stores/runtimeStore';
import {
  filterRunsForComparison,
  formatRunCompareOption,
  parseCompareThreshold,
  sortRunsForComparison,
  type RunCompareScorecardSummary,
} from '../../src/renderer/components/runtime/runsCompareBoardModel';

function makeRun(overrides: Partial<RuntimeRunEntry> & Pick<RuntimeRunEntry, 'runId'>): RuntimeRunEntry {
  return {
    runId: overrides.runId,
    sessionId: overrides.sessionId ?? 'session-1',
    sessionLabel: overrides.sessionLabel ?? 'Session 1',
    surface: overrides.surface ?? 'mission',
    status: overrides.status ?? 'succeeded',
    message: overrides.message ?? '',
    taskId: overrides.taskId ?? null,
    error: overrides.error ?? null,
    resultPreview: overrides.resultPreview ?? null,
    costUsd: overrides.costUsd ?? 0,
    createdAt: overrides.createdAt ?? 1713265200,
    startedAt: overrides.startedAt ?? 1713265200,
    finishedAt: overrides.finishedAt ?? null,
  };
}

function scorecard(weightedScore: number, toolCallCount = 0): RunCompareScorecardSummary {
  return { weightedScore, toolCallCount };
}

function run(): void {
  const runs = [
    makeRun({ runId: 'run-low', costUsd: 1.5, createdAt: 3, startedAt: 3 }),
    makeRun({ runId: 'run-mid', costUsd: 3.25, createdAt: 2, startedAt: 2 }),
    makeRun({ runId: 'run-high', costUsd: 4.75, createdAt: 1, startedAt: 1 }),
  ];
  const scorecards = new Map<string, RunCompareScorecardSummary | null>([
    ['run-low', scorecard(0.42, 3)],
    ['run-mid', scorecard(0.68, 5)],
    ['run-high', scorecard(0.91, 9)],
  ]);

  // === sort by cost and score uses the requested comparison dimension ===
  {
    assert.deepEqual(
      sortRunsForComparison(runs, 'cost-asc', scorecards).map((run) => run.runId),
      ['run-low', 'run-mid', 'run-high'],
    );
    assert.deepEqual(
      sortRunsForComparison(runs, 'cost-desc', scorecards).map((run) => run.runId),
      ['run-high', 'run-mid', 'run-low'],
    );
    assert.deepEqual(
      sortRunsForComparison(runs, 'score-desc', scorecards).map((run) => run.runId),
      ['run-high', 'run-mid', 'run-low'],
    );
    assert.deepEqual(
      sortRunsForComparison(runs, 'score-asc', scorecards).map((run) => run.runId),
      ['run-low', 'run-mid', 'run-high'],
    );
  }

  // === filters keep only runs that satisfy the requested thresholds ===
  {
    assert.deepEqual(
      filterRunsForComparison(
        runs,
        { minCostUsd: 2, maxWeightedScore: 0.8 },
        scorecards,
      ).map((run) => run.runId),
      ['run-mid'],
    );
    assert.deepEqual(
      filterRunsForComparison(
        runs,
        { minCostUsd: null, maxWeightedScore: 0.5 },
        scorecards,
      ).map((run) => run.runId),
      ['run-low'],
    );
  }

  // === helpers tolerate missing scorecards while keeping the run visible ===
  {
    const noScores = new Map<string, RunCompareScorecardSummary | null>();
    assert.deepEqual(
      filterRunsForComparison(
        runs,
        { minCostUsd: 2, maxWeightedScore: 0.5 },
        noScores,
      ).map((run) => run.runId),
      ['run-mid', 'run-high'],
    );
    assert.deepEqual(
      sortRunsForComparison(runs, 'score-desc', noScores).map((run) => run.runId),
      ['run-low', 'run-mid', 'run-high'],
    );
  }

  // === UI labels include both cost and weighted score dimensions ===
  {
    const label = formatRunCompareOption(runs[0], scorecards);
    assert.ok(label.includes('score 0.420'));
    assert.ok(label.includes('$1.5000'));
  }

  // === threshold parser tolerates blank and invalid input ===
  {
    assert.equal(parseCompareThreshold(''), null);
    assert.equal(parseCompareThreshold('  '), null);
    assert.equal(parseCompareThreshold('1.25'), 1.25);
    assert.equal(parseCompareThreshold('not-a-number'), null);
  }

  console.log('[contract] PASS run-compare-dimensions (5 cases)');
}

run();
