"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const resolveWorkspaceExportRunId_1 = require("../../src/renderer/application/workspace/resolveWorkspaceExportRunId");
function run() {
    const runtimeRuns = [
        { runId: 'run-old', sessionId: 'session-a', startedAt: 10 },
        { runId: 'run-current', sessionId: 'session-a', startedAt: 30 },
        { runId: 'run-other-session', sessionId: 'session-b', startedAt: 40 },
    ];
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        focus: {
            mode: 'detail',
            target: 'result',
            value: 'result-focused',
        },
        sessionId: 'session-a',
        selectedRunId: 'run-old',
        reasoningRunId: 'run-old',
        runtimeRuns,
        cards: [
            {
                resultId: 'result-focused',
                runId: 'run-current',
            },
        ],
        pinnedItems: [],
    }), 'run-current');
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        sessionId: 'session-a',
        selectedRunId: 'run-current',
        reasoningRunId: 'run-old',
        runtimeRuns,
        cards: [],
        pinnedItems: [],
    }), 'run-current');
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        sessionId: 'session-a',
        selectedRunId: 'run-missing',
        reasoningRunId: 'run-old',
        runtimeRuns,
        cards: [],
        pinnedItems: [],
    }), 'run-old');
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        sessionId: 'session-a',
        selectedRunId: null,
        reasoningRunId: null,
        runtimeRuns,
        cards: [],
        pinnedItems: [{ runId: 'run-old' }],
    }), 'run-old');
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        sessionId: 'session-a',
        selectedRunId: null,
        reasoningRunId: null,
        runtimeRuns,
        cards: [],
        pinnedItems: [],
    }), 'run-current');
    strict_1.default.equal((0, resolveWorkspaceExportRunId_1.resolveWorkspaceExportRunId)({
        sessionId: 'missing-session',
        selectedRunId: 'run-current',
        reasoningRunId: 'run-old',
        runtimeRuns,
        cards: [],
        pinnedItems: [{ runId: 'run-old' }],
    }), null);
    console.log('[contract] PASS resolve-workspace-export-run-id (6 cases)');
}
run();
