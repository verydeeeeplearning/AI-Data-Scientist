import type {
  RegressionAlertView,
  RegressionBoardPointView,
  RegressionBoardView,
  RegressionDimensionSummaryView,
  RegressionTaskSummaryView,
} from '../../types/evaluation';

export interface RegressionPointDiffView {
  name: string;
  label: string;
  currentScore: number | null;
  previousScore: number | null;
  deltaScore: number | null;
}

export interface RegressionModeDiffView {
  mode: string;
  currentScore: number | null;
  previousScore: number | null;
  deltaScore: number | null;
}

export interface RegressionBoardModel {
  totalRecords: number;
  recentScorePercent: number | null;
  baselineScorePercent: number | null;
  deltaScorePercentPoints: number | null;
  deltaPassRatePercentPoints: number | null;
  alertCount: number;
  baselineSource: 'rolling' | 'frozen';
  axisKind: 'commit' | 'date';
  pointCount: number;
  canFreezeBaseline: boolean;
  selectedPoint: RegressionBoardPointView | null;
  selectedPointIsFrozenBaseline: boolean;
  previousPoint: RegressionBoardPointView | null;
  pointScoreDeltaPercentPoints: number | null;
  pointPassRateDeltaPercentPoints: number | null;
  pointDiffs: RegressionPointDiffView[];
  pointModeDiffs: RegressionModeDiffView[];
  topAlerts: RegressionAlertView[];
  topTaskRegressions: RegressionTaskSummaryView[];
  topDimensionRegressions: RegressionDimensionSummaryView[];
}

export function buildRegressionBoardModel(
  board: RegressionBoardView | null | undefined,
  selectedPointKey: string | null = null
): RegressionBoardModel | null {
  if (!board) {
    return null;
  }

  const selectedPoint = resolveSelectedPoint(board.points, selectedPointKey);
  const previousPoint = resolvePreviousPoint(board.points, selectedPoint);
  const selectedPointIsFrozenBaseline =
    selectedPoint !== null && board.frozenBaseline?.commitSha === selectedPoint.axisKey;
  const pointDiffs = buildPointDiffs(board, selectedPoint, previousPoint);
  const pointModeDiffs = buildModeDiffs(selectedPoint, previousPoint);

  return {
    totalRecords: board.totalRecords,
    recentScorePercent: toPercent(board.overall.recent.avgWeightedScore),
    baselineScorePercent: toPercent(board.overall.baseline.avgWeightedScore),
    deltaScorePercentPoints: toPercentPoints(board.overall.deltaScore),
    deltaPassRatePercentPoints: toPercentPoints(board.overall.deltaPassRate),
    alertCount: board.alerts.length,
    baselineSource: board.baselineSource,
    axisKind: board.axisKind,
    pointCount: board.pointCount,
    canFreezeBaseline:
      board.axisKind === 'commit' && selectedPoint !== null && !selectedPointIsFrozenBaseline,
    selectedPoint,
    selectedPointIsFrozenBaseline,
    previousPoint,
    pointScoreDeltaPercentPoints:
      selectedPoint && previousPoint
        ? toPercentPoints(selectedPoint.weightedScoreMean - previousPoint.weightedScoreMean)
        : null,
    pointPassRateDeltaPercentPoints:
      selectedPoint && previousPoint
        ? toPercentPoints(selectedPoint.passRate - previousPoint.passRate)
        : null,
    pointDiffs,
    pointModeDiffs,
    topAlerts: board.alerts.slice(0, 3),
    topTaskRegressions: [...board.taskSummaries]
      .filter((task) => task.deltaScore !== null && task.deltaScore < 0)
      .sort((left, right) => (left.deltaScore ?? 0) - (right.deltaScore ?? 0))
      .slice(0, 3),
    topDimensionRegressions: [...board.dimensionSummaries]
      .filter((dimension) => dimension.deltaScore !== null && dimension.deltaScore < 0)
      .sort((left, right) => (left.deltaScore ?? 0) - (right.deltaScore ?? 0))
      .slice(0, 4),
  };
}

export function getDefaultRegressionPointKey(
  board: RegressionBoardView | null | undefined
): string | null {
  if (!board || board.points.length === 0) {
    return null;
  }
  return board.points[board.points.length - 1]?.axisKey ?? null;
}

function resolveSelectedPoint(
  points: RegressionBoardPointView[],
  selectedPointKey: string | null
): RegressionBoardPointView | null {
  if (points.length === 0) {
    return null;
  }
  if (selectedPointKey) {
    const matched = points.find((item) => item.axisKey === selectedPointKey);
    if (matched) {
      return matched;
    }
  }
  return points[points.length - 1] ?? null;
}

function resolvePreviousPoint(
  points: RegressionBoardPointView[],
  selectedPoint: RegressionBoardPointView | null
): RegressionBoardPointView | null {
  if (!selectedPoint) {
    return null;
  }
  const selectedIndex = points.findIndex((item) => item.axisKey === selectedPoint.axisKey);
  if (selectedIndex <= 0) {
    return null;
  }
  return points[selectedIndex - 1] ?? null;
}

function buildPointDiffs(
  board: RegressionBoardView,
  selectedPoint: RegressionBoardPointView | null,
  previousPoint: RegressionBoardPointView | null
): RegressionPointDiffView[] {
  if (!selectedPoint || !previousPoint) {
    return [];
  }
  const labelByName = new Map(board.dimensionSummaries.map((item) => [item.name, item.label]));
  const names = new Set([
    ...Object.keys(selectedPoint.perDimensionMeans),
    ...Object.keys(previousPoint.perDimensionMeans),
  ]);
  return [...names]
    .map((name) => {
      const current = selectedPoint.perDimensionMeans[name];
      const baseline = previousPoint.perDimensionMeans[name];
      return {
        name,
        label: labelByName.get(name) ?? humanizeName(name),
        currentScore: current ?? null,
        previousScore: baseline ?? null,
        deltaScore:
          current === undefined || baseline === undefined ? null : current - baseline,
      };
    })
    .sort((left, right) => (left.deltaScore ?? 0) - (right.deltaScore ?? 0))
    .slice(0, 4);
}

function buildModeDiffs(
  selectedPoint: RegressionBoardPointView | null,
  previousPoint: RegressionBoardPointView | null
): RegressionModeDiffView[] {
  if (!selectedPoint || !previousPoint) {
    return [];
  }
  const modes = new Set([
    ...Object.keys(selectedPoint.perModeWeightedScores),
    ...Object.keys(previousPoint.perModeWeightedScores),
  ]);
  return [...modes]
    .map((mode) => {
      const current = selectedPoint.perModeWeightedScores[mode];
      const previous = previousPoint.perModeWeightedScores[mode];
      return {
        mode,
        currentScore: current ?? null,
        previousScore: previous ?? null,
        deltaScore:
          current === undefined || previous === undefined ? null : current - previous,
      };
    })
    .sort((left, right) => left.mode.localeCompare(right.mode));
}

function humanizeName(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(' ');
}

function toPercent(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return Math.round(value * 100);
}

function toPercentPoints(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return Math.round(value * 1000) / 10;
}
