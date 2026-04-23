import type { RuntimeRunEntry } from '../../stores/runtimeStore';

export type RunCompareSortKey =
  | 'newest'
  | 'oldest'
  | 'cost-desc'
  | 'cost-asc'
  | 'score-desc'
  | 'score-asc';

export interface RunCompareScorecardSummary {
  readonly weightedScore: number;
  readonly toolCallCount?: number | null;
}

export interface RunCompareFilters {
  readonly minCostUsd: number | null;
  readonly maxWeightedScore: number | null;
}

function runTimestamp(run: RuntimeRunEntry): number {
  return run.startedAt || run.createdAt;
}

export function getRunWeightedScore(
  runId: string,
  scorecardsByRunId: ReadonlyMap<string, RunCompareScorecardSummary | null>,
): number | null {
  const scorecard = scorecardsByRunId.get(runId) ?? null;
  return scorecard ? scorecard.weightedScore : null;
}

export function parseCompareThreshold(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function sortRunsForComparison(
  runs: readonly RuntimeRunEntry[],
  sortKey: RunCompareSortKey,
  scorecardsByRunId: ReadonlyMap<string, RunCompareScorecardSummary | null>,
): RuntimeRunEntry[] {
  const scored = [...runs];

  scored.sort((left, right) => {
    const leftScore = getRunWeightedScore(left.runId, scorecardsByRunId);
    const rightScore = getRunWeightedScore(right.runId, scorecardsByRunId);

    if (sortKey === 'cost-asc' || sortKey === 'cost-desc') {
      if (left.costUsd !== right.costUsd) {
        return sortKey === 'cost-desc'
          ? right.costUsd - left.costUsd
          : left.costUsd - right.costUsd;
      }
    } else if (sortKey === 'score-asc' || sortKey === 'score-desc') {
      if (leftScore !== rightScore) {
        if (leftScore === null) return 1;
        if (rightScore === null) return -1;
        return sortKey === 'score-desc'
          ? rightScore - leftScore
          : leftScore - rightScore;
      }
      if (runTimestamp(left) !== runTimestamp(right)) {
        return sortKey === 'score-desc'
          ? runTimestamp(right) - runTimestamp(left)
          : runTimestamp(left) - runTimestamp(right);
      }
    } else if (runTimestamp(left) !== runTimestamp(right)) {
      return sortKey === 'oldest'
        ? runTimestamp(left) - runTimestamp(right)
        : runTimestamp(right) - runTimestamp(left);
    }

    if (left.costUsd !== right.costUsd) {
      return right.costUsd - left.costUsd;
    }

    return left.runId.localeCompare(right.runId);
  });

  return scored;
}

export function filterRunsForComparison(
  runs: readonly RuntimeRunEntry[],
  filters: RunCompareFilters,
  scorecardsByRunId: ReadonlyMap<string, RunCompareScorecardSummary | null>,
): RuntimeRunEntry[] {
  return runs.filter((run) => {
    if (filters.minCostUsd !== null && run.costUsd <= filters.minCostUsd) {
      return false;
    }

    if (filters.maxWeightedScore === null) {
      return true;
    }

    const weightedScore = getRunWeightedScore(run.runId, scorecardsByRunId);
    if (weightedScore === null) {
      return true;
    }

    return weightedScore < filters.maxWeightedScore;
  });
}

export function formatRunCompareOption(
  run: RuntimeRunEntry,
  scorecardsByRunId: ReadonlyMap<string, RunCompareScorecardSummary | null>,
): string {
  const sessionLabel = run.sessionLabel || run.sessionId;
  const timestamp = new Date((run.finishedAt ?? run.startedAt ?? run.createdAt) * 1000);
  const weightedScore = getRunWeightedScore(run.runId, scorecardsByRunId);
  const scorePart = weightedScore === null ? 'score n/a' : `score ${weightedScore.toFixed(3)}`;
  return `${run.runId} | ${run.status} | ${sessionLabel} | ${scorePart} | $${run.costUsd.toFixed(4)} | ${timestamp.toLocaleString()}`;
}
