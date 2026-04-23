"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const resolveStageJumpTarget_1 = require("../../src/renderer/application/execution/resolveStageJumpTarget");
function stage(overrides) {
    return {
        status: 'completed',
        outcome: undefined,
        ...overrides,
    };
}
function run() {
    // Pending / running stages → unavailable jump.
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({ status: 'pending' }));
        strict_1.default.equal(target.kind, 'unavailable');
        strict_1.default.equal(target.available, false);
        strict_1.default.equal(target.anchorId, null);
        strict_1.default.equal(target.artifact, null);
    }
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({ status: 'running' }));
        strict_1.default.equal(target.kind, 'unavailable');
        strict_1.default.equal(target.available, false);
    }
    // Completed stage with artifact → artifact jump.
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({
            status: 'completed',
            outcome: {
                summary: 'Loaded 1 file.',
                detailRefs: [{ kind: 'plot', id: 'plot-1', label: 'Histogram' }],
            },
        }));
        strict_1.default.equal(target.kind, 'artifact');
        strict_1.default.equal(target.available, true);
        strict_1.default.equal(target.artifact?.kind, 'plot');
        strict_1.default.equal(target.artifact?.id, 'plot-1');
        strict_1.default.equal(target.anchorId, 'ds-artifact-plot-plot-1');
    }
    // Completed stage without artifact, with assistant anchor → message jump.
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({ status: 'completed', outcome: { summary: 'done' } }), { latestAssistantMessageId: 'msg-42-abc' });
        strict_1.default.equal(target.kind, 'message');
        strict_1.default.equal(target.available, true);
        strict_1.default.equal(target.anchorId, 'ds-chat-message-msg-42-abc');
        strict_1.default.equal(target.artifact, null);
    }
    // Completed stage without artifact, with result card ??card jump beats message jump.
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({ status: 'completed', outcome: { summary: 'done' } }), { latestResultCardId: 'card-42', latestAssistantMessageId: 'msg-42-abc' });
        strict_1.default.equal(target.kind, 'card');
        strict_1.default.equal(target.available, true);
        strict_1.default.equal(target.anchorId, 'ds-result-card-card-42');
        strict_1.default.equal(target.artifact, null);
    }
    // Failed stage with artifact → still routes to artifact (failure may have logs).
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({
            status: 'failed',
            outcome: {
                summary: 'Failed with errors',
                detailRefs: [{ kind: 'message', id: 'msg-err-1' }],
            },
        }));
        strict_1.default.equal(target.kind, 'artifact');
        strict_1.default.equal(target.anchorId, 'ds-artifact-message-msg-err-1');
    }
    // Completed stage with neither artifact nor assistant id → unavailable.
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)(stage({ status: 'completed', outcome: { summary: 'done' } }));
        strict_1.default.equal(target.kind, 'unavailable');
        strict_1.default.equal(target.available, false);
    }
    // Anchor builders are deterministic.
    {
        strict_1.default.equal((0, resolveStageJumpTarget_1.buildArtifactAnchorId)({ kind: 'file', id: 'fp-1' }), 'ds-artifact-file-fp-1');
        strict_1.default.equal((0, resolveStageJumpTarget_1.buildCardAnchorId)('card-7'), 'ds-result-card-card-7');
        strict_1.default.equal((0, resolveStageJumpTarget_1.buildMessageAnchorId)('msg-7'), 'ds-chat-message-msg-7');
    }
    console.log('[contract] PASS stage-outcome-link (18 cases)');
}
run();
