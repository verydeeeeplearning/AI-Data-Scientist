"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const branchRun_1 = require("../../src/renderer/application/run/branchRun");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards parentRunId/message and relays branchedFromRunId verbatim ===
    {
        const { port, calls } = makePort({
            runId: 'run-99',
            sessionId: 'sess-A',
            branchedFromRunId: 'run-42',
        });
        const result = await (0, branchRun_1.branchRun)(port, {
            parentRunId: 'run-42',
            message: 'explore alternative model',
        });
        strict_1.default.equal(result.runId, 'run-99');
        strict_1.default.equal(result.sessionId, 'sess-A');
        strict_1.default.equal(result.branchedFromRunId, 'run-42');
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.parentRunId, 'run-42');
        strict_1.default.equal(calls[0]?.input.message, 'explore alternative model');
    }
    // === rejects empty parentRunId before reaching transport ===
    {
        const { port, calls } = makePort({
            runId: 'unused',
            sessionId: 'unused',
            branchedFromRunId: null,
        });
        await strict_1.default.rejects(() => (0, branchRun_1.branchRun)(port, { parentRunId: '   ', message: 'hi' }), /parentRunId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === rejects empty message before reaching transport ===
    {
        const { port, calls } = makePort({
            runId: 'unused',
            sessionId: 'unused',
            branchedFromRunId: null,
        });
        await strict_1.default.rejects(() => (0, branchRun_1.branchRun)(port, { parentRunId: 'run-1', message: '   ' }), /message is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === forwards optional model + checkpointId untouched to the port ===
    {
        const { port, calls } = makePort({
            runId: 'run-77',
            sessionId: 'sess-B',
            branchedFromRunId: 'run-1',
        });
        const result = await (0, branchRun_1.branchRun)(port, {
            parentRunId: 'run-1',
            message: 'branch from snapshot',
            model: 'claude-opus-4-7',
            checkpointId: 'ckpt_abc',
        });
        strict_1.default.equal(result.branchedFromRunId, 'run-1');
        strict_1.default.equal(calls[0]?.input.model, 'claude-opus-4-7');
        strict_1.default.equal(calls[0]?.input.checkpointId, 'ckpt_abc');
    }
    console.log('[contract] PASS branch-run (4 cases)');
}
void run();
