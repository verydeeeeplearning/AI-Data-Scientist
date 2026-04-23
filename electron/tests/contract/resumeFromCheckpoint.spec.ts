import assert from 'node:assert/strict';

import { resumeFromCheckpoint } from '../../src/renderer/application/run/resumeFromCheckpoint';
import type {
  ResumeFromCheckpointInput,
  ResumeFromCheckpointPort,
  ResumeFromCheckpointResult,
} from '../../src/renderer/application/run/resumeFromCheckpointPort';

interface PortCall {
  readonly input: ResumeFromCheckpointInput;
}

function makePort(result: ResumeFromCheckpointResult): {
  port: ResumeFromCheckpointPort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: ResumeFromCheckpointPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards sessionId/message/model untouched and surfaces resumed=true ===
  {
    const { port, calls } = makePort({
      resumed: true,
      runId: 'run-42',
      sessionId: 'sess-A',
    });

    const result = await resumeFromCheckpoint(port, {
      sessionId: 'sess-A',
      message: 'Resume the prior plan.',
      model: 'claude-opus-4-7',
    });

    assert.equal(result.resumed, true);
    assert.equal(result.runId, 'run-42');
    assert.equal(result.sessionId, 'sess-A');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.sessionId, 'sess-A');
    assert.equal(calls[0]?.input.message, 'Resume the prior plan.');
    assert.equal(calls[0]?.input.model, 'claude-opus-4-7');
  }

  // === backend reports no checkpoint → use case faithfully relays resumed=false ===
  {
    const { port } = makePort({
      resumed: false,
      runId: 'run-77',
      sessionId: 'sess-B',
    });
    const result = await resumeFromCheckpoint(port, {
      sessionId: 'sess-B',
      message: 'Resume',
    });

    assert.equal(result.resumed, false);
    assert.equal(result.runId, 'run-77');
  }

  // === guards reject empty sessionId ===
  {
    const { port } = makePort({ resumed: true, runId: null, sessionId: '' });
    await assert.rejects(
      () => resumeFromCheckpoint(port, { sessionId: '   ', message: 'Resume' }),
      /sessionId is required/,
    );
  }

  // === guards reject empty message ===
  {
    const { port } = makePort({ resumed: true, runId: null, sessionId: '' });
    await assert.rejects(
      () => resumeFromCheckpoint(port, { sessionId: 'sess-C', message: '   ' }),
      /message is required/,
    );
  }

  console.log('[contract] PASS resume-from-checkpoint (4 cases)');
}

void run();
