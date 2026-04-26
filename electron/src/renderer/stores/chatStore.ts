/**
 * Chat state and result-card hydration store.
 */

import { create } from 'zustand';
import type {
  ResultCardSourcePayload,
  ResultCardType,
  StreamDoneEvent,
} from '../types/events';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  truncated?: boolean;
}

export interface PersistedChatMessage {
  messageId?: string;
  role: string;
  content: string;
}

export interface ResultCardSource extends ResultCardSourcePayload {
  toolCallId?: string | null;
}

export interface ResultCardRecord {
  cardId: string;
  resultId: string;
  type: ResultCardType;
  createdAt: number;
  source: ResultCardSource;
  trustStrip?: Record<string, unknown> | null;
  pinned: boolean;
  archived: boolean;
  [key: string]: unknown;
}

export interface ChatHistorySnapshot {
  messages: PersistedChatMessage[];
  cards: ResultCardRecord[];
}

export interface NormalizedStreamDonePayload extends Omit<StreamDoneEvent, 'cards'> {
  cards: ResultCardRecord[];
}

export interface ToolActivity {
  name: string;
  status: 'running' | 'done' | 'error';
  args?: Record<string, unknown>;
  result?: string;
  elapsed?: number;
  startedAt: number;
}

interface ChatState {
  messages: ChatMessage[];
  toolActivities: ToolActivity[];
  isStreaming: boolean;
  streamBuffer: string;
  sessionId: string | null;
  cardsById: Record<string, ResultCardRecord>;
  cardIdsByMessageId: Record<string, string[]>;
  /** Mission-level goal string, displayed in MissionContextBar. */
  goal: string | null;
  /** Wall-clock timestamp of the first user message in the current session. */
  startedAt: number | null;
  /** Assistant messages received while FloatingChat was collapsed. */
  unreadCount: number;

  // Actions
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendStreamDelta: (token: string, expectedMessageId?: string) => void;
  finalizeStream: (
    content: string,
    messageId?: string | null,
    expectedMessageId?: string,
  ) => boolean;
  setStreaming: (v: boolean) => void;
  setSessionId: (id: string) => void;
  setGoal: (goal: string | null) => void;
  markAllRead: () => void;
  markLastAssistantTruncated: (expectedMessageId?: string | null) => void;
  upsertCards: (cards: ResultCardRecord[]) => void;
  replaceConversation: (
    messages: PersistedChatMessage[],
    sessionId: string,
    cards?: ResultCardRecord[],
  ) => void;

  addToolActivity: (name: string, args?: Record<string, unknown>) => void;
  completeToolActivity: (
    name: string,
    success: boolean,
    elapsed?: number,
    result?: string,
  ) => void;
  markRunningToolsCancelled: () => void;
  clearToolActivities: () => void;

  resetConversation: (keepSessionId?: boolean) => void;
  clearMessages: () => void;
}

const RESULT_CARD_TYPES = new Set<ResultCardType>([
  'insight',
  'experiment',
  'risk',
  'artifact',
  'other',
]);

let msgCounter = 0;

