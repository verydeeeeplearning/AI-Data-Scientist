"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const runsCompareBoardModel_1 = require("../../src/renderer/components/runtime/runsCompareBoardModel");
function makeRun(overrides) {
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
function scorecard(weightedScore, toolCallCount = 0) {
    return { weightedScore, toolCallCount };
}
function run() {
    const runs = [
        makeRun({ runId: 'run-low', costUsd: 1.5, createdAt: 3, startedAt: 3 }),
        makeRun({ runId: 'run-mid', costUsd: 3.25, createdAt: 2, startedAt: 2 }),
        makeRun({ runId: 'run-high', costUsd: 4.75, createdAt: 1, startedAt: 1 }),
    ];
    const scorecards = new Map([
        ['run-low', scorecard(0.42, 3)],
        ['run-mid', scorecard(0.68, 5)],
        ['run-high', scorecard(0.91, 9)],
    ]);
    // === sort by cost and score uses the requested comparison dimension ===
    {
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.sortRunsForComparison)(runs, 'cost-asc', scorecards).map((run) => run.runId), ['run-low', 'run-mid', 'run-high']);
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.sortRunsForComparison)(runs, 'cost-desc', scorecards).map((run) => run.runId), ['run-high', 'run-mid', 'run-low']);
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.sortRunsForComparison)(runs, 'score-desc', scorecards).map((run) => run.runId), ['run-high', 'run-mid', 'run-low']);
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.sortRunsForComparison)(runs, 'score-asc', scorecards).map((run) => run.runId), ['run-low', 'run-mid', 'run-high']);
    }
    // === filters keep only runs that satisfy the requested thresholds ===
    {
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.filterRunsForComparison)(runs, { minCostUsd: 2, maxWeightedScore: 0.8 }, scorecards).map((run) => run.runId), ['run-mid']);
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.filterRunsForComparison)(runs, { minCostUsd: null, maxWeightedScore: 0.5 }, scorecards).map((run) => run.runId), ['run-low']);
    }
    // === helpers tolerate missing scorecards while keeping the run visible ===
    {
        const noScores = new Map();
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.filterRunsForComparison)(runs, { minCostUsd: 2, maxWeightedScore: 0.5 }, noScores).map((run) => run.runId), ['run-mid', 'run-high']);
        strict_1.default.deepEqual((0, runsCompareBoardModel_1.sortRunsForComparison)(runs, 'score-desc', noScores).map((run) => run.runId), ['run-low', 'run-mid', 'run-high']);
    }
    // === UI labels include both cost and weighted score dimensions ===
    {
        const label = (0, runsCompareBoardModel_1.formatRunCompareOption)(runs[0], scorecards);
        strict_1.default.ok(label.includes('score 0.420'));
        strict_1.default.ok(label.includes('$1.5000'));
    }
    // === threshold parser tolerates blank and invalid input ===
    {
        strict_1.default.equal((0, runsCompareBoardModel_1.parseCompareThreshold)(''), null);
        strict_1.default.equal((0, runsCompareBoardModel_1.parseCompareThreshold)('  '), null);
        strict_1.default.equal((0, runsCompareBoardModel_1.parseCompareThreshold)('1.25'), 1.25);
        strict_1.default.equal((0, runsCompareBoardModel_1.parseCompareThreshold)('not-a-number'), null);
    }
    console.log('[contract] PASS run-compare-dimensions (5 cases)');
}
run();
