import assert from 'node:assert/strict';

import { rerunFromStep } from '../../src/renderer/application/run/rerunFromStep';
import type {
  RerunFromStepInput,
  RerunFromStepPort,
  RerunFromStepResult,
} from '../../src/renderer/application/run/rerunFromStepPort';

interface PortCall {
  readonly input: RerunFromStepInput;
}

function makePort(result: RerunFromStepResult): {
  port: RerunFromStepPort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: RerunFromStepPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards parentRunId/planNodeId and relays branchedFromRunId+rerunFromNodeId verbatim ===
  {
    const { port, calls } = makePort({
      runId: 'rerun-1',
      sessionId: 'sess-A',
      branchedFromRunId: 'parent-1',
      rerunFromNodeId: 'ds_workflow_plan/feature_engineering',
    });

    const result = await rerunFromStep(port, {
      parentRunId: 'parent-1',
      planNodeId: 'ds_workflow_plan/feature_engineering',
    });

    assert.equal(result.runId, 'rerun-1');
    assert.equal(result.sessionId, 'sess-A');
    assert.equal(result.branchedFromRunId, 'parent-1');
    assert.equal(result.rerunFromNodeId, 'ds_workflow_plan/feature_engineering');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.parentRunId, 'parent-1');
    assert.equal(calls[0]?.input.planNodeId, 'ds_workflow_plan/feature_engineering');
  }

  // === rejects empty parentRunId before reaching transport ===
  {
    const { port, calls } = makePort({
      runId: 'unused',
      sessionId: 'unused',
      branchedFromRunId: null,
      rerunFromNodeId: null,
    });
    await assert.rejects(
      () => rerunFromStep(port, { parentRunId: '   ', planNodeId: 'step' }),
      /parentRunId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === rejects empty planNodeId before reaching transport ===
  {
    const { port, calls } = makePort({
      runId: 'unused',
      sessionId: 'unused',
      branchedFromRunId: null,
      rerunFromNodeId: null,
    });
    await assert.rejects(
      () => rerunFromStep(port, { parentRunId: 'parent-1', planNodeId: '   ' }),
      /planNodeId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === forwards optional message + model untouched to the port ===
  {
    const { port, calls } = makePort({
      runId: 'rerun-7',
      sessionId: 'sess-B',
      branchedFromRunId: 'parent-2',
      rerunFromNodeId: 'modelling_node',
    });
    await rerunFromStep(port, {
      parentRunId: 'parent-2',
      planNodeId: 'modelling_node',
      message: 'redo with regularization',
      model: 'claude-opus-4-7',
    });

    assert.equal(calls[0]?.input.message, 'redo with regularization');
    assert.equal(calls[0]?.input.model, 'claude-opus-4-7');
  }

  console.log('[contract] PASS rerun-from-step (4 cases)');
}

void run();
