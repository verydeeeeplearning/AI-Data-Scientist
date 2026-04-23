import assert from 'node:assert/strict';

import {
  buildArtifactAnchorId,
  buildCardAnchorId,
  buildMessageAnchorId,
  resolveStageJumpTarget,
} from '../../src/renderer/application/execution/resolveStageJumpTarget';
import type { Stage } from '../../src/renderer/domain/execution/stage';

function stage(overrides: Partial<Stage>): Pick<Stage, 'status' | 'outcome'> {
  return {
    status: 'completed',
    outcome: undefined,
    ...overrides,
  } as Pick<Stage, 'status' | 'outcome'>;
}

function run(): void {
  // Pending / running stages → unavailable jump.
  {
    const target = resolveStageJumpTarget(stage({ status: 'pending' }));
    assert.equal(target.kind, 'unavailable');
    assert.equal(target.available, false);
    assert.equal(target.anchorId, null);
    assert.equal(target.artifact, null);
  }
  {
    const target = resolveStageJumpTarget(stage({ status: 'running' }));
    assert.equal(target.kind, 'unavailable');
    assert.equal(target.available, false);
  }

  // Completed stage with artifact → artifact jump.
  {
    const target = resolveStageJumpTarget(
      stage({
        status: 'completed',
        outcome: {
          summary: 'Loaded 1 file.',
          detailRefs: [{ kind: 'plot', id: 'plot-1', label: 'Histogram' }],
        },
      }),
    );
    assert.equal(target.kind, 'artifact');
    assert.equal(target.available, true);
    assert.equal(target.artifact?.kind, 'plot');
    assert.equal(target.artifact?.id, 'plot-1');
    assert.equal(target.anchorId, 'ds-artifact-plot-plot-1');
  }

  // Completed stage without artifact, with assistant anchor → message jump.
  {
    const target = resolveStageJumpTarget(
      stage({ status: 'completed', outcome: { summary: 'done' } }),
      { latestAssistantMessageId: 'msg-42-abc' },
    );
    assert.equal(target.kind, 'message');
    assert.equal(target.available, true);
    assert.equal(target.anchorId, 'ds-chat-message-msg-42-abc');
    assert.equal(target.artifact, null);
  }

  // Completed stage without artifact, with result card ??card jump beats message jump.
  {
    const target = resolveStageJumpTarget(
      stage({ status: 'completed', outcome: { summary: 'done' } }),
      { latestResultCardId: 'card-42', latestAssistantMessageId: 'msg-42-abc' },
    );
    assert.equal(target.kind, 'card');
    assert.equal(target.available, true);
    assert.equal(target.anchorId, 'ds-result-card-card-42');
    assert.equal(target.artifact, null);
  }

  // Failed stage with artifact → still routes to artifact (failure may have logs).
  {
    const target = resolveStageJumpTarget(
      stage({
        status: 'failed',
        outcome: {
          summary: 'Failed with errors',
          detailRefs: [{ kind: 'message', id: 'msg-err-1' }],
        },
      }),
    );
    assert.equal(target.kind, 'artifact');
    assert.equal(target.anchorId, 'ds-artifact-message-msg-err-1');
  }

  // Completed stage with neither artifact nor assistant id → unavailable.
  {
    const target = resolveStageJumpTarget(
      stage({ status: 'completed', outcome: { summary: 'done' } }),
    );
    assert.equal(target.kind, 'unavailable');
    assert.equal(target.available, false);
  }

  // Anchor builders are deterministic.
  {
    assert.equal(
      buildArtifactAnchorId({ kind: 'file', id: 'fp-1' }),
      'ds-artifact-file-fp-1',
    );
    assert.equal(buildCardAnchorId('card-7'), 'ds-result-card-card-7');
    assert.equal(buildMessageAnchorId('msg-7'), 'ds-chat-message-msg-7');
  }

  console.log('[contract] PASS stage-outcome-link (18 cases)');
}

run();
