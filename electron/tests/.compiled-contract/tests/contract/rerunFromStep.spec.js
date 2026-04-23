"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const rerunFromStep_1 = require("../../src/renderer/application/run/rerunFromStep");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards parentRunId/planNodeId and relays branchedFromRunId+rerunFromNodeId verbatim ===
    {
        const { port, calls } = makePort({
            runId: 'rerun-1',
            sessionId: 'sess-A',
            branchedFromRunId: 'parent-1',
            rerunFromNodeId: 'ds_workflow_plan/feature_engineering',
        });
        const result = await (0, rerunFromStep_1.rerunFromStep)(port, {
            parentRunId: 'parent-1',
            planNodeId: 'ds_workflow_plan/feature_engineering',
        });
        strict_1.default.equal(result.runId, 'rerun-1');
        strict_1.default.equal(result.sessionId, 'sess-A');
        strict_1.default.equal(result.branchedFromRunId, 'parent-1');
        strict_1.default.equal(result.rerunFromNodeId, 'ds_workflow_plan/feature_engineering');
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.parentRunId, 'parent-1');
        strict_1.default.equal(calls[0]?.input.planNodeId, 'ds_workflow_plan/feature_engineering');
    }
    // === rejects empty parentRunId before reaching transport ===
    {
        const { port, calls } = makePort({
            runId: 'unused',
            sessionId: 'unused',
            branchedFromRunId: null,
            rerunFromNodeId: null,
        });
        await strict_1.default.rejects(() => (0, rerunFromStep_1.rerunFromStep)(port, { parentRunId: '   ', planNodeId: 'step' }), /parentRunId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === rejects empty planNodeId before reaching transport ===
    {
        const { port, calls } = makePort({
            runId: 'unused',
            sessionId: 'unused',
            branchedFromRunId: null,
            rerunFromNodeId: null,
        });
        await strict_1.default.rejects(() => (0, rerunFromStep_1.rerunFromStep)(port, { parentRunId: 'parent-1', planNodeId: '   ' }), /planNodeId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === forwards optional message + model untouched to the port ===
    {
        const { port, calls } = makePort({
            runId: 'rerun-7',
            sessionId: 'sess-B',
            branchedFromRunId: 'parent-2',
            rerunFromNodeId: 'modelling_node',
        });
        await (0, rerunFromStep_1.rerunFromStep)(port, {
            parentRunId: 'parent-2',
            planNodeId: 'modelling_node',
            message: 'redo with regularization',
            model: 'claude-opus-4-7',
        });
        strict_1.default.equal(calls[0]?.input.message, 'redo with regularization');
        strict_1.default.equal(calls[0]?.input.model, 'claude-opus-4-7');
    }
    console.log('[contract] PASS rerun-from-step (4 cases)');
}
void run();
