"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const saveCheckpoint_1 = require("../../src/renderer/application/run/saveCheckpoint");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards sessionId/name/description untouched and surfaces createdAt as number ===
    {
        const { port, calls } = makePort({
            checkpointId: 'ckpt_abc',
            sessionId: 'sess-A',
            name: 'before fe',
            transcriptStep: 5,
            createdAt: 1734000000.5,
            description: 'snapshot before feature engineering',
        });
        const result = await (0, saveCheckpoint_1.saveCheckpoint)(port, {
            sessionId: 'sess-A',
            name: 'before fe',
            description: 'snapshot before feature engineering',
        });
        strict_1.default.equal(result.checkpointId, 'ckpt_abc');
        strict_1.default.equal(result.name, 'before fe');
        strict_1.default.equal(result.transcriptStep, 5);
        strict_1.default.equal(typeof result.createdAt, 'number');
        strict_1.default.equal(result.createdAt, 1734000000.5);
        strict_1.default.equal(result.description, 'snapshot before feature engineering');
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.sessionId, 'sess-A');
        strict_1.default.equal(calls[0]?.input.name, 'before fe');
        strict_1.default.equal(calls[0]?.input.description, 'snapshot before feature engineering');
    }
    // === rejects empty sessionId before reaching transport ===
    {
        const { port, calls } = makePort({
            checkpointId: 'unused',
            sessionId: 'unused',
            name: 'unused',
            transcriptStep: 0,
            createdAt: 0,
            description: null,
        });
        await strict_1.default.rejects(() => (0, saveCheckpoint_1.saveCheckpoint)(port, { sessionId: '   ', name: 'x' }), /sessionId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === rejects empty name before reaching transport ===
    {
        const { port, calls } = makePort({
            checkpointId: 'unused',
            sessionId: 'unused',
            name: 'unused',
            transcriptStep: 0,
            createdAt: 0,
            description: null,
        });
        await strict_1.default.rejects(() => (0, saveCheckpoint_1.saveCheckpoint)(port, { sessionId: 'sess-B', name: '   ' }), /name is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === passes through null description and surfaces transcriptStep verbatim ===
    {
        const { port } = makePort({
            checkpointId: 'ckpt_zero',
            sessionId: 'sess-C',
            name: 'mark zero',
            transcriptStep: 0,
            createdAt: 1,
            description: null,
        });
        const result = await (0, saveCheckpoint_1.saveCheckpoint)(port, {
            sessionId: 'sess-C',
            name: 'mark zero',
        });
        strict_1.default.equal(result.transcriptStep, 0);
        strict_1.default.equal(result.description, null);
    }
    console.log('[contract] PASS save-checkpoint (4 cases)');
}
void run();
