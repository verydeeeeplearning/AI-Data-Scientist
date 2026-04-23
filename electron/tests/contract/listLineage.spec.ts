import assert from 'node:assert/strict';

import { listLineage } from '../../src/renderer/application/run/listLineage';
import type {
  ListLineageInput,
  ListLineagePort,
  ListLineageResult,
} from '../../src/renderer/application/run/listLineagePort';

interface PortCall {
  readonly input: ListLineageInput;
}

function makePort(result: ListLineageResult): {
  port: ListLineagePort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: ListLineagePort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards rootRunId and relays lineage payload verbatim ===
  {
    const { port, calls } = makePort({
      rootRunId: 'run-root',
      seedRunId: 'run-leaf',
      nodes: [
        {
          runId: 'run-root',
          sessionId: 'sess-A',
          status: 'succeeded',
          message: 'root',
          createdAt: 1,
          startedAt: 1,
          finishedAt: 2,
          branchedFromRunId: null,
          rerunFromNodeId: null,
          depth: 0,
          isRoot: true,
          isSeed: false,
        },
      ],
    });

    const result = await listLineage(port, { rootRunId: 'run-leaf' });

    assert.equal(result.rootRunId, 'run-root');
    assert.equal(result.seedRunId, 'run-leaf');
    assert.equal(result.nodes.length, 1);
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.rootRunId, 'run-leaf');
  }

  // === rejects blank rootRunId before reaching transport ===
  {
    const { port, calls } = makePort({
      rootRunId: 'unused',
      seedRunId: 'unused',
      nodes: [],
    });

    await assert.rejects(
      () => listLineage(port, { rootRunId: '   ' }),
      /rootRunId is required/,
    );
    assert.equal(calls.length, 0);
  }

  console.log('[contract] PASS list-lineage (2 cases)');
}

void run();