function nextMsgId(): string {
  return `msg-${++msgCounter}-${Date.now().toString(36)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function normalizeCardId(payload: Record<string, unknown>): string | null {
  if (isNonEmptyString(payload.cardId)) {
    return payload.cardId;
  }
  if (isNonEmptyString(payload.id)) {
    return payload.id;
  }
  return null;
}

function normalizeResultId(payload: Record<string, unknown>, cardId: string): string {
  if (isNonEmptyString(payload.resultId)) {
    return payload.resultId;
  }
  return cardId;
}

function normalizeCreatedAt(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (!isNonEmptyString(value)) {
    return null;
  }

  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric;
  }

  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed / 1000 : null;
}

function normalizeCardSource(
  value: unknown,
  messageIdFallback?: string | null,
): ResultCardSource | null {
  if (!isRecord(value) || !isNonEmptyString(value.runId)) {
    return null;
  }

  const messageId = isNonEmptyString(value.messageId)
    ? value.messageId
    : (isNonEmptyString(messageIdFallback) ? messageIdFallback : null);
  if (!messageId) {
    return null;
  }

  return {
    messageId,
    runId: value.runId,
    toolCallId: isNonEmptyString(value.toolCallId) ? value.toolCallId : null,
  };
}

function normalizeResultCardType(value: unknown): ResultCardType {
  if (isNonEmptyString(value) && RESULT_CARD_TYPES.has(value as ResultCardType)) {
    return value as ResultCardType;
  }
  return 'other';
}

function sortCards(cards: ResultCardRecord[]): ResultCardRecord[] {
  return [...cards].sort((left, right) => {
    if (left.createdAt !== right.createdAt) {
      return left.createdAt - right.createdAt;
    }
    return left.cardId.localeCompare(right.cardId);
  });
}

function indexCardsByMessageId(
  cardsById: Record<string, ResultCardRecord>,
): Record<string, string[]> {
  const next: Record<string, string[]> = {};
  for (const card of sortCards(Object.values(cardsById))) {
    const messageId = card.source.messageId;
    next[messageId] = [...(next[messageId] ?? []), card.cardId];
  }
  return next;
}

function buildCardState(cards: ResultCardRecord[]) {
  const cardsById: Record<string, ResultCardRecord> = {};
  for (const card of cards) {
    cardsById[card.cardId] = card;
  }
  return {
    cardsById,
    cardIdsByMessageId: indexCardsByMessageId(cardsById),
  };
}

interface NormalizedHistoryMessageRecord {
  message: PersistedChatMessage | null;
  cards: ResultCardRecord[];
}

function normalizeHistoryMessageRecord(item: unknown): NormalizedHistoryMessageRecord {
  if (!isRecord(item)) {
    return { message: null, cards: [] };
  }

  const messageId = isNonEmptyString(item.messageId) ? item.messageId : undefined;
  return {
    message: {
      messageId,
      role: typeof item.role === 'string' ? item.role : 'assistant',
      content: typeof item.content === 'string' ? item.content : '',
    },
    cards: normalizeResultCardCollection(item.cards, { messageIdFallback: messageId ?? null }),
  };
}

export function normalizeResultCardPayload(
  payload: unknown,
  options: { messageIdFallback?: string | null } = {},
): ResultCardRecord | null {
  if (!isRecord(payload)) {
    return null;
  }

  const cardId = normalizeCardId(payload);
  if (!cardId) {
    return null;
  }

  const source = normalizeCardSource(payload.source, options.messageIdFallback);
  if (!source) {
    return null;
  }

  const normalized: ResultCardRecord = {
    ...payload,
    cardId,
    resultId: normalizeResultId(payload, cardId),
    type: normalizeResultCardType(payload.type),
    createdAt: normalizeCreatedAt(payload.createdAt) ?? Date.now() / 1000,
    source,
    trustStrip: isRecord(payload.trustStrip) ? payload.trustStrip : null,
    pinned: payload.pinned === true,
    archived: payload.archived === true,
  };

  delete (normalized as Record<string, unknown>).id;
  return normalized;
}

export function normalizeResultCardCollection(
  payload: unknown,
  options: { messageIdFallback?: string | null } = {},
): ResultCardRecord[] {
  if (!Array.isArray(payload)) {
    return [];
  }

  const cardsById: Record<string, ResultCardRecord> = {};
  for (const item of payload) {
    const card = normalizeResultCardPayload(item, options);
    if (card) {
      cardsById[card.cardId] = card;
    }
  }
  return sortCards(Object.values(cardsById));
}

export function normalizeStreamDonePayload(payload: unknown): NormalizedStreamDonePayload {
  if (!isRecord(payload)) {
    return { content: '', messageId: null, cards: [] };
  }

  const messageId = isNonEmptyString(payload.messageId) ? payload.messageId : null;
  const normalized: NormalizedStreamDonePayload = {
    content: typeof payload.content === 'string' ? payload.content : '',
    messageId,
    cards: normalizeResultCardCollection(payload.cards, { messageIdFallback: messageId }),
  };

  if (typeof payload.cost === 'number' && Number.isFinite(payload.cost)) {
    normalized.cost = payload.cost;
  }

  return normalized;
}

export function normalizeChatHistoryPayload(payload: unknown): ChatHistorySnapshot {
  if (!isRecord(payload)) {
    return { messages: [], cards: [] };
  }

  const messages: PersistedChatMessage[] = [];
  const cardsById: Record<string, ResultCardRecord> = {};

  if (Array.isArray(payload.messages)) {
    for (const item of payload.messages) {
      const normalized = normalizeHistoryMessageRecord(item);
      if (normalized.message && normalized.message.content.length > 0) {
        messages.push(normalized.message);
      }
      for (const card of normalized.cards) {
        cardsById[card.cardId] = card;
      }
    }
  }

  for (const card of normalizeResultCardCollection(payload.cards)) {
    cardsById[card.cardId] = card;
  }

  return {
    messages,
    cards: sortCards(Object.values(cardsById)),
  };
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  toolActivities: [],
  isStreaming: false,
  streamBuffer: '',
  sessionId: null,
  cardsById: {},
  cardIdsByMessageId: {},
  goal: null,
  startedAt: null,
  unreadCount: 0,

  addUserMessage: (content) => {
    const id = nextMsgId();
    set((s) => ({
      messages: [...s.messages, {
        id,
        role: 'user',
        content,
        timestamp: Date.now(),
      }],
      startedAt: s.startedAt ?? Date.now(),
      // user just typed → presumably looking at chat → reset unread
      unreadCount: 0,
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = nextMsgId();
    set((s) => ({
      messages: [...s.messages, {
        id,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }],
      streamBuffer: '',
      isStreaming: true,
    }));
    return id;
  },

  appendStreamDelta: (token, expectedMessageId) => {
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length === 0) {
        return s;
      }
      const last = msgs[msgs.length - 1];
      if (last.role !== 'assistant') {
        return s;
      }
      if (expectedMessageId !== undefined && last.id !== expectedMessageId) {
        return s;
      }
      msgs[msgs.length - 1] = {
        ...last,
        content: last.content + token,
      };
      return { messages: msgs, streamBuffer: s.streamBuffer + token };
    });
  },

  finalizeStream: (content, messageId, expectedMessageId) => {
    let finalized = false;
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
        const last = msgs[msgs.length - 1];
        if (expectedMessageId !== undefined && last.id !== expectedMessageId) {
          return s;
        }
        msgs[msgs.length - 1] = {
          ...last,
          id: typeof messageId === 'string' && messageId.length > 0
            ? messageId
            : last.id,
          content,
          truncated: false,
        };
        finalized = true;
      }
      return {
        messages: msgs,
        isStreaming: false,
        streamBuffer: '',
        // assistant message landed; bump unread (FloatingChat resets when visible)
        unreadCount: s.unreadCount + 1,
      };
    });
    return finalized;
  },

  setStreaming: (v) => set({ isStreaming: v }),
  setSessionId: (id) => set({ sessionId: id }),
  setGoal: (goal) => set({ goal }),
  markAllRead: () => set({ unreadCount: 0 }),
  markLastAssistantTruncated: (expectedMessageId) => {
    set((s) => {
      const msgs = [...s.messages];
      for (let index = msgs.length - 1; index >= 0; index -= 1) {
        const message = msgs[index];
        if (message.role !== 'assistant') {
          continue;
        }
        if (
          expectedMessageId != null
          && message.id !== expectedMessageId
        ) {
          return s;
        }
        if (message.truncated === true) {
          return s;
        }
        msgs[index] = { ...message, truncated: true };
        return { messages: msgs };
      }
      return s;
    });
  },

  upsertCards: (cards) => {
    if (cards.length === 0) {
      return;
    }

    set((s) => {
      const cardsById = { ...s.cardsById };
      for (const card of cards) {
        cardsById[card.cardId] = {
          ...(cardsById[card.cardId] ?? {}),
          ...card,
        };
      }
      return {
        cardsById,
        cardIdsByMessageId: indexCardsByMessageId(cardsById),
      };
    });
  },

  replaceConversation: (messages, sessionId, cards = []) =>
    set({
      messages: messages.map((message, index) => ({
        id: typeof message.messageId === 'string' && message.messageId.length > 0
          ? message.messageId
          : nextMsgId(),
        role: message.role === 'user' ? 'user' : 'assistant',
        content: message.content,
        timestamp: Date.now() + index,
      })),
      ...buildCardState(cards),
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId,
      unreadCount: 0,
      startedAt: messages.length > 0 ? Date.now() : null,
    }),

  addToolActivity: (name, args) => {
    set((s) => ({
      toolActivities: [...s.toolActivities, {
        name,
        status: 'running',
        args,
        startedAt: Date.now(),
      }],
    }));
  },

  completeToolActivity: (name, success, elapsed, result) => {
    set((s) => {
      const next = [...s.toolActivities];
      for (let index = next.length - 1; index >= 0; index -= 1) {
        const activity = next[index];
        if (activity.name === name && activity.status === 'running') {
          next[index] = {
            ...activity,
            status: success ? 'done' : 'error',
            elapsed,
            result,
          };
          break;
        }
      }
      return { toolActivities: next };
    });
  },

  markRunningToolsCancelled: () => {
    set((s) => {
      let changed = false;
      const now = Date.now();
      const toolActivities = s.toolActivities.map((activity) => {
        if (activity.status !== 'running') {
          return activity;
        }
        changed = true;
        return {
          ...activity,
          status: 'error' as const,
          result: activity.result ?? 'cancelled',
          elapsed: activity.elapsed ?? now - activity.startedAt,
        };
      });
      return changed ? { toolActivities } : s;
    });
  },

  clearToolActivities: () => set({ toolActivities: [] }),
  resetConversation: (keepSessionId = false) =>
    set((s) => ({
      messages: [],
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId: keepSessionId ? s.sessionId : null,
      cardsById: {},
      cardIdsByMessageId: {},
      goal: null,
      startedAt: null,
      unreadCount: 0,
    })),
  clearMessages: () =>
    set({
      messages: [],
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId: null,
      cardsById: {},
      cardIdsByMessageId: {},
      goal: null,
      startedAt: null,
      unreadCount: 0,
    }),
}));
