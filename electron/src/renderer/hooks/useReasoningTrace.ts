import { useEffect, useMemo, useRef } from 'react';
import { selectExecutionTimeline } from '../application/execution/selectExecutionTimeline';
import type {
  PlanCreatedEvent,
  PlanReplannedEvent,
  PlanUpdatedEvent,
  ReasoningEmittedEvent,
} from '../types/events';
import type { StageKey } from '../domain/execution/stage';
import { useWs } from './WsProvider';
import { useChatStore } from '../stores/chatStore';
import {
  useReasoningTraceStore,
  type ReasoningTraceEntry,
} from '../stores/reasoningTraceStore';

const REPLAN_HIGHLIGHT_TTL_MS = 3_000;
const HYDRATION_REPLACEMENT_WINDOW_MS = 1_500;

function resolveCurrentStageKey(): StageKey | null {
  const toolActivities = useChatStore.getState().toolActivities;
  return selectExecutionTimeline(toolActivities).currentStage?.key ?? null;
}

function normalizeReasoningTrace(
  payload: ReasoningEmittedEvent,
): ReasoningTraceEntry | null {
  const emittedAt = typeof payload.emittedAt === 'number'
    ? payload.emittedAt
    : Date.now();
  const traceId = typeof payload.id === 'string' && payload.id.trim().length > 0
    ? payload.id
    : `reasoning.${emittedAt}`;

  const hasContent = Boolean(
    payload.thinking
      || payload.hypothesis
      || payload.action
      || payload.observation
      || payload.decision,
  );

  if (!hasContent) {
    return null;
  }

  return {
    id: traceId,
    stageKey: resolveCurrentStageKey(),
    emittedAt,
    planNodeId: payload.planNodeId,
    thinking: payload.thinking,
    hypothesis: payload.hypothesis,
    action: payload.action,
    observation: payload.observation,
    decision: payload.decision,
  };
}

function asReasoningEmittedEvent(payload: Record<string, unknown>): ReasoningEmittedEvent {
  return payload as unknown as ReasoningEmittedEvent;
}

function asPlanReplannedEvent(payload: Record<string, unknown>): PlanReplannedEvent {
  return payload as unknown as PlanReplannedEvent;
}

function asPlanCreatedEvent(payload: Record<string, unknown>): PlanCreatedEvent {
  return payload as unknown as PlanCreatedEvent;
}

function asPlanUpdatedEvent(payload: Record<string, unknown>): PlanUpdatedEvent {
  return payload as unknown as PlanUpdatedEvent;
}

