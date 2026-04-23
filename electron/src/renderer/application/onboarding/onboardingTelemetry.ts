/**
 * Onboarding telemetry port.
 *
 * Wave 2 W2-E phase 2: define a transport-independent telemetry surface so the
 * wizard can emit step transitions, finalize success, and finalize failure
 * without coupling to a specific observability vendor. Adapters live in the
 * infrastructure layer and the composition root injects the port.
 */

import type {
  OnboardingAutonomyMode,
  OnboardingDataChoiceId,
  OnboardingDeliverableId,
  OnboardingPrimaryStepId,
  OnboardingUseCaseId,
} from './onboardingState';

export type OnboardingTelemetryEvent =
  | OnboardingStartedEvent
  | OnboardingStepEnteredEvent
  | OnboardingUseCaseSelectedEvent
  | OnboardingFinalizeStartedEvent
  | OnboardingFinalizeSucceededEvent
  | OnboardingFinalizeFailedEvent;

export interface OnboardingStartedEvent {
  type: 'onboarding.started';
  alreadyCompletedBefore: boolean;
}

export interface OnboardingStepEnteredEvent {
  type: 'onboarding.step_entered';
  step: OnboardingPrimaryStepId;
  stepIndex: number;
}

export interface OnboardingUseCaseSelectedEvent {
  type: 'onboarding.use_case_selected';
  useCaseId: OnboardingUseCaseId;
}

export interface OnboardingFinalizeStartedEvent {
  type: 'onboarding.finalize_started';
  useCaseId: OnboardingUseCaseId;
  dataChoiceId: OnboardingDataChoiceId;
  deliverables: readonly OnboardingDeliverableId[];
  autonomyMode: OnboardingAutonomyMode;
  modelId: string;
}

export interface OnboardingFinalizeSucceededEvent {
  type: 'onboarding.finalize_succeeded';
  useCaseId: OnboardingUseCaseId;
  modelId: string;
  durationMs: number;
}

export interface OnboardingFinalizeFailedEvent {
  type: 'onboarding.finalize_failed';
  useCaseId: OnboardingUseCaseId | null;
  modelId: string | null;
  reason: string;
  durationMs: number;
}

export type OnboardingTelemetryPort = (event: OnboardingTelemetryEvent) => void;

export const NOOP_ONBOARDING_TELEMETRY: OnboardingTelemetryPort = () => {};

export function buildConsoleOnboardingTelemetry(
  consoleLike: { info: (...args: unknown[]) => void },
): OnboardingTelemetryPort {
  return (event) => {
    consoleLike.info('[onboarding-telemetry]', event.type, event);
  };
}
