"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const listRunExportArtifacts_1 = require("../../src/renderer/application/workspace/listRunExportArtifacts");
async function run() {
    const portCalls = [];
    const port = async ({ runId }) => {
        portCalls.push(runId);
        return {
            runId,
            sessionId: 'session-1',
            files: [
                {
                    name: 'report.md',
                    path: 'report.md',
                    size: 256,
                    type: 'md',
                    modifiedAt: 1000,
                },
            ],
            exportCandidates: [
                {
                    name: 'report.md',
                    path: 'report.md',
                    type: 'md',
                    formats: ['docx', 'html', 'pdf'],
                },
            ],
        };
    };
    const result = await (0, listRunExportArtifacts_1.listRunExportArtifacts)(port, { runId: '  run-123  ' });
    strict_1.default.equal(portCalls[0], 'run-123');
    strict_1.default.equal(result.sessionId, 'session-1');
    strict_1.default.equal(result.exportCandidates[0]?.path, 'report.md');
    strict_1.default.deepEqual(result.exportCandidates[0]?.formats, ['docx', 'html', 'pdf']);
    await strict_1.default.rejects(() => (0, listRunExportArtifacts_1.listRunExportArtifacts)(port, { runId: '   ' }), /runId is required/);
    console.log('[contract] PASS list-run-export-artifacts (5 cases)');
}
void run();
