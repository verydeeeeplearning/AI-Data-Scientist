import assert from 'node:assert/strict';

import {
  selectExecutionTimeline,
  transitionsEqual,
} from '../../src/renderer/application/execution/selectExecutionTimeline';
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
  // Empty input → empty snapshot.
  {
    const snap = selectExecutionTimeline([]);
    assert.equal(snap.stages.length, 0);
    assert.equal(snap.currentStage, null);
    assert.equal(snap.latestTransition, null);
    assert.equal(snap.hasActivity, false);
  }

  // Single completed stage → currentStage falls back to last stage.
  {
    const snap = selectExecutionTimeline([
      makeActivity('read_file', { result: 'Loaded 100 rows from a.csv' }),
    ]);
    assert.equal(snap.stages.length, 1);
    assert.equal(snap.currentStage?.key, 'data_loading');
    assert.equal(snap.currentStage?.status, 'completed');
    assert.equal(snap.latestTransition?.stageKey, 'data_loading');
    assert.equal(snap.latestTransition?.status, 'completed');
    assert.equal(snap.latestTransition?.toolEventCount, 1);
    assert.equal(snap.hasActivity, true);
  }

  // Running stage takes precedence over later completed/failed.
  {
    const snap = selectExecutionTimeline([
      makeActivity('read_file', { result: 'Loaded 1 file', startedAt: 1 }),
      makeActivity('train_model', { status: 'running', startedAt: 2 }),
      makeActivity('evaluate_model', { startedAt: 3 }),
    ]);
    assert.equal(snap.currentStage?.status, 'running');
    assert.equal(snap.currentStage?.key, 'baseline_modeling');
    assert.equal(snap.latestTransition?.status, 'running');
  }

  // Agent-control tools must not appear as stages.
  {
    const snap = selectExecutionTimeline([
      makeActivity('ask_user'),
      makeActivity('memory_search'),
      makeActivity('skill_search'),
    ]);
    assert.equal(snap.stages.length, 0, 'Pure agent-control input → no stages');
    assert.equal(snap.currentStage, null);
    assert.equal(snap.latestTransition, null);
    assert.equal(snap.hasActivity, true, 'hasActivity reflects raw activity input');
  }

  // Failed stage surfaces as the current stage if newest in order.
  {
    const snap = selectExecutionTimeline([
      makeActivity('read_file', { startedAt: 1 }),
      makeActivity('train_model', { status: 'error', startedAt: 2 }),
    ]);
    assert.equal(snap.currentStage?.key, 'baseline_modeling');
    assert.equal(snap.currentStage?.status, 'failed');
  }

  // Snapshot stability: identical inputs produce equal transitions.
  {
    const input: ToolActivityLike[] = [
      makeActivity('read_file', { startedAt: 1 }),
      makeActivity('run_eda', { status: 'running', startedAt: 2 }),
    ];
    const a = selectExecutionTimeline(input);
    const b = selectExecutionTimeline(input);
    assert.deepEqual(a.latestTransition, b.latestTransition);
    assert.equal(transitionsEqual(a.latestTransition, b.latestTransition), true);
  }

  // transitionsEqual contract.
  {
    assert.equal(transitionsEqual(null, null), true);
    assert.equal(
      transitionsEqual(null, { stageKey: 'eda', status: 'running', toolEventCount: 1 }),
      false,
    );
    assert.equal(
      transitionsEqual(
        { stageKey: 'eda', status: 'running', toolEventCount: 1 },
        { stageKey: 'eda', status: 'running', toolEventCount: 1 },
      ),
      true,
    );
    assert.equal(
      transitionsEqual(
        { stageKey: 'eda', status: 'running', toolEventCount: 1 },
        { stageKey: 'eda', status: 'completed', toolEventCount: 1 },
      ),
      false,
    );
    assert.equal(
      transitionsEqual(
        { stageKey: 'eda', status: 'running', toolEventCount: 1 },
        { stageKey: 'reporting', status: 'running', toolEventCount: 1 },
      ),
      false,
    );
  }

  console.log('[contract] PASS use-execution-timeline (22 cases)');
}

run();
