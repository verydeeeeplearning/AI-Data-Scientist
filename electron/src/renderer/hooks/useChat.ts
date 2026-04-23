/**
 * Chat hook — connects WebSocket events to stores.
 *
 * Subscribes to stream.delta, stream.done, tool.start, tool.end, etc.
 * and dispatches to chatStore / agentStore.
 */

import { useCallback, useEffect } from 'react';
import { useWs } from './WsProvider';
import {
  normalizeStreamDonePayload,
  useChatStore,
} from '../stores/chatStore';
import { useAgentStore } from '../stores/agentStore';

export function useChat() {
  const { status, disconnectReason, rpc, on } = useWs();

  // Extract only the action functions via selectors (stable references)
  const setConnected = useAgentStore((s) => s.setConnected);
  const updateFromStatus = useAgentStore((s) => s.updateFromStatus);
  const setCost = useAgentStore((s) => s.setCost);
  const setStep = useAgentStore((s) => s.setStep);
  const model = useAgentStore((s) => s.model);

  const addUserMessage = useChatStore((s) => s.addUserMessage);
  const startAssistantMessage = useChatStore((s) => s.startAssistantMessage);
  const appendStreamDelta = useChatStore((s) => s.appendStreamDelta);
  const finalizeStream = useChatStore((s) => s.finalizeStream);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const upsertCards = useChatStore((s) => s.upsertCards);
  const addToolActivity = useChatStore((s) => s.addToolActivity);
  const completeToolActivity = useChatStore((s) => s.completeToolActivity);
  const clearToolActivities = useChatStore((s) => s.clearToolActivities);
  const sessionId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);

  // Sync connection status
  useEffect(() => {
    setConnected(status === 'connected');
  }, [status, setConnected]);

  // Fetch initial status on connect
  useEffect(() => {
    if (status === 'connected') {
      rpc('status.get').then((data) => {
        updateFromStatus(data);
      }).catch((err) => console.warn('[useChat] status.get failed:', err));
    }
  }, [status, rpc, updateFromStatus]);

  // Subscribe to events
  useEffect(() => {
    const unsubs = [
      on('stream.delta', (payload) => {
        appendStreamDelta((payload.token as string) ?? '');
      }),

      on('stream.done', (payload) => {
        const normalized = normalizeStreamDonePayload(payload);
        finalizeStream(normalized.content, normalized.messageId ?? null);
        upsertCards(normalized.cards);
        setStreaming(false);
        if (typeof normalized.cost === 'number') {
          setCost(normalized.cost);
        }
      }),

      on('tool.start', (payload) => {
        addToolActivity(
          (payload.name as string) ?? 'unknown',
          payload.args as Record<string, unknown>,
        );
      }),

      on('tool.end', (payload) => {
        completeToolActivity(
          (payload.name as string) ?? 'unknown',
          (payload.success as boolean) ?? true,
          payload.elapsed as number | undefined,
          payload.result as string | undefined,
        );
      }),

      on('status.update', (payload) => {
        if (typeof payload.step === 'number') {
          setStep(payload.step);
        }
      }),

    ];

    return () => { unsubs.forEach((fn) => fn()); };
  }, [
    on,
    appendStreamDelta,
    finalizeStream,
    upsertCards,
    setStreaming,
    setCost,
    addToolActivity,
    completeToolActivity,
    setStep,
  ]);

  // Send message
  const sendMessage = useCallback(async (message: string) => {
    addUserMessage(message);
    startAssistantMessage();
    clearToolActivities();

    try {
      const result = await rpc('chat.send', {
        message,
        sessionId,
        model,
      });
      if (result.sessionId) {
        setSessionId(result.sessionId as string);
      }
    } catch (err) {
      finalizeStream(`Error: ${err}`);
    }
  }, [rpc, sessionId, model, addUserMessage, startAssistantMessage, clearToolActivities, setSessionId, finalizeStream]);

  // Abort current run
  const abort = useCallback(async () => {
    try {
      await rpc('chat.abort');
    } catch (err) {
      console.warn('[useChat] abort failed:', err);
    }
  }, [rpc]);

  return { sendMessage, abort, status, disconnectReason, on };
}
