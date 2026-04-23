import assert from 'node:assert/strict';

import { saveCheckpoint } from '../../src/renderer/application/run/saveCheckpoint';
import type {
  SaveCheckpointInput,
  SaveCheckpointPort,
  SaveCheckpointResult,
} from '../../src/renderer/application/run/saveCheckpointPort';

interface PortCall {
  readonly input: SaveCheckpointInput;
}

function makePort(result: SaveCheckpointResult): {
  port: SaveCheckpointPort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: SaveCheckpointPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards sessionId/name/description untouched and surfaces createdAt as number ===
  {
    const { port, calls } = makePort({
      checkpointId: 'ckpt_abc',
      sessionId: 'sess-A',
      name: 'before fe',
      transcriptStep: 5,
      createdAt: 1734000000.5,
      description: 'snapshot before feature engineering',
    });

    const result = await saveCheckpoint(port, {
      sessionId: 'sess-A',
      name: 'before fe',
      description: 'snapshot before feature engineering',
    });

    assert.equal(result.checkpointId, 'ckpt_abc');
    assert.equal(result.name, 'before fe');
    assert.equal(result.transcriptStep, 5);
    assert.equal(typeof result.createdAt, 'number');
    assert.equal(result.createdAt, 1734000000.5);
    assert.equal(result.description, 'snapshot before feature engineering');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.sessionId, 'sess-A');
    assert.equal(calls[0]?.input.name, 'before fe');
    assert.equal(
      calls[0]?.input.description,
      'snapshot before feature engineering',
    );
  }

  // === rejects empty sessionId before reaching transport ===
  {
    const { port, calls } = makePort({
      checkpointId: 'unused',
      sessionId: 'unused',
      name: 'unused',
      transcriptStep: 0,
      createdAt: 0,
      description: null,
    });
    await assert.rejects(
      () => saveCheckpoint(port, { sessionId: '   ', name: 'x' }),
      /sessionId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === rejects empty name before reaching transport ===
  {
    const { port, calls } = makePort({
      checkpointId: 'unused',
      sessionId: 'unused',
      name: 'unused',
      transcriptStep: 0,
      createdAt: 0,
      description: null,
    });
    await assert.rejects(
      () => saveCheckpoint(port, { sessionId: 'sess-B', name: '   ' }),
      /name is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === passes through null description and surfaces transcriptStep verbatim ===
  {
    const { port } = makePort({
      checkpointId: 'ckpt_zero',
      sessionId: 'sess-C',
      name: 'mark zero',
      transcriptStep: 0,
      createdAt: 1,
      description: null,
    });
    const result = await saveCheckpoint(port, {
      sessionId: 'sess-C',
      name: 'mark zero',
    });

    assert.equal(result.transcriptStep, 0);
    assert.equal(result.description, null);
  }

  console.log('[contract] PASS save-checkpoint (4 cases)');
}

void run();
