/**
 * Session-history hook for attaching a runtime session to the chat surface.
 */

import { useCallback, useState } from 'react';
import { useWs } from './WsProvider';
import { useChatStore, type PersistedChatMessage } from '../stores/chatStore';

function normalizeMessages(payload: unknown): PersistedChatMessage[] {
  if (!Array.isArray(payload)) return [];
  return payload
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item) => ({
      role: typeof item.role === 'string' ? item.role : 'assistant',
      content: typeof item.content === 'string' ? item.content : '',
    }))
    .filter((item) => item.content.length > 0);
}

export function useSessionHistory() {
  const { rpc } = useWs();
  const replaceConversation = useChatStore((s) => s.replaceConversation);
  const currentSessionId = useChatStore((s) => s.sessionId);
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);

  const openSession = useCallback(
    async (sessionId: string) => {
      const normalized = sessionId.trim();
      if (!normalized) return false;

      const isSwitching = currentSessionId !== normalized;
      if (isSwitching && isStreaming) {
        const ok = window.confirm(
          'A run is still streaming. It will be aborted before switching sessions. Continue?',
        );
        if (!ok) return false;
        try {
          await rpc('chat.abort');
        } catch (err) {
          console.warn('[useSessionHistory] abort before switch failed:', err);
        }
      } else if (isSwitching && messages.length > 0) {
        const ok = window.confirm(
          'Replace the current chat view with the selected session history?',
        );
        if (!ok) return false;
      }

      setOpeningSessionId(normalized);
      try {
        const result = await rpc('chat.history', {
          sessionId: normalized,
          limit: 200,
        });
        replaceConversation(normalizeMessages(result.messages), normalized);
        return true;
      } catch (err) {
        console.warn('[useSessionHistory] chat.history failed:', err);
        window.alert(`Failed to open session: ${(err as Error)?.message ?? err}`);
        return false;
      } finally {
        setOpeningSessionId(null);
      }
    },
    [currentSessionId, isStreaming, messages.length, replaceConversation, rpc],
  );

  return {
    currentSessionId,
    openingSessionId,
    openSession,
  };
}
