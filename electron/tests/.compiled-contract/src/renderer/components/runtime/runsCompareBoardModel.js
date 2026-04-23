"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getRunWeightedScore = getRunWeightedScore;
exports.parseCompareThreshold = parseCompareThreshold;
exports.sortRunsForComparison = sortRunsForComparison;
exports.filterRunsForComparison = filterRunsForComparison;
exports.formatRunCompareOption = formatRunCompareOption;
function runTimestamp(run) {
    return run.startedAt || run.createdAt;
}
function getRunWeightedScore(runId, scorecardsByRunId) {
    const scorecard = scorecardsByRunId.get(runId) ?? null;
    return scorecard ? scorecard.weightedScore : null;
}
function parseCompareThreshold(value) {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
        return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
}
function sortRunsForComparison(runs, sortKey, scorecardsByRunId) {
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
        }
        else if (sortKey === 'score-asc' || sortKey === 'score-desc') {
            if (leftScore !== rightScore) {
                if (leftScore === null)
                    return 1;
                if (rightScore === null)
                    return -1;
                return sortKey === 'score-desc'
                    ? rightScore - leftScore
                    : leftScore - rightScore;
            }
            if (runTimestamp(left) !== runTimestamp(right)) {
                return sortKey === 'score-desc'
                    ? runTimestamp(right) - runTimestamp(left)
                    : runTimestamp(left) - runTimestamp(right);
            }
        }
        else if (runTimestamp(left) !== runTimestamp(right)) {
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
function filterRunsForComparison(runs, filters, scorecardsByRunId) {
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
function formatRunCompareOption(run, scorecardsByRunId) {
    const sessionLabel = run.sessionLabel || run.sessionId;
    const timestamp = new Date((run.finishedAt ?? run.startedAt ?? run.createdAt) * 1000);
    const weightedScore = getRunWeightedScore(run.runId, scorecardsByRunId);
    const scorePart = weightedScore === null ? 'score n/a' : `score ${weightedScore.toFixed(3)}`;
    return `${run.runId} | ${run.status} | ${sessionLabel} | ${scorePart} | $${run.costUsd.toFixed(4)} | ${timestamp.toLocaleString()}`;
}
