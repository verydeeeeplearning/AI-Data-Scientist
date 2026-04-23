import assert from 'node:assert/strict';

import { promoteToArtifact } from '../../src/renderer/application/run/promoteToArtifact';
import type {
  PromoteToArtifactInput,
  PromoteToArtifactPort,
  PromoteToArtifactResult,
} from '../../src/renderer/application/run/promoteToArtifactPort';

interface PortCall {
  readonly input: PromoteToArtifactInput;
}

function makePort(result: PromoteToArtifactResult): {
  port: PromoteToArtifactPort;
  calls: PortCall[];
} {
  const calls: PortCall[] = [];
  const port: PromoteToArtifactPort = async (input) => {
    calls.push({ input });
    return result;
  };
  return { port, calls };
}

async function run(): Promise<void> {
  // === forwards inputs and relays artifact metadata verbatim ===
  {
    const { port, calls } = makePort({
      artifactId: 'art_abc123',
      runId: 'run-1',
      cardId: 'RC-7',
      audience: 'exec',
      title: 'Q2 churn brief',
      createdAt: 1_700_000_000,
    });

    const result = await promoteToArtifact(port, {
      runId: 'run-1',
      cardId: 'RC-7',
      audience: 'exec',
      title: 'Q2 churn brief',
    });

    assert.equal(result.artifactId, 'art_abc123');
    assert.equal(result.audience, 'exec');
    assert.equal(result.title, 'Q2 churn brief');
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input.runId, 'run-1');
    assert.equal(calls[0]?.input.cardId, 'RC-7');
    assert.equal(calls[0]?.input.audience, 'exec');
    assert.equal(calls[0]?.input.title, 'Q2 churn brief');
  }

  // === rejects empty runId before reaching transport ===
  {
    const { port, calls } = makePort({
      artifactId: 'unused',
      runId: 'unused',
      cardId: 'unused',
      audience: 'ds',
      title: 'unused',
      createdAt: 0,
    });
    await assert.rejects(
      () =>
        promoteToArtifact(port, {
          runId: '   ',
          cardId: 'RC-1',
          audience: 'ds',
        }),
      /runId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === rejects empty cardId before reaching transport ===
  {
    const { port, calls } = makePort({
      artifactId: 'unused',
      runId: 'unused',
      cardId: 'unused',
      audience: 'ds',
      title: 'unused',
      createdAt: 0,
    });
    await assert.rejects(
      () =>
        promoteToArtifact(port, {
          runId: 'run-1',
          cardId: '   ',
          audience: 'ds',
        }),
      /cardId is required/,
    );
    assert.equal(calls.length, 0);
  }

  // === rejects unknown audience before reaching transport ===
  {
    const { port, calls } = makePort({
      artifactId: 'unused',
      runId: 'unused',
      cardId: 'unused',
      audience: 'ds',
      title: 'unused',
      createdAt: 0,
    });
    await assert.rejects(
      () =>
        promoteToArtifact(port, {
          runId: 'run-1',
          cardId: 'RC-1',
          // Cast at the boundary so we exercise the runtime validator.
          audience: 'board' as unknown as 'ds',
        }),
      /audience must be one of/,
    );
    assert.equal(calls.length, 0);
  }

  // === all three known audiences are accepted ===
  {
    const { port, calls } = makePort({
      artifactId: 'art_x',
      runId: 'run-1',
      cardId: 'RC-1',
      audience: 'ml',
      title: 'RC-1',
      createdAt: 0,
    });
    for (const audience of ['ds', 'exec', 'ml'] as const) {
      await promoteToArtifact(port, {
        runId: 'run-1',
        cardId: 'RC-1',
        audience,
      });
    }
    assert.equal(calls.length, 3);
    assert.deepEqual(
      calls.map((call) => call.input.audience),
      ['ds', 'exec', 'ml'],
    );
  }

  console.log('[contract] PASS promote-to-artifact (5 cases)');
}

void run();
