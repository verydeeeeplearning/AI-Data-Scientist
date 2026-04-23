import assert from 'node:assert/strict';

import { selectExecutionTimeline } from '../../src/renderer/application/execution/selectExecutionTimeline';
import {
  buildArtifactAnchorId,
  buildMessageAnchorId,
  resolveStageJumpTarget,
} from '../../src/renderer/application/execution/resolveStageJumpTarget';
import { prefersReducedMotion } from '../../src/renderer/application/a11y/reducedMotion';
import {
  STAGE_METADATA,
  STAGE_ORDER,
  type StageKey,
} from '../../src/renderer/domain/execution/stage';
import type { ToolActivityLike } from '../../src/renderer/application/execution/aggregateStages';

function makeActivity(
  name: string,
  overrides: Partial<ToolActivityLike> = {},
): ToolActivityLike {
  return {
    name,
    status: 'done',
    startedAt: 1_000,
    ...overrides,
  };
}

function run(): void {
  // Every stage in STAGE_ORDER has an i18n labelKey so screen readers can
  // announce a translated stage name (no raw enum values).
  {
    const expectedPrefix = 'execution.stage.';
    for (const key of STAGE_ORDER) {
      const meta = STAGE_METADATA[key as StageKey];
      assert.equal(
        meta.labelKey,
        `${expectedPrefix}${key}`,
        `Stage ${key} must expose i18n key ${expectedPrefix}${key}`,
      );
      assert.ok(meta.label.length > 0, `Stage ${key} fallback label must be non-empty`);
    }
    assert.equal(STAGE_ORDER.length, 10, 'Phase-1 stage taxonomy is 10 entries.');
  }

  // Reduced-motion utility returns false in non-DOM environments without throwing,
  // which lets StageRow / RawToolLog import the module from contract tests.
  {
    const reduce = prefersReducedMotion();
    assert.equal(typeof reduce, 'boolean');
    // In Node test runtime, no matchMedia → expect false (no animation suppression).
    assert.equal(reduce, false);
  }

  // currentStage exposes the latest running stage so announce() targets it.
  {
    const snap = selectExecutionTimeline([
      makeActivity('read_file', { startedAt: 1 }),
      makeActivity('train_model', { status: 'running', startedAt: 2 }),
    ]);
    assert.ok(snap.currentStage, 'currentStage must be set when activity exists');
    assert.equal(snap.currentStage?.status, 'running');
    assert.equal(snap.latestTransition?.status, 'running');
  }

  // Disabled jump preserves Tab order (no anchor → kind=unavailable, available=false).
  {
    const target = resolveStageJumpTarget({ status: 'pending', outcome: undefined });
    assert.equal(target.available, false);
    assert.equal(target.kind, 'unavailable');
    assert.equal(target.anchorId, null);
  }

  // Anchor builders match ChatMessage / artifact id rendering.
  {
    assert.equal(buildMessageAnchorId('msg-9'), 'ds-chat-message-msg-9');
    assert.equal(
      buildArtifactAnchorId({ kind: 'plot', id: 'plot-7' }),
      'ds-artifact-plot-plot-7',
    );
  }

  console.log('[contract] PASS execution-timeline-a11y (15 cases)');
}

run();
