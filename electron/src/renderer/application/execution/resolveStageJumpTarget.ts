import type { ArtifactRef, Stage } from '../../domain/execution/stage';

export type StageJumpKind = 'artifact' | 'card' | 'message' | 'unavailable';

export interface StageJumpTarget {
  readonly kind: StageJumpKind;
  readonly anchorId: string | null;
  readonly artifact: ArtifactRef | null;
  readonly available: boolean;
}

const UNAVAILABLE: StageJumpTarget = Object.freeze({
  kind: 'unavailable',
  anchorId: null,
  artifact: null,
  available: false,
});

export interface ResolveJumpOptions {
  readonly latestResultCardId?: string | null;
  readonly latestAssistantMessageId?: string | null;
}

/**
 * Resolve where the "View results" link of a finished stage should jump.
 *
 * Artifact deep-links take precedence. Wave 2 adds result-card anchors between
 * artifact and message jumps so the execution timeline can land on structured
 * card output once cards exist. Pending/running stages keep a disabled control
 * instead of disappearing so keyboard Tab order stays stable.
 */
export function resolveStageJumpTarget(
  stage: Pick<Stage, 'status' | 'outcome'>,
  options: ResolveJumpOptions = {},
): StageJumpTarget {
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

export function buildArtifactAnchorId(artifact: ArtifactRef): string {
  return `ds-artifact-${artifact.kind}-${artifact.id}`;
}

export function buildCardAnchorId(cardId: string): string {
  return `ds-result-card-${cardId}`;
}

export function buildMessageAnchorId(messageId: string): string {
  return `ds-chat-message-${messageId}`;
}
