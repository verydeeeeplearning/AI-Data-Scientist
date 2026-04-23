"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const listLineage_1 = require("../../src/renderer/application/run/listLineage");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards rootRunId and relays lineage payload verbatim ===
    {
        const { port, calls } = makePort({
            rootRunId: 'run-root',
            seedRunId: 'run-leaf',
            nodes: [
                {
                    runId: 'run-root',
                    sessionId: 'sess-A',
                    status: 'succeeded',
                    message: 'root',
                    createdAt: 1,
                    startedAt: 1,
                    finishedAt: 2,
                    branchedFromRunId: null,
                    rerunFromNodeId: null,
                    depth: 0,
                    isRoot: true,
                    isSeed: false,
                },
            ],
        });
        const result = await (0, listLineage_1.listLineage)(port, { rootRunId: 'run-leaf' });
        strict_1.default.equal(result.rootRunId, 'run-root');
        strict_1.default.equal(result.seedRunId, 'run-leaf');
        strict_1.default.equal(result.nodes.length, 1);
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.rootRunId, 'run-leaf');
    }
    // === rejects blank rootRunId before reaching transport ===
    {
        const { port, calls } = makePort({
            rootRunId: 'unused',
            seedRunId: 'unused',
            nodes: [],
        });
        await strict_1.default.rejects(() => (0, listLineage_1.listLineage)(port, { rootRunId: '   ' }), /rootRunId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    console.log('[contract] PASS list-lineage (2 cases)');
}
void run();
