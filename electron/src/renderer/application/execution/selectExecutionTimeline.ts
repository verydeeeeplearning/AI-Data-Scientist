import { aggregateStages, type ToolActivityLike } from './aggregateStages';
import type { Stage, StageKey } from '../../domain/execution/stage';

export interface ExecutionTimelineTransition {
  readonly stageKey: StageKey;
  readonly status: Stage['status'];
  readonly toolEventCount: number;
}

export interface ExecutionTimelineSnapshot {
  readonly stages: readonly Stage[];
  readonly currentStage: Stage | null;
  readonly latestTransition: ExecutionTimelineTransition | null;
  readonly hasActivity: boolean;
}

function pickCurrentStage(stages: readonly Stage[]): Stage | null {
  for (let index = stages.length - 1; index >= 0; index -= 1) {
    const stage = stages[index];
    if (stage.status === 'running') {
      return stage;
    }
  }
  return stages[stages.length - 1] ?? null;
}

function buildTransition(stage: Stage | null): ExecutionTimelineTransition | null {
  if (!stage) {
    return null;
  }
  return Object.freeze({
    stageKey: stage.key,
    status: stage.status,
    toolEventCount: stage.toolEvents.length,
  });
}

export function transitionsEqual(
  a: ExecutionTimelineTransition | null,
  b: ExecutionTimelineTransition | null,
): boolean {
  if (a === b) return true;
  if (a === null || b === null) return false;
  return (
    a.stageKey === b.stageKey
    && a.status === b.status
    && a.toolEventCount === b.toolEventCount
  );
}

export function selectExecutionTimeline(
  activities: readonly ToolActivityLike[],
): ExecutionTimelineSnapshot {
  const stages = aggregateStages(activities);
  const currentStage = pickCurrentStage(stages);
  return Object.freeze({
    stages,
    currentStage,
    latestTransition: buildTransition(currentStage),
    hasActivity: activities.length > 0,
  });
}
