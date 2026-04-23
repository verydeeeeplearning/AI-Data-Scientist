import assert from 'node:assert/strict';

import { branchRun } from '../../src/renderer/application/run/branchRun';
import type {
  BranchRunInput,
  BranchRunPort,
  BranchRunResult,
} from '../../src/renderer/application/run/branchRunPort';

interface PortCall {
  readonly input: BranchRunInput;
}

function makePort(result: BranchRunResult): {
  port: BranchRunPort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: BranchRunPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards parentRunId/message and relays branchedFromRunId verbatim ===
  {
    const { port, calls } = makePort({
      runId: 'run-99',
      sessionId: 'sess-A',
      branchedFromRunId: 'run-42',
    });

    const result = await branchRun(port, {
      parentRunId: 'run-42',
      message: 'explore alternative model',
    });

    assert.equal(result.runId, 'run-99');
    assert.equal(result.sessionId, 'sess-A');
    assert.equal(result.branchedFromRunId, 'run-42');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.parentRunId, 'run-42');
    assert.equal(calls[0]?.input.message, 'explore alternative model');
  }

  // === rejects empty parentRunId before reaching transport ===
  {
    const { port, calls } = makePort({
      runId: 'unused',
      sessionId: 'unused',
      branchedFromRunId: null,
    });
    await assert.rejects(
      () => branchRun(port, { parentRunId: '   ', message: 'hi' }),
      /parentRunId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === rejects empty message before reaching transport ===
  {
    const { port, calls } = makePort({
      runId: 'unused',
      sessionId: 'unused',
      branchedFromRunId: null,
    });
    await assert.rejects(
      () => branchRun(port, { parentRunId: 'run-1', message: '   ' }),
      /message is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === forwards optional model + checkpointId untouched to the port ===
  {
    const { port, calls } = makePort({
      runId: 'run-77',
      sessionId: 'sess-B',
      branchedFromRunId: 'run-1',
    });
    const result = await branchRun(port, {
      parentRunId: 'run-1',
      message: 'branch from snapshot',
      model: 'claude-opus-4-7',
      checkpointId: 'ckpt_abc',
    });

    assert.equal(result.branchedFromRunId, 'run-1');
    assert.equal(calls[0]?.input.model, 'claude-opus-4-7');
    assert.equal(calls[0]?.input.checkpointId, 'ckpt_abc');
  }

  console.log('[contract] PASS branch-run (4 cases)');
}

void run();
