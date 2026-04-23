import assert from 'node:assert/strict';

import type { MissionContextPatch } from '../../src/renderer/domain/mission';
import { subscribeToMissionContextUpdates } from '../../src/renderer/infrastructure/ws/wsMissionSubscriber';

type EventHandler = (payload: unknown) => void;

interface Bus {
  on(event: string, handler: EventHandler): () => void;
  emit(event: string, payload: unknown): void;
  listenerCount(event: string): number;
}

function createBus(): Bus {
  const listeners = new Map<string, Set<EventHandler>>();
  return {
    on(event, handler) {
      const set = listeners.get(event) ?? new Set<EventHandler>();
      set.add(handler);
      listeners.set(event, set);
      return () => {
        set.delete(handler);
        if (set.size === 0) {
          listeners.delete(event);
        }
      };
    },
    emit(event, payload) {
      for (const handler of listeners.get(event) ?? []) {
        handler(payload);
      }
    },
    listenerCount(event) {
      return listeners.get(event)?.size ?? 0;
    },
  };
}

interface SubscribeRecord {
  bus: Bus;
  unsubscribe: () => void;
}

function simulateLifecycle(): {
  records: SubscribeRecord[];
  received: MissionContextPatch[];
  resubscribe: (status: 'connecting' | 'connected' | 'disconnected') => void;
  teardown: () => void;
  bus: Bus;
} {
  const bus = createBus();
  const received: MissionContextPatch[] = [];
  const records: SubscribeRecord[] = [];

  function resubscribe(status: 'connecting' | 'connected' | 'disconnected') {
    while (records.length > 0) {
      const record = records.pop();
      record?.unsubscribe();
    }
    if (status !== 'connected') {
      return;
    }
    const unsubscribe = subscribeToMissionContextUpdates(bus.on, 'session-x', (patch) => {
      received.push(patch);
    });
    records.push({ bus, unsubscribe });
  }

  return {
    records,
    received,
    resubscribe,
    teardown() {
      while (records.length > 0) {
        records.pop()?.unsubscribe();
      }
    },
    bus,
  };
}

function run(): void {
  // First connect — single subscription wired.
  {
    const lifecycle = simulateLifecycle();
    lifecycle.resubscribe('connected');
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);

    lifecycle.bus.emit('mission.context.updated', {
      sessionId: 'session-x',
      stage: { current: 2, label: 'Analysis running' },
    });
    assert.deepEqual(lifecycle.received, [
      { stage: { current: 2, label: 'Analysis running' } },
    ]);

    lifecycle.teardown();
  }

  // Reconnect cycle — disconnect tears down listener, reconnect re-attaches exactly one.
  {
    const lifecycle = simulateLifecycle();
    lifecycle.resubscribe('connected');
    lifecycle.resubscribe('disconnected');
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);

    lifecycle.resubscribe('connecting');
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);

    lifecycle.resubscribe('connected');
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);

    lifecycle.bus.emit('mission.context.updated', {
      sessionId: 'session-x',
      mode: 'auto',
    });
    assert.deepEqual(lifecycle.received.at(-1), { mode: 'auto' });

    lifecycle.teardown();
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 0);
  }

  // Multiple reconnects do not stack listeners.
  {
    const lifecycle = simulateLifecycle();
    for (let i = 0; i < 5; i += 1) {
      lifecycle.resubscribe('disconnected');
      lifecycle.resubscribe('connected');
    }
    assert.equal(lifecycle.bus.listenerCount('mission.context.updated'), 1);
    lifecycle.teardown();
  }

  // sessionId scoping survives reconnect.
  {
    const lifecycle = simulateLifecycle();
    lifecycle.resubscribe('connected');

    lifecycle.bus.emit('mission.context.updated', {
      sessionId: 'session-other',
      mode: 'controlled',
    });
    lifecycle.bus.emit('mission.context.updated', {
      sessionId: 'session-x',
      mode: 'controlled',
    });

    assert.equal(lifecycle.received.length, 1);
    assert.deepEqual(lifecycle.received[0], { mode: 'controlled' });
    lifecycle.teardown();
  }

  console.log('[contract] PASS ws-mission-resubscribe (8 cases)');
}

run();
