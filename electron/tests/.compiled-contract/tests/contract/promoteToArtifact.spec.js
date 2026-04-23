"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const promoteToArtifact_1 = require("../../src/renderer/application/run/promoteToArtifact");
function makePort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
async function run() {
    // === forwards inputs and relays artifact metadata verbatim ===
    {
        const { port, calls } = makePort({
            artifactId: 'art_abc123',
            runId: 'run-1',
            cardId: 'RC-7',
            audience: 'exec',
            title: 'Q2 churn brief',
            createdAt: 1700000000,
        });
        const result = await (0, promoteToArtifact_1.promoteToArtifact)(port, {
            runId: 'run-1',
            cardId: 'RC-7',
            audience: 'exec',
            title: 'Q2 churn brief',
        });
        strict_1.default.equal(result.artifactId, 'art_abc123');
        strict_1.default.equal(result.audience, 'exec');
        strict_1.default.equal(result.title, 'Q2 churn brief');
        strict_1.default.equal(calls.length, 1);
        strict_1.default.equal(calls[0]?.input.runId, 'run-1');
        strict_1.default.equal(calls[0]?.input.cardId, 'RC-7');
        strict_1.default.equal(calls[0]?.input.audience, 'exec');
        strict_1.default.equal(calls[0]?.input.title, 'Q2 churn brief');
    }
    // === rejects empty runId before reaching transport ===
    {
        const { port, calls } = makePort({
            artifactId: 'unused',
            runId: 'unused',
            cardId: 'unused',
            audience: 'ds',
            title: 'unused',
            createdAt: 0,
        });
        await strict_1.default.rejects(() => (0, promoteToArtifact_1.promoteToArtifact)(port, {
            runId: '   ',
            cardId: 'RC-1',
            audience: 'ds',
        }), /runId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === rejects empty cardId before reaching transport ===
    {
        const { port, calls } = makePort({
            artifactId: 'unused',
            runId: 'unused',
            cardId: 'unused',
            audience: 'ds',
            title: 'unused',
            createdAt: 0,
        });
        await strict_1.default.rejects(() => (0, promoteToArtifact_1.promoteToArtifact)(port, {
            runId: 'run-1',
            cardId: '   ',
            audience: 'ds',
        }), /cardId is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === rejects unknown audience before reaching transport ===
    {
        const { port, calls } = makePort({
            artifactId: 'unused',
            runId: 'unused',
            cardId: 'unused',
            audience: 'ds',
            title: 'unused',
            createdAt: 0,
        });
        await strict_1.default.rejects(() => (0, promoteToArtifact_1.promoteToArtifact)(port, {
            runId: 'run-1',
            cardId: 'RC-1',
            // Cast at the boundary so we exercise the runtime validator.
            audience: 'board',
        }), /audience must be one of/);
        strict_1.default.equal(calls.length, 0);
    }
    // === all three known audiences are accepted ===
    {
        const { port, calls } = makePort({
            artifactId: 'art_x',
            runId: 'run-1',
            cardId: 'RC-1',
            audience: 'ml',
            title: 'RC-1',
            createdAt: 0,
        });
        for (const audience of ['ds', 'exec', 'ml']) {
            await (0, promoteToArtifact_1.promoteToArtifact)(port, {
                runId: 'run-1',
                cardId: 'RC-1',
                audience,
            });
        }
        strict_1.default.equal(calls.length, 3);
        strict_1.default.deepEqual(calls.map((call) => call.input.audience), ['ds', 'exec', 'ml']);
    }
    console.log('[contract] PASS promote-to-artifact (5 cases)');
}
void run();
