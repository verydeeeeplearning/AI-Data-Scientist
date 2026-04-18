import assert from 'node:assert/strict';

import {
  canAdvance,
  canClose,
  nextPhase,
} from '../../src/renderer/components/workflow/workObjectPanelModel';
import type { WorkObjectPhase } from '../../src/renderer/types/workObject';

function run(): void {
  // nextPhase: normal progression
  assert.equal(nextPhase('intake'), 'executing');
  assert.equal(nextPhase('executing'), 'review');
  assert.equal(nextPhase('review'), 'documenting');
  assert.equal(nextPhase('documenting'), 'followup');
  assert.equal(nextPhase('followup'), 'closed');

  // nextPhase: terminal phases return null
  assert.equal(nextPhase('closed'), null);
  assert.equal(nextPhase('failed'), null);

  // canAdvance: true for active phases
  const advanceable: WorkObjectPhase[] = ['intake', 'executing', 'review', 'documenting', 'followup'];
  for (const phase of advanceable) {
    assert.equal(canAdvance(phase), true, `canAdvance('${phase}') should be true`);
  }

  // canAdvance: false for terminal phases
  assert.equal(canAdvance('closed'), false);
  assert.equal(canAdvance('failed'), false);

  // canClose: true for all non-terminal phases
  for (const phase of advanceable) {
    assert.equal(canClose(phase), true, `canClose('${phase}') should be true`);
  }

  // canClose: false for terminal phases
  assert.equal(canClose('closed'), false);
  assert.equal(canClose('failed'), false);

  console.log('[contract] PASS work-object-mutations model');
}

run();
