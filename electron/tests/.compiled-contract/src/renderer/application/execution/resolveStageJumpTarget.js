"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveStageJumpTarget = resolveStageJumpTarget;
exports.buildArtifactAnchorId = buildArtifactAnchorId;
exports.buildCardAnchorId = buildCardAnchorId;
exports.buildMessageAnchorId = buildMessageAnchorId;
const UNAVAILABLE = Object.freeze({
    kind: 'unavailable',
    anchorId: null,
    artifact: null,
    available: false,
});
/**
 * Resolve where the "View results" link of a finished stage should jump.
 *
 * Artifact deep-links take precedence. Wave 2 adds result-card anchors between
 * artifact and message jumps so the execution timeline can land on structured
 * card output once cards exist. Pending/running stages keep a disabled control
 * instead of disappearing so keyboard Tab order stays stable.
 */
function resolveStageJumpTarget(stage, options = {}) {
    if (stage.status !== 'completed' && stage.status !== 'failed') {
        return UNAVAILABLE;
    }
    const artifact = stage.outcome?.detailRefs?.[0];
    if (artifact) {
        return Object.freeze({
            kind: 'artifact',
            anchorId: buildArtifactAnchorId(artifact),
            artifact,
            available: true,
        });
    }
    const cardId = options.latestResultCardId ?? null;
    if (cardId) {
        return Object.freeze({
            kind: 'card',
            anchorId: buildCardAnchorId(cardId),
            artifact: null,
            available: true,
        });
    }
    const messageId = options.latestAssistantMessageId ?? null;
    if (messageId) {
        return Object.freeze({
            kind: 'message',
            anchorId: buildMessageAnchorId(messageId),
            artifact: null,
            available: true,
        });
    }
    return UNAVAILABLE;
}
function buildArtifactAnchorId(artifact) {
    return `ds-artifact-${artifact.kind}-${artifact.id}`;
}
function buildCardAnchorId(cardId) {
    return `ds-result-card-${cardId}`;
}
function buildMessageAnchorId(messageId) {
    return `ds-chat-message-${messageId}`;
}