export function useReasoningTraceBridge(enabled: boolean): void {
  const { on, status } = useWs();
  const upsertTrace = useReasoningTraceStore((state) => state.upsertTrace);
  const replacePlanTree = useReasoningTraceStore((state) => state.replacePlanTree);
  const patchPlanNode = useReasoningTraceStore((state) => state.patchPlanNode);
  const applyReplanDiff = useReasoningTraceStore((state) => state.applyReplanDiff);
  const clearReplanHighlights = useReasoningTraceStore((state) => state.clearReplanHighlights);
  const markPlanCreated = useReasoningTraceStore((state) => state.markPlanCreated);
  const markPlanUpdated = useReasoningTraceStore((state) => state.markPlanUpdated);
  const markPlanReplanned = useReasoningTraceStore((state) => state.markPlanReplanned);
  const setRunId = useReasoningTraceStore((state) => state.setRunId);
  const hydrateFromPersistence = useReasoningTraceStore((state) => state.hydrateFromPersistence);
  const clearPersistence = useReasoningTraceStore((state) => state.clearPersistence);
  const reset = useReasoningTraceStore((state) => state.reset);

  const replanHighlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastPlanCreatedAtRef = useRef<number>(0);
  const previousStatusRef = useRef<typeof status>(status);

  useEffect(() => {
    if (!enabled) {
      reset();
      return;
    }

    const unsubs = [
      on('task.started', (payload) => {
        // Clear any prior snapshot BEFORE assigning the new runId so the
        // localStorage key is not briefly anchored to stale data.
        clearPersistence();
        reset();
        const runId = typeof payload?.runId === 'string' && payload.runId.length > 0
          ? payload.runId
          : null;
        if (runId) {
          // Anchors the persistence snapshot to this run. Subsequent
          // reconnects compare ``stored.runId === runId`` before
          // restoring; the 1.5s replacement window in the reconnect
          // effect still wins if a fresh ``plan.created`` arrives first.
          setRunId(runId);
          // Mark this as a fresh run so the hydration effect below skips
          // restoring a stale snapshot if the WS bounces immediately
          // after task.started — a fresh ``plan.created`` will arrive
          // within the 1.5s window and replace anything we'd hydrate.
          lastPlanCreatedAtRef.current = Date.now();
        }
      }),
      on('reasoning.emitted', (payload) => {
        const trace = normalizeReasoningTrace(asReasoningEmittedEvent(payload));
        if (trace) {
          upsertTrace(trace);
        }
      }),
      on('plan.created', (payload) => {
        const typedPayload = asPlanCreatedEvent(payload);
        replacePlanTree(typedPayload.planTree);
        const ts = Date.now();
        markPlanCreated(ts);
        lastPlanCreatedAtRef.current = ts;
      }),
      on('plan.updated', (payload) => {
        const typedPayload = asPlanUpdatedEvent(payload);
        patchPlanNode(typedPayload.nodeId, typedPayload.updates);
        markPlanUpdated(Date.now());
      }),
      on('plan.replanned', (payload) => {
        const typedPayload = asPlanReplannedEvent(payload);
        applyReplanDiff(typedPayload.diff);
        markPlanReplanned(Date.now(), typedPayload.diff.reason ?? null);
        if (replanHighlightTimerRef.current !== null) {
          clearTimeout(replanHighlightTimerRef.current);
        }
        replanHighlightTimerRef.current = setTimeout(() => {
          clearReplanHighlights();
          replanHighlightTimerRef.current = null;
        }, REPLAN_HIGHLIGHT_TTL_MS);
      }),
    ];

    return () => {
      unsubs.forEach((unsubscribe) => unsubscribe());
      if (replanHighlightTimerRef.current !== null) {
        clearTimeout(replanHighlightTimerRef.current);
        replanHighlightTimerRef.current = null;
      }
    };
  }, [
    applyReplanDiff,
    clearPersistence,
    clearReplanHighlights,
    enabled,
    markPlanCreated,
    markPlanReplanned,
    markPlanUpdated,
    on,
    patchPlanNode,
    replacePlanTree,
    reset,
    setRunId,
    upsertTrace,
  ]);

  // Reconnect-safe hydration: when WS transitions back to "connected" after a
  // disconnected/reconnecting phase AND we have an active runId, restore the
  // last-known plan tree from storage. If a fresh ``plan.created`` lands
  // within ``HYDRATION_REPLACEMENT_WINDOW_MS`` the live data already replaced
  // it, so the stale snapshot is harmless.
  useEffect(() => {
    if (!enabled) {
      previousStatusRef.current = status;
      return;
    }

    const previous = previousStatusRef.current;
    previousStatusRef.current = status;

    if (status !== 'connected') {
      return;
    }
    if (previous === 'connected') {
      return;
    }

    const runId = useReasoningTraceStore.getState().runId;
    if (!runId) {
      return;
    }

    const sinceLastFreshPlan = Date.now() - lastPlanCreatedAtRef.current;
    if (sinceLastFreshPlan < HYDRATION_REPLACEMENT_WINDOW_MS) {
      return;
    }

    hydrateFromPersistence(runId);
  }, [enabled, hydrateFromPersistence, status]);
}

export function useStageReasoningTrace(stageKey: StageKey) {
  const traces = useReasoningTraceStore((state) => state.traces);
  const planState = useReasoningTraceStore((state) => state.planState);

  return useMemo(
    () => ({
      traces: traces
        .filter((trace) => trace.stageKey === stageKey)
        .sort((left, right) => left.emittedAt - right.emittedAt),
      planState,
    }),
    [planState, stageKey, traces],
  );
}

export type {
  PlanCreatedEvent,
  PlanUpdatedEvent,
  PlanReplannedEvent,
  ReasoningEmittedEvent,
};
