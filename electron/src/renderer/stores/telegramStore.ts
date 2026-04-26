import { create } from 'zustand';

import {
  cancelTelegramPairing,
  disconnectTelegram,
  getTelegramPairingStatus,
  getTelegramStatus,
  normalizeTelegramStatus,
  reconnectTelegram,
  sendTelegramTestMessage,
  startTelegramPairing,
  testTelegramBot,
  type TelegramBotIdentity,
  type TelegramPairedChat,
  type TelegramPairingHandle,
  type TelegramPairingStatus,
  type TelegramRuntimeStatus,
  type TelegramStatusSnapshot,
  type TelegramTestResult,
} from '../infrastructure/api/telegramApi';
import type { RpcFn } from '../components/settings/types';

export interface TelegramPairingSession {
  handleId: string;
  code: string | null;
  state: TelegramPairingStatus;
  expiresAtMs: number | null;
  botIdentity: TelegramBotIdentity | null;
  chatId: string | null;
}

interface TelegramState {
  enabled: boolean;
  status: TelegramRuntimeStatus;
  botIdentity: TelegramBotIdentity | null;
  pairedChat: TelegramPairedChat | null;
  pairedChats: TelegramPairedChat[];
  pairing: TelegramPairingSession | null;
  loading: boolean;
  error: string | null;
  lastError: string | null;
  lastUpdatedAt: number | null;

  applyStatusSnapshot: (snapshot: TelegramStatusSnapshot) => void;
  applyStatusEvent: (payload: unknown) => TelegramStatusSnapshot;
  applyPairedEvent: (payload: unknown) => void;
  setPairingState: (state: TelegramPairingStatus) => void;
  setError: (message: string | null) => void;
  clearError: () => void;
  resetTelegram: () => void;

  testToken: (rpc: RpcFn, token: string) => Promise<TelegramTestResult>;
  startPairing: (rpc: RpcFn, token: string) => Promise<TelegramPairingHandle>;
  refreshPairingStatus: (
    rpc: RpcFn,
    handleId?: string | null,
  ) => Promise<TelegramPairingStatus | null>;
  cancelPairing: (rpc: RpcFn, handleId?: string | null) => Promise<void>;
  refreshStatus: (rpc: RpcFn) => Promise<TelegramStatusSnapshot>;
  sendTestMessage: (rpc: RpcFn, chatId?: string | null) => Promise<void>;
  disconnect: (rpc: RpcFn, chatId?: string | null) => Promise<void>;
  reconnect: (rpc: RpcFn) => Promise<TelegramStatusSnapshot>;
}

const INITIAL_STATE = {
  enabled: false,
  status: 'disabled' as TelegramRuntimeStatus,
  botIdentity: null,
  pairedChat: null,
  pairedChats: [],
  pairing: null,
  loading: false,
  error: null,
  lastError: null,
  lastUpdatedAt: null,
};

function messageFromError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim().length > 0
    ? error.message
    : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function pickString(...values: readonly unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== 'string') {
      continue;
    }
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      return trimmed;
    }
  }
  return null;
}

function primaryChat(chats: readonly TelegramPairedChat[]): TelegramPairedChat | null {
  return chats[0] ?? null;
}

function mergeBotIdentity(
  next: TelegramBotIdentity | null,
  current: TelegramBotIdentity | null,
): TelegramBotIdentity | null {
  if (!next) {
    return current;
  }
  if (!current) {
    return next;
  }

  const sameBot =
    next.username === null
    || current.username === null
    || next.username === current.username;

  return {
    username: next.username ?? current.username,
    botId: next.botId ?? (sameBot ? current.botId : null),
    firstName: next.firstName ?? (sameBot ? current.firstName : null),
  };
}

function createPairingFromHandle(handle: TelegramPairingHandle): TelegramPairingSession {
  return {
    handleId: handle.handleId,
    code: handle.code,
    state: handle.state === 'unknown' ? 'pending' : handle.state,
    expiresAtMs: handle.expiresAtMs,
    botIdentity: handle.botIdentity,
    chatId: null,
  };
}

