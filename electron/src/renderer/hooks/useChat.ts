/**
 * Chat hook — connects WebSocket events to stores.
 *
 * Subscribes to stream.delta, stream.done, tool.start, tool.end, etc.
 * and dispatches to chatStore / agentStore.
 */

import { useCallback, useEffect, useRef } from 'react';
import { useWs } from './WsProvider';
import {
  normalizeStreamDonePayload,
  useChatStore,
} from '../stores/chatStore';
import { useAgentStore } from '../stores/agentStore';
import { useAuthStore } from '../stores/authStore';
import { useI18n } from '../stores/i18nStore';
import { useToastStore } from '../stores/toastStore';
import { describeModelAccess } from '../utils/modelAuth';

export function useChat() {
  const { status, disconnectReason, rpc, on } = useWs();
  const t = useI18n((state) => state.t);
  const currentStreamIdRef = useRef<string | null>(null);

  // Extract only the action functions via selectors (stable references)
  const setConnected = useAgentStore((s) => s.setConnected);
  const updateFromStatus = useAgentStore((s) => s.updateFromStatus);
  const setCost = useAgentStore((s) => s.setCost);
  const setStep = useAgentStore((s) => s.setStep);
  const model = useAgentStore((s) => s.model);
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const pushToast = useToastStore((s) => s.pushToast);

  const addUserMessage = useChatStore((s) => s.addUserMessage);
  const setGoal = useChatStore((s) => s.setGoal);
  const startAssistantMessage = useChatStore((s) => s.startAssistantMessage);
  const appendStreamDelta = useChatStore((s) => s.appendStreamDelta);
  const finalizeStream = useChatStore((s) => s.finalizeStream);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const upsertCards = useChatStore((s) => s.upsertCards);
  const addToolActivity = useChatStore((s) => s.addToolActivity);
  const completeToolActivity = useChatStore((s) => s.completeToolActivity);
  const markRunningToolsCancelled = useChatStore((s) => s.markRunningToolsCancelled);
  const clearToolActivities = useChatStore((s) => s.clearToolActivities);
  const markLastAssistantTruncated = useChatStore((s) => s.markLastAssistantTruncated);
  const sessionId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);

  // Sync connection status
  useEffect(() => {
    setConnected(status === 'connected');
  }, [status, setConnected]);

  // Fetch initial status on connect
  useEffect(() => {
    if (status !== 'connected') {
      return;
    }
    let cancelled = false;
    rpc('status.get')
      .then((data) => {
        if (!cancelled) {
          updateFromStatus(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('[useChat] status.get failed:', err);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status, rpc, updateFromStatus]);

  // Subscribe to events
  useEffect(() => {
    const unsubs = [
      on('stream.delta', (payload) => {
        const expectedMessageId = currentStreamIdRef.current;
        if (expectedMessageId == null) {
          return;
        }
        appendStreamDelta((payload.token as string) ?? '', expectedMessageId);
      }),

      on('stream.done', (payload) => {
        const expectedMessageId = currentStreamIdRef.current;
        if (expectedMessageId == null) {
          return;
        }
        const normalized = normalizeStreamDonePayload(payload);
        const finalized = finalizeStream(
          normalized.content,
          normalized.messageId ?? null,
          expectedMessageId,
        );
        if (!finalized) {
          return;
        }
        upsertCards(normalized.cards);
        currentStreamIdRef.current = null;
        if (typeof normalized.cost === 'number') {
          setCost(normalized.cost);
        }
      }),

      on('stream.error', (payload) => {
        const expectedMessageId = currentStreamIdRef.current;
        markRunningToolsCancelled();
        if (expectedMessageId == null) {
          setStreaming(false);
          return;
        }
        const finalized = finalizeStream(
          formatStreamError(payload),
          null,
          expectedMessageId,
        );
        if (finalized) {
          currentStreamIdRef.current = null;
        }
        setStreaming(false);
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
    markRunningToolsCancelled,
    setStep,
  ]);

  useEffect(() => {
    if (status !== 'disconnected') {
      return;
    }
    const state = useChatStore.getState();
    if (state.isStreaming) {
      markLastAssistantTruncated(currentStreamIdRef.current);
      setStreaming(false);
      currentStreamIdRef.current = null;
    }
    markRunningToolsCancelled();
  }, [status, markLastAssistantTruncated, markRunningToolsCancelled, setStreaming]);

  // Send message
  const sendMessage = useCallback(async (message: string) => {
    const modelAccess = describeModelAccess({
      modelId: model,
      providerStatuses,
      oauthStatuses,
    });
    if (!modelAccess.ready) {
      pushToast({
        title: t('chat.error.modelKeyMissing', {
          model: modelAccess.providerLabel,
        }),
        tone: 'warning',
      });
      return;
    }

    // First user message of a session establishes the mission goal shown in
    // MissionContextBar. Subsequent messages don't overwrite it.
    const trimmed = message.trim();
    if (trimmed.length > 0 && useChatStore.getState().goal == null) {
      const summary = trimmed.length > 120 ? `${trimmed.slice(0, 117)}...` : trimmed;
      setGoal(summary);
    }
    addUserMessage(message);
    const assistantMessageId = startAssistantMessage();
    currentStreamIdRef.current = assistantMessageId;
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
      const finalized = finalizeStream(`Error: ${err}`, null, assistantMessageId);
      if (finalized && currentStreamIdRef.current === assistantMessageId) {
        currentStreamIdRef.current = null;
      }
    }
  }, [
    rpc,
    sessionId,
    model,
    providerStatuses,
    oauthStatuses,
    pushToast,
    t,
    addUserMessage,
    setGoal,
    startAssistantMessage,
    clearToolActivities,
    setSessionId,
    finalizeStream,
  ]);

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

function formatStreamError(payload: Record<string, unknown>): string {
  const message = typeof payload.message === 'string' && payload.message.trim().length > 0
    ? payload.message.trim()
    : 'Stream failed';
  return `Error: ${message}`;
}
