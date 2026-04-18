export interface RegressionWindowStatsView {
  recordCount: number;
  avgWeightedScore: number | null;
  passRate: number | null;
}

export interface RegressionAlertView {
  kind: string;
  severity: 'high' | 'medium' | 'low';
  scope: 'overall' | 'dimension' | 'task' | 'mode';
  scopeKey: string | null;
  dimension: string | null;
  taskId: string | null;
  message: string;
  delta: number | null;
  currentValue: number | null;
  baselineValue: number | null;
}

export interface RegressionBoardPointView {
  axisKey: string;
  axisLabel: string;
  runCount: number;
  passRate: number;
  weightedScoreMean: number;
  perDimensionMeans: Record<string, number>;
  perModeWeightedScores: Record<string, number>;
}

export interface RegressionFrozenBaselineView {
  baselineId: string;
  commitSha: string;
  mode: string | null;
  domain: string | null;
  taskId: string | null;
  passRate: number;
  weightedScoreMean: number;
  baselineWindowDays: number;
  sourcePointCount: number;
  createdAt: number;
}

export interface RegressionModeSummaryView {
  mode: string;
  recordCount: number;
  avgWeightedScore: number | null;
  passRate: number | null;
}

export interface RegressionTaskSummaryView {
  taskId: string;
  domain: string | null;
  difficulty: string | null;
  latestRunId: string;
  latestMode: string;
  latestRecordedAt: number;
  latestWeightedScore: number;
  latestPassed: boolean;
  passThreshold: number | null;
  alertOnDropBelow: number | null;
  recentRecordCount: number;
  baselineRecordCount: number;
  recentMeanScore: number | null;
  baselineMeanScore: number | null;
  deltaScore: number | null;
  status: 'healthy' | 'regressed' | 'failing' | 'insufficient_baseline';
}

export interface RegressionDimensionSummaryView {
  name: string;
  label: string;
  recentRecordCount: number;
  baselineRecordCount: number;
  recentMeanScore: number | null;
  baselineMeanScore: number | null;
  deltaScore: number | null;
}

export interface RegressionBoardView {
  generatedAt: number;
  totalRecords: number;
  recentWindow: number;
  baselineWindowDays: number;
  axisKind: 'commit' | 'date';
  baselineSource: 'rolling' | 'frozen';
  pointCount: number;
  filters: {
    mode: string | null;
    domain: string | null;
  };
  availableDomains: string[];
  overall: {
    recent: RegressionWindowStatsView;
    baseline: RegressionWindowStatsView;
    deltaScore: number | null;
    deltaPassRate: number | null;
  };
  frozenBaseline: RegressionFrozenBaselineView | null;
  modeSummaries: RegressionModeSummaryView[];
  points: RegressionBoardPointView[];
  taskSummaries: RegressionTaskSummaryView[];
  dimensionSummaries: RegressionDimensionSummaryView[];
  alerts: RegressionAlertView[];
}
