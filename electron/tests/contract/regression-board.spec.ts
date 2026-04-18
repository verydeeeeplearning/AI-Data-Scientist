import assert from 'node:assert/strict';

import type { RegressionBoardView } from '../../src/renderer/types/evaluation';
import {
  buildRegressionBoardModel,
  getDefaultRegressionPointKey,
} from '../../src/renderer/components/runtime/regressionBoardModel';

function fixture(): RegressionBoardView {
  return {
    generatedAt: 1713265200,
    totalRecords: 6,
    recentWindow: 3,
    baselineWindowDays: 14,
    axisKind: 'commit',
    baselineSource: 'frozen',
    pointCount: 3,
    filters: {
      mode: null,
      domain: null,
    },
    availableDomains: ['finance', 'retail'],
    overall: {
      recent: {
        recordCount: 3,
        avgWeightedScore: 0.55,
        passRate: 0,
      },
      baseline: {
        recordCount: 3,
        avgWeightedScore: 0.87,
        passRate: 1,
      },
      deltaScore: -0.32,
      deltaPassRate: -1,
    },
    frozenBaseline: {
      baselineId: 'baseline-123',
      commitSha: 'commit-b',
      mode: null,
      domain: null,
      taskId: null,
      passRate: 1,
      weightedScoreMean: 0.87,
      baselineWindowDays: 14,
      sourcePointCount: 3,
      createdAt: 1713260000,
    },
    modeSummaries: [
      { mode: 'offline', recordCount: 4, avgWeightedScore: 0.78, passRate: 0.75 },
      { mode: 'online', recordCount: 2, avgWeightedScore: 0.56, passRate: 0 },
    ],
    points: [
      {
        axisKey: 'commit-a',
        axisLabel: 'commit-a',
        runCount: 2,
        passRate: 1,
        weightedScoreMean: 0.91,
        perDimensionMeans: {
          scoping_accuracy: 0.92,
          tool_trajectory: 0.88,
        },
        perModeWeightedScores: {
          offline: 0.91,
        },
      },
      {
        axisKey: 'commit-b',
        axisLabel: 'commit-b',
        runCount: 2,
        passRate: 0.5,
        weightedScoreMean: 0.74,
        perDimensionMeans: {
          scoping_accuracy: 0.78,
          tool_trajectory: 0.71,
        },
        perModeWeightedScores: {
          offline: 0.74,
        },
      },
      {
        axisKey: 'commit-c',
        axisLabel: 'commit-c',
        runCount: 2,
        passRate: 0,
        weightedScoreMean: 0.55,
        perDimensionMeans: {
          scoping_accuracy: 0.52,
          tool_trajectory: 0.7,
        },
        perModeWeightedScores: {
          offline: 0.54,
          online: 0.56,
        },
      },
    ],
    taskSummaries: [
      {
        taskId: 'retail.margin_watch.v1',
        domain: 'retail',
        difficulty: 'medium',
        latestRunId: 'run-4',
        latestMode: 'offline',
        latestRecordedAt: 1713265100,
        latestWeightedScore: 0.52,
        latestPassed: false,
        passThreshold: 0.6,
        alertOnDropBelow: 0.5,
        recentRecordCount: 2,
        baselineRecordCount: 2,
        recentMeanScore: 0.7,
        baselineMeanScore: 0.89,
        deltaScore: -0.19,
        status: 'failing',
      },
      {
        taskId: 'finance.risk_triage.v1',
        domain: 'finance',
        difficulty: 'medium',
        latestRunId: 'run-6',
        latestMode: 'online',
        latestRecordedAt: 1713265200,
        latestWeightedScore: 0.54,
        latestPassed: false,
        passThreshold: 0.65,
        alertOnDropBelow: 0.55,
        recentRecordCount: 2,
        baselineRecordCount: 1,
        recentMeanScore: 0.56,
        baselineMeanScore: 0.82,
        deltaScore: -0.26,
        status: 'failing',
      },
    ],
    dimensionSummaries: [
      {
        name: 'scoping_accuracy',
        label: 'Scoping Accuracy',
        recentRecordCount: 3,
        baselineRecordCount: 3,
        recentMeanScore: 0.52,
        baselineMeanScore: 0.85,
        deltaScore: -0.33,
      },
      {
        name: 'tool_trajectory',
        label: 'Tool Trajectory',
        recentRecordCount: 3,
        baselineRecordCount: 3,
        recentMeanScore: 0.7,
        baselineMeanScore: 0.82,
        deltaScore: -0.12,
      },
    ],
    alerts: [
      {
        kind: 'pass_rate_drop',
        severity: 'high',
        scope: 'overall',
        scopeKey: null,
        dimension: null,
        taskId: null,
        message: 'Gold-suite pass rate dropped below the rolling baseline by more than 3pp.',
        delta: -1,
        currentValue: 0,
        baselineValue: 1,
      },
      {
        kind: 'single_task_hard_fail',
        severity: 'high',
        scope: 'task',
        scopeKey: 'retail.margin_watch.v1',
        dimension: null,
        taskId: 'retail.margin_watch.v1',
        message: 'retail.margin_watch.v1 fell below its task pass threshold.',
        delta: null,
        currentValue: 0.52,
        baselineValue: 0.6,
      },
      {
        kind: 'dimension_regression',
        severity: 'medium',
        scope: 'dimension',
        scopeKey: 'scoping_accuracy',
        dimension: 'scoping_accuracy',
        taskId: null,
        message: 'Scoping Accuracy dropped below the rolling baseline by more than 5pp.',
        delta: -0.33,
        currentValue: 0.52,
        baselineValue: 0.85,
      },
    ],
  };
}

