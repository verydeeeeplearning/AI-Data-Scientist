/**
 * useExecutionTimeline — bridges chatStore tool activities to the stage timeline.
 *
 * Memoized React hook on top of the pure `selectExecutionTimeline` selector.
 * Stable transition identity prevents downstream `announce()` and outcome-jump
 * effects from re-firing when only the activity reference changes.
 */

import { useEffect, useMemo, useRef } from 'react';
import {
  selectExecutionTimeline,
  transitionsEqual,
  type ExecutionTimelineSnapshot,
  type ExecutionTimelineTransition,
} from '../application/execution/selectExecutionTimeline';
import { useChatStore, type ToolActivity } from '../stores/chatStore';

export type {
  ExecutionTimelineSnapshot,
  ExecutionTimelineTransition,
} from '../application/execution/selectExecutionTimeline';

export interface UseExecutionTimelineOptions {
  readonly activitiesOverride?: readonly ToolActivity[];
}

export function useExecutionTimeline(
  options: UseExecutionTimelineOptions = {},
): ExecutionTimelineSnapshot {
  const storeActivities = useChatStore((state) => state.toolActivities);
  const activities = options.activitiesOverride ?? storeActivities;

  const snapshot = useMemo<ExecutionTimelineSnapshot>(
    () => selectExecutionTimeline(activities),
    [activities],
  );

  const previousTransitionRef = useRef<ExecutionTimelineTransition | null>(null);
  const transitionForCallers = useMemo(() => {
    if (transitionsEqual(previousTransitionRef.current, snapshot.latestTransition)) {
      return previousTransitionRef.current;
    }
    return snapshot.latestTransition;
  }, [snapshot.latestTransition]);

  useEffect(() => {
    previousTransitionRef.current = transitionForCallers;
  }, [transitionForCallers]);

  if (transitionForCallers === snapshot.latestTransition) {
    return snapshot;
  }
  return Object.freeze({
    ...snapshot,
    latestTransition: transitionForCallers,
  });
}
