/**
 * Chat state — Zustand store for messages and tool activity.
 */

import { create } from 'zustand';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface PersistedChatMessage {
  role: string;
  content: string;
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

  // Actions
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendStreamDelta: (token: string) => void;
  finalizeStream: (content: string) => void;
  setStreaming: (v: boolean) => void;
  setSessionId: (id: string) => void;
  replaceConversation: (messages: PersistedChatMessage[], sessionId: string) => void;

  addToolActivity: (name: string, args?: Record<string, unknown>) => void;
  completeToolActivity: (name: string, success: boolean, elapsed?: number) => void;
  clearToolActivities: () => void;

  resetConversation: (keepSessionId?: boolean) => void;
  clearMessages: () => void;
}

let msgCounter = 0;
function nextMsgId(): string {
  return `msg-${++msgCounter}-${Date.now().toString(36)}`;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  toolActivities: [],
  isStreaming: false,
  streamBuffer: '',
  sessionId: null,

  addUserMessage: (content) => {
    const id = nextMsgId();
    set((s) => ({
      messages: [...s.messages, {
        id,
        role: 'user',
        content,
        timestamp: Date.now(),
      }],
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

  appendStreamDelta: (token) => {
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...msgs[msgs.length - 1],
          content: msgs[msgs.length - 1].content + token,
        };
      }
      return { messages: msgs, streamBuffer: s.streamBuffer + token };
    });
  },

  finalizeStream: (content) => {
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...msgs[msgs.length - 1],
          content,
        };
      }
      return { messages: msgs, isStreaming: false, streamBuffer: '' };
    });
  },

  setStreaming: (v) => set({ isStreaming: v }),
  setSessionId: (id) => set({ sessionId: id }),
  replaceConversation: (messages, sessionId) =>
    set({
      messages: messages.map((message, index) => ({
        id: nextMsgId(),
        role: message.role === 'user' ? 'user' : 'assistant',
        content: message.content,
        timestamp: Date.now() + index,
      })),
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId,
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

  completeToolActivity: (name, success, elapsed) => {
    set((s) => ({
      toolActivities: s.toolActivities.map((t) =>
        t.name === name && t.status === 'running'
          ? { ...t, status: success ? 'done' : 'error', elapsed }
          : t
      ),
    }));
  },

  clearToolActivities: () => set({ toolActivities: [] }),
  resetConversation: (keepSessionId = false) =>
    set((s) => ({
      messages: [],
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId: keepSessionId ? s.sessionId : null,
    })),
  clearMessages: () =>
    set({
      messages: [],
      toolActivities: [],
      isStreaming: false,
      streamBuffer: '',
      sessionId: null,
    }),
}));
