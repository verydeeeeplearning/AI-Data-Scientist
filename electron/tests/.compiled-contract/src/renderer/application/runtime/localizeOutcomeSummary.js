"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.localizeOutcomeSummary = localizeOutcomeSummary;
function intValue(value) {
    return Number.parseInt(value.replace(/,/g, ''), 10);
}
function normalizedRows(value) {
    return intValue(value).toLocaleString();
}
const OUTCOME_PATTERNS = [
    {
        pattern: /^Loaded (\d+) file\(s\) and scanned ([\d,]+) rows\.$/,
        key: 'run.runtime.stageOutcome.dataLoader.loadedRows',
        vars: (match) => ({ count: intValue(match[1]), rows: normalizedRows(match[2]) }),
    },
    {
        pattern: /^Loaded (\d+) file\(s\)\.$/,
        key: 'run.runtime.stageOutcome.dataLoader.loaded',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Detected (\d+) schema or quality issue\(s\)\.$/,
        key: 'run.runtime.stageOutcome.schemaDiagnose.detected',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^No major schema issues surfaced\.$/,
        key: 'run.runtime.stageOutcome.schemaDiagnose.none',
        vars: () => undefined,
    },
    {
        pattern: /^Captured (\d+) evaluation signal\(s\)\.$/,
        key: 'run.runtime.stageOutcome.evaluation.captured',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Evaluation completed across (\d+) tool step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.evaluation.completed',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Prepared (\d+) export artifact\(s\)\.$/,
        key: 'run.runtime.stageOutcome.export.prepared',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Completed (\d+) exploratory analysis step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.eda.completed',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Prepared (\d+) feature engineering step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.featureEngineering.prepared',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Built (\d+) baseline modeling step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.baselineModeling.built',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Compared (\d+) model candidate step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.modelComparison.compared',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Generated (\d+) reporting artifact step\(s\)\.$/,
        key: 'run.runtime.stageOutcome.reporting.generated',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
    {
        pattern: /^Ran (\d+) verification check\(s\)\.$/,
        key: 'run.runtime.stageOutcome.verification.ran',
        vars: (match) => ({ count: intValue(match[1]) }),
    },
];
function localizeOutcomeSummary(t, summary) {
    const trimmed = summary.trim();
    if (trimmed.length === 0) {
        return summary;
    }
    for (const item of OUTCOME_PATTERNS) {
        const match = trimmed.match(item.pattern);
        if (match) {
            return t(item.key, item.vars(match));
        }
    }
    return summary;
}