function applyStatusPatch(
  snapshot: TelegramStatusSnapshot,
  currentIdentity: TelegramBotIdentity | null,
) {
  return {
    enabled: snapshot.enabled,
    status: snapshot.status,
    botIdentity: mergeBotIdentity(snapshot.botIdentity, currentIdentity),
    pairedChats: snapshot.pairedChats,
    pairedChat: primaryChat(snapshot.pairedChats),
    lastError: snapshot.lastError,
    error: snapshot.lastError,
    lastUpdatedAt: Date.now(),
  };
}

function createPairedChat(chatId: string): TelegramPairedChat {
  const now = Date.now();
  return {
    chatId,
    firstActiveAtMs: now,
    lastActiveAtMs: now,
  };
}

function upsertPairedChat(
  chats: readonly TelegramPairedChat[],
  chat: TelegramPairedChat,
): TelegramPairedChat[] {
  const existingIndex = chats.findIndex((entry) => entry.chatId === chat.chatId);
  if (existingIndex === -1) {
    return [chat, ...chats];
  }
  return chats.map((entry, index) => (index === existingIndex ? { ...entry, ...chat } : entry));
}

export const useTelegramStore = create<TelegramState>((set, get) => ({
  ...INITIAL_STATE,

  applyStatusSnapshot: (snapshot) =>
    set((state) => applyStatusPatch(snapshot, state.botIdentity)),

  applyStatusEvent: (payload) => {
    const snapshot = normalizeTelegramStatus(payload);
    set((state) => applyStatusPatch(snapshot, state.botIdentity));
    return snapshot;
  },

  applyPairedEvent: (payload) => {
    const raw = isRecord(payload) ? payload : {};
    const handleId = pickString(raw.handleId, raw.handle_id);
    const chatId = pickString(raw.chatId, raw.chat_id);

    set((state) => {
      const pairing =
        state.pairing && (!handleId || state.pairing.handleId === handleId)
          ? {
              ...state.pairing,
              state: 'paired' as TelegramPairingStatus,
              chatId: chatId ?? state.pairing.chatId,
            }
          : state.pairing;

      if (!chatId) {
        return {
          pairing,
          enabled: true,
          lastUpdatedAt: Date.now(),
        };
      }

      const pairedChats = upsertPairedChat(state.pairedChats, createPairedChat(chatId));
      return {
        enabled: true,
        status: state.status === 'disabled' ? 'running' : state.status,
        pairing,
        pairedChats,
        pairedChat: primaryChat(pairedChats),
        lastUpdatedAt: Date.now(),
      };
    });
  },

  setPairingState: (pairingState) =>
    set((state) => ({
      pairing: state.pairing ? { ...state.pairing, state: pairingState } : null,
      lastUpdatedAt: Date.now(),
    })),

  setError: (message) => set({ error: message, lastError: message }),
  clearError: () => set({ error: null }),
  resetTelegram: () => set({ ...INITIAL_STATE }),

  testToken: async (rpc, token) => {
    set({ loading: true, error: null });
    try {
      const result = await testTelegramBot(rpc, token);
      if (result.ok) {
        set((state) => ({
          botIdentity: mergeBotIdentity(result.botIdentity, state.botIdentity),
          loading: false,
          error: null,
          lastUpdatedAt: Date.now(),
        }));
      } else {
        set({
          loading: false,
          error: result.reason,
          lastError: result.reason,
          lastUpdatedAt: Date.now(),
        });
      }
      return result;
    } catch (error) {
      const message = messageFromError(error, 'Telegram bot validation failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  startPairing: async (rpc, token) => {
    set({ loading: true, error: null });
    try {
      const handle = await startTelegramPairing(rpc, token);
      set((state) => ({
        enabled: true,
        status: state.status === 'disabled' ? 'starting' : state.status,
        botIdentity: mergeBotIdentity(handle.botIdentity, state.botIdentity),
        pairing: createPairingFromHandle(handle),
        loading: false,
        error: null,
        lastUpdatedAt: Date.now(),
      }));
      return handle;
    } catch (error) {
      const message = messageFromError(error, 'Telegram pairing failed to start');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  refreshPairingStatus: async (rpc, handleId) => {
    const targetHandleId = handleId?.trim() || get().pairing?.handleId || null;
    if (!targetHandleId) {
      return null;
    }

    set({ loading: true, error: null });
    try {
      const result = await getTelegramPairingStatus(rpc, targetHandleId);
      set((state) => {
        const existing = state.pairing;
        const pairing =
          existing && existing.handleId === targetHandleId
            ? { ...existing, state: result.state }
            : {
                handleId: targetHandleId,
                code: null,
                state: result.state,
                expiresAtMs: null,
                botIdentity: null,
                chatId: null,
              };
        return {
          pairing,
          loading: false,
          error: null,
          lastUpdatedAt: Date.now(),
        };
      });
      return result.state;
    } catch (error) {
      const message = messageFromError(error, 'Telegram pairing status refresh failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  cancelPairing: async (rpc, handleId) => {
    const targetHandleId = handleId?.trim() || get().pairing?.handleId || null;
    if (!targetHandleId) {
      return;
    }

    set({ loading: true, error: null });
    try {
      await cancelTelegramPairing(rpc, targetHandleId);
      set((state) => ({
        pairing:
          state.pairing && state.pairing.handleId === targetHandleId
            ? { ...state.pairing, state: 'cancelled' }
            : state.pairing,
        loading: false,
        error: null,
        lastUpdatedAt: Date.now(),
      }));
    } catch (error) {
      const message = messageFromError(error, 'Telegram pairing cancellation failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  refreshStatus: async (rpc) => {
    set({ loading: true, error: null });
    try {
      const snapshot = await getTelegramStatus(rpc);
      set((state) => ({
        ...applyStatusPatch(snapshot, state.botIdentity),
        loading: false,
      }));
      return snapshot;
    } catch (error) {
      const message = messageFromError(error, 'Telegram status refresh failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  sendTestMessage: async (rpc, chatId) => {
    const targetChatId = chatId?.trim() || get().pairedChat?.chatId || null;
    if (!targetChatId) {
      const error = new Error('No Telegram chat is paired');
      set({
        error: error.message,
        lastError: error.message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }

    set({ loading: true, error: null });
    try {
      await sendTelegramTestMessage(rpc, targetChatId);
      set({ loading: false, error: null, lastUpdatedAt: Date.now() });
    } catch (error) {
      const message = messageFromError(error, 'Telegram test message failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  disconnect: async (rpc, chatId) => {
    const targetChatId = chatId?.trim() || null;
    set({ loading: true, error: null });
    try {
      await disconnectTelegram(rpc, targetChatId);
      set((state) => {
        if (!targetChatId) {
          return {
            ...INITIAL_STATE,
            loading: false,
            lastUpdatedAt: Date.now(),
          };
        }

        const pairedChats = state.pairedChats.filter(
          (entry) => entry.chatId !== targetChatId,
        );
        return {
          pairedChats,
          pairedChat: primaryChat(pairedChats),
          enabled: pairedChats.length > 0 ? state.enabled : false,
          status: pairedChats.length > 0 ? state.status : 'disabled',
          loading: false,
          error: null,
          lastUpdatedAt: Date.now(),
        };
      });
    } catch (error) {
      const message = messageFromError(error, 'Telegram disconnect failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },

  reconnect: async (rpc) => {
    set({ loading: true, error: null });
    try {
      await reconnectTelegram(rpc);
      const snapshot = await getTelegramStatus(rpc);
      set((state) => ({
        ...applyStatusPatch(snapshot, state.botIdentity),
        loading: false,
      }));
      return snapshot;
    } catch (error) {
      const message = messageFromError(error, 'Telegram reconnect failed');
      set({
        loading: false,
        error: message,
        lastError: message,
        lastUpdatedAt: Date.now(),
      });
      throw error;
    }
  },
}));
