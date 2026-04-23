"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const selectExecutionTimeline_1 = require("../../src/renderer/application/execution/selectExecutionTimeline");
const resolveStageJumpTarget_1 = require("../../src/renderer/application/execution/resolveStageJumpTarget");
const reducedMotion_1 = require("../../src/renderer/application/a11y/reducedMotion");
const stage_1 = require("../../src/renderer/domain/execution/stage");
function makeActivity(name, overrides = {}) {
    return {
        name,
        status: 'done',
        startedAt: 1000,
        ...overrides,
    };
}
function run() {
    // Every stage in STAGE_ORDER has an i18n labelKey so screen readers can
    // announce a translated stage name (no raw enum values).
    {
        const expectedPrefix = 'execution.stage.';
        for (const key of stage_1.STAGE_ORDER) {
            const meta = stage_1.STAGE_METADATA[key];
            strict_1.default.equal(meta.labelKey, `${expectedPrefix}${key}`, `Stage ${key} must expose i18n key ${expectedPrefix}${key}`);
            strict_1.default.ok(meta.label.length > 0, `Stage ${key} fallback label must be non-empty`);
        }
        strict_1.default.equal(stage_1.STAGE_ORDER.length, 10, 'Phase-1 stage taxonomy is 10 entries.');
    }
    // Reduced-motion utility returns false in non-DOM environments without throwing,
    // which lets StageRow / RawToolLog import the module from contract tests.
    {
        const reduce = (0, reducedMotion_1.prefersReducedMotion)();
        strict_1.default.equal(typeof reduce, 'boolean');
        // In Node test runtime, no matchMedia → expect false (no animation suppression).
        strict_1.default.equal(reduce, false);
    }
    // currentStage exposes the latest running stage so announce() targets it.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([
            makeActivity('read_file', { startedAt: 1 }),
            makeActivity('train_model', { status: 'running', startedAt: 2 }),
        ]);
        strict_1.default.ok(snap.currentStage, 'currentStage must be set when activity exists');
        strict_1.default.equal(snap.currentStage?.status, 'running');
        strict_1.default.equal(snap.latestTransition?.status, 'running');
    }
    // Disabled jump preserves Tab order (no anchor → kind=unavailable, available=false).
    {
        const target = (0, resolveStageJumpTarget_1.resolveStageJumpTarget)({ status: 'pending', outcome: undefined });
        strict_1.default.equal(target.available, false);
        strict_1.default.equal(target.kind, 'unavailable');
        strict_1.default.equal(target.anchorId, null);
    }
    // Anchor builders match ChatMessage / artifact id rendering.
    {
        strict_1.default.equal((0, resolveStageJumpTarget_1.buildMessageAnchorId)('msg-9'), 'ds-chat-message-msg-9');
        strict_1.default.equal((0, resolveStageJumpTarget_1.buildArtifactAnchorId)({ kind: 'plot', id: 'plot-7' }), 'ds-artifact-plot-plot-7');
    }
    console.log('[contract] PASS execution-timeline-a11y (15 cases)');
}
run();
