"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const regressionBoardModel_1 = require("../../src/renderer/components/runtime/regressionBoardModel");
function fixture() {
    return {
        generatedAt: 1713265200,
        totalRecords: 6,
        recentWindow: 3,
        baselineWindowDays: 14,
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
        modeSummaries: [
            { mode: 'offline', recordCount: 4, avgWeightedScore: 0.78, passRate: 0.75 },
            { mode: 'online', recordCount: 2, avgWeightedScore: 0.56, passRate: 0 },
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
                message: 'Scoping Accuracy dropped below the rolling baseline by more than 5pp.',
                delta: -0.33,
                currentValue: 0.52,
                baselineValue: 0.85,
            },
        ],
    };
}
function run() {
    const model = (0, regressionBoardModel_1.buildRegressionBoardModel)(fixture());
    strict_1.default.ok(model);
    strict_1.default.equal(model?.totalRecords, 6);
    strict_1.default.equal(model?.alertCount, 3);
    strict_1.default.equal(model?.recentScorePercent, 55);
    strict_1.default.equal(model?.baselineScorePercent, 87);
    strict_1.default.equal(model?.deltaScorePercentPoints, -32);
    strict_1.default.equal(model?.deltaPassRatePercentPoints, -100);
    strict_1.default.equal(model?.topAlerts[0].kind, 'pass_rate_drop');
    strict_1.default.equal(model?.topTaskRegressions[0].taskId, 'finance.risk_triage.v1');
    strict_1.default.deepEqual(model?.topDimensionRegressions.map((item) => item.name), ['scoping_accuracy', 'tool_trajectory']);
    console.log('[contract] PASS regression-board model');
}
run();
