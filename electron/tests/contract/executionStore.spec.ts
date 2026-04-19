import assert from 'node:assert/strict';

import {
  createExecutionState,
  reduceUpdateFromStatus,
  reduceSetModel,
  reduceSetCost,
  reduceSetConnected,
  type ExecutionMode,
} from '../../src/renderer/domain/execution/executionState';

function run(): void {
  // === createExecutionState defaults match historical agentStore ===
  {
    const state = createExecutionState();
    assert.equal(state.model, 'anthropic/claude-sonnet-4-6');
    assert.equal(state.qualityPreset, 'balanced');
    assert.equal(state.mode, 'auto');
    assert.equal(state.cost, 0);
    assert.equal(state.step, 0);
    assert.equal(state.activeSessions, 0);
    assert.equal(state.connected, false);
  }

  // === reduceSetModel returns a new state with updated model ===
  {
    const a = createExecutionState();
    const b = reduceSetModel(a, 'openai/gpt-5.4');
    assert.equal(a.model, 'anthropic/claude-sonnet-4-6', 'original immutable');
    assert.equal(b.model, 'openai/gpt-5.4');
    assert.notEqual(a, b);
  }

  // === reduceSetCost ===
  {
    const a = createExecutionState();
    const b = reduceSetCost(a, 1.234);
    assert.equal(b.cost, 1.234);
  }

  // === reduceSetConnected ===
  {
    const a = createExecutionState();
    const b = reduceSetConnected(a, true);
    assert.equal(b.connected, true);
    assert.equal(reduceSetConnected(b, false).connected, false);
  }

  // === reduceUpdateFromStatus picks known fields and falls back to current ===
  {
    const a = createExecutionState();
    const partial = {
      model: 'openai/gpt-5.4',
      qualityPreset: 'fast',
      mode: 'supervised' as ExecutionMode,
      activeSessions: 7,
    };
    const b = reduceUpdateFromStatus(a, partial as unknown as Record<string, unknown>);
    assert.equal(b.model, 'openai/gpt-5.4');
    assert.equal(b.qualityPreset, 'fast');
    assert.equal(b.mode, 'supervised');
    assert.equal(b.activeSessions, 7);
  }

  // === reduceUpdateFromStatus tolerates missing fields (preserves current) ===
  {
    const a = reduceSetModel(createExecutionState(), 'anthropic/claude-opus-4-7');
    const b = reduceUpdateFromStatus(a, {});
    assert.equal(b.model, 'anthropic/claude-opus-4-7');
    assert.equal(b.mode, 'auto');
  }

  // === reduceUpdateFromStatus normalises unknown qualityPreset to 'custom' (legacy) ===
  {
    const a = createExecutionState();
    const b = reduceUpdateFromStatus(a, { qualityPreset: 'gibberish' });
    assert.equal(b.qualityPreset, 'custom');
  }

  console.log('[contract] PASS execution-store reducers (7 cases)');
}

run();