function run(): void {
  const board = fixture();
  const model = buildRegressionBoardModel(board, getDefaultRegressionPointKey(board));
  assert.ok(model);
  assert.equal(model?.totalRecords, 6);
  assert.equal(model?.alertCount, 3);
  assert.equal(model?.axisKind, 'commit');
  assert.equal(model?.baselineSource, 'frozen');
  assert.equal(model?.pointCount, 3);
  assert.equal(model?.recentScorePercent, 55);
  assert.equal(model?.baselineScorePercent, 87);
  assert.equal(model?.deltaScorePercentPoints, -32);
  assert.equal(model?.deltaPassRatePercentPoints, -100);
  assert.equal(model?.topAlerts[0].kind, 'pass_rate_drop');
  assert.equal(model?.topTaskRegressions[0].taskId, 'finance.risk_triage.v1');
  assert.equal(model?.selectedPoint?.axisKey, 'commit-c');
  assert.equal(model?.selectedPointIsFrozenBaseline, false);
  assert.equal(model?.previousPoint?.axisKey, 'commit-b');
  assert.equal(model?.pointScoreDeltaPercentPoints, -19);
  assert.equal(model?.pointPassRateDeltaPercentPoints, -50);
  assert.equal(model?.pointDiffs[0]?.name, 'scoping_accuracy');
  assert.equal(model?.pointDiffs[0]?.previousScore, 0.78);
  assert.equal(model?.pointDiffs[0]?.currentScore, 0.52);
  assert.equal(model?.pointModeDiffs.length, 2);
  assert.deepEqual(
    model?.pointModeDiffs.map((item) => item.mode),
    ['offline', 'online']
  );
  assert.ok(
    Math.abs((model?.pointModeDiffs[0]?.deltaScore ?? 0) - (-0.2)) < 1e-9
  );
  assert.equal(model?.pointModeDiffs[1]?.deltaScore, null);
  assert.equal(model?.canFreezeBaseline, true);
  assert.deepEqual(
    model?.topDimensionRegressions.map((item) => item.name),
    ['scoping_accuracy', 'tool_trajectory']
  );

  const frozenPointModel = buildRegressionBoardModel(board, 'commit-b');
  assert.ok(frozenPointModel);
  assert.equal(frozenPointModel?.selectedPoint?.axisKey, 'commit-b');
  assert.equal(frozenPointModel?.selectedPointIsFrozenBaseline, true);
  assert.equal(frozenPointModel?.canFreezeBaseline, false);

  console.log('[contract] PASS regression-board model');
}

run();
