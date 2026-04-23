import assert from 'node:assert/strict';

import {
  getMissionBudgetState,
  getMissionConnectionStateFromWs,
  mergeMissionContext,
  type MissionContext,
  type MissionContextPatch,
} from '../../src/renderer/domain/mission';
import { subscribeToMissionContextUpdates } from '../../src/renderer/infrastructure/ws/wsMissionSubscriber';

const BASE_MISSION: MissionContext = {
  goal: {
    title: 'Reduce churn for premium users',
    successCriteria: ['Deliver retention analysis'],
  },
  dataSources: [
    { type: 'file', label: 'train.csv', rowCount: 1200 },
  ],
  deliverables: ['report'],
  constraints: {
    language: 'ko',
    requiresApproval: true,
    localOnlyModel: false,
  },
  stage: {
    current: 1,
    total: 4,
    label: 'Mission agreed',
  },
  mode: 'supervised',
  model: {
    primary: 'anthropic/claude-sonnet-4-6',
    fallbacks: ['openai/gpt-4.1'],
    capabilities: ['balanced_reasoning'],
  },
  budget: {
    spentUsd: 1.5,
    limitUsd: 10,
    elapsedSec: 30,
    nearLimit: false,
  },
  connection: {
    state: 'connected',
  },
};

type EventHandler = (payload: unknown) => void;

function createEventBus() {
  const listeners = new Map<string, Set<EventHandler>>();

  return {
    on(event: string, handler: EventHandler): () => void {
      const handlers = listeners.get(event) ?? new Set<EventHandler>();
      handlers.add(handler);
      listeners.set(event, handlers);

      return () => {
        handlers.delete(handler);
        if (handlers.size === 0) {
          listeners.delete(event);
        }
      };
    },
    emit(event: string, payload: unknown): void {
      for (const handler of listeners.get(event) ?? []) {
        handler(payload);
      }
    },
  };
}

function run(): void {
  {
    const merged = mergeMissionContext(BASE_MISSION, {
      stage: {
        current: 2,
        label: 'Analysis running',
      },
      budget: {
        spentUsd: 8.4,
        nearLimit: true,
      },
      model: {
        capabilities: ['deep_reasoning', 'richer_reports'],
      },
    });

    assert.equal(merged.stage.current, 2);
    assert.equal(merged.stage.total, 4);
    assert.equal(merged.stage.label, 'Analysis running');
    assert.equal(merged.budget.spentUsd, 8.4);
    assert.equal(merged.budget.limitUsd, 10);
    assert.deepEqual(merged.model.capabilities, ['deep_reasoning', 'richer_reports']);
  }

  {
    assert.equal(getMissionBudgetState(BASE_MISSION.budget), 'default');
    assert.equal(
      getMissionBudgetState({ ...BASE_MISSION.budget, spentUsd: 8.2, nearLimit: true }),
      'warning',
    );
    assert.equal(
      getMissionBudgetState({ ...BASE_MISSION.budget, spentUsd: 10, nearLimit: true }),
      'error',
    );
  }

  {
    assert.equal(getMissionConnectionStateFromWs('connected'), 'connected');
    assert.equal(getMissionConnectionStateFromWs('connecting'), 'reconnecting');
    assert.equal(getMissionConnectionStateFromWs('disconnected'), 'disconnected');
  }

  {
    const bus = createEventBus();
    const received: MissionContextPatch[] = [];

    const unsubscribe = subscribeToMissionContextUpdates(bus.on, 'session-a', (patch) => {
      received.push(patch);
    });

    bus.emit('mission.context.updated', {
      sessionId: 'session-b',
      stage: { current: 3, label: 'Wrong session' },
    });
    bus.emit('mission.context.updated', {
      sessionId: 'session-a',
      stage: { current: 2, label: 'Analysis running' },
    });

    assert.deepEqual(received, [{ stage: { current: 2, label: 'Analysis running' } }]);
    unsubscribe();
  }

  {
    const bus = createEventBus();
    let received: MissionContextPatch | null = null;

    subscribeToMissionContextUpdates(bus.on, 'session-a', (patch) => {
      received = patch;
    });

    bus.emit('mission.context.updated', {
      budget: { spentUsd: 2.1 },
      model: { primary: 'anthropic/claude-3-7-sonnet' },
    });

    assert.deepEqual(received, {
      budget: { spentUsd: 2.1 },
      model: { primary: 'anthropic/claude-3-7-sonnet' },
    });
  }

  {
    const bus = createEventBus();
    let called = false;

    subscribeToMissionContextUpdates(bus.on, 'session-a', () => {
      called = true;
    });

    bus.emit('mission.context.updated', null);
    bus.emit('mission.context.updated', 'not-an-object');

    assert.equal(called, false);
  }

  console.log('[contract] PASS mission-context (12 cases)');
}

run();
