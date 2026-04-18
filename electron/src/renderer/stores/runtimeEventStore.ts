/**
 * Runtime event timeline state for operator alerts and recovery history.
 */

import { create } from 'zustand';

export interface RuntimeEventEntry {
  eventId: string;
  category: string;
  kind: string;
  severity: 'info' | 'success' | 'warning' | 'error';
  message: string;
  sessionId?: string | null;
  runId?: string | null;
  surface: string;
  source: string;
  metadata: Record<string, unknown>;
  createdAt: number;
}

interface RuntimeEventState {
  events: RuntimeEventEntry[];
  lastUpdatedAt: number | null;

  setEvents: (events: RuntimeEventEntry[]) => void;
  upsertEvent: (event: RuntimeEventEntry) => void;
  resetEvents: () => void;
}

function sortEvents(events: RuntimeEventEntry[]): RuntimeEventEntry[] {
  return [...events].sort((left, right) => {
    if (right.createdAt !== left.createdAt) {
      return right.createdAt - left.createdAt;
    }
    return right.eventId.localeCompare(left.eventId);
  });
}

export const useRuntimeEventStore = create<RuntimeEventState>((set) => ({
  events: [],
  lastUpdatedAt: null,

  setEvents: (events) => set({ events: sortEvents(events), lastUpdatedAt: Date.now() }),
  upsertEvent: (event) =>
    set((state) => ({
      events: sortEvents([
        event,
        ...state.events.filter((entry) => entry.eventId !== event.eventId),
      ]),
      lastUpdatedAt: Date.now(),
    })),
  resetEvents: () => set({ events: [], lastUpdatedAt: null }),
}));
