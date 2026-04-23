"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const resumeFromCheckpoint_1 = require("../../src/renderer/application/run/resumeFromCheckpoint");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards sessionId/message/model untouched and surfaces resumed=true ===
    {
        const { port, calls } = makePort({
            resumed: true,
            runId: 'run-42',
            sessionId: 'sess-A',
        });
        const result = await (0, resumeFromCheckpoint_1.resumeFromCheckpoint)(port, {
            sessionId: 'sess-A',
            message: 'Resume the prior plan.',
            model: 'claude-opus-4-7',
        });
        strict_1.default.equal(result.resumed, true);
        strict_1.default.equal(result.runId, 'run-42');
        strict_1.default.equal(result.sessionId, 'sess-A');
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.sessionId, 'sess-A');
        strict_1.default.equal(calls[0]?.input.message, 'Resume the prior plan.');
        strict_1.default.equal(calls[0]?.input.model, 'claude-opus-4-7');
    }
    // === backend reports no checkpoint → use case faithfully relays resumed=false ===
    {
        const { port } = makePort({
            resumed: false,
            runId: 'run-77',
            sessionId: 'sess-B',
        });
        const result = await (0, resumeFromCheckpoint_1.resumeFromCheckpoint)(port, {
            sessionId: 'sess-B',
            message: 'Resume',
        });
        strict_1.default.equal(result.resumed, false);
        strict_1.default.equal(result.runId, 'run-77');
    }
    // === guards reject empty sessionId ===
    {
        const { port } = makePort({ resumed: true, runId: null, sessionId: '' });
        await strict_1.default.rejects(() => (0, resumeFromCheckpoint_1.resumeFromCheckpoint)(port, { sessionId: '   ', message: 'Resume' }), /sessionId is required/);
    }
    // === guards reject empty message ===
    {
        const { port } = makePort({ resumed: true, runId: null, sessionId: '' });
        await strict_1.default.rejects(() => (0, resumeFromCheckpoint_1.resumeFromCheckpoint)(port, { sessionId: 'sess-C', message: '   ' }), /message is required/);
    }
    console.log('[contract] PASS resume-from-checkpoint (4 cases)');
}
void run();
