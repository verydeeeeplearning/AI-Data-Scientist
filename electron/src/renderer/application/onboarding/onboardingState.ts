/**
 * Pure onboarding state domain.
 *
 * Wave 2 W2-E phase 2: extract step transitions, defaults, and the
 * `OnboardingFinalizeRequest` builder out of the OnboardingWizard component
 * so they can be unit-tested without React, exercised by telemetry, and
 * reused by future entry surfaces (CLI bootstrap, restore-from-config flow).
 *
 * The component still owns React state; this module owns the transition
 * rules and serialization contracts so the boundaries match the Clean
 * Architecture rule (component is a presenter, this is application logic).
 */

import type { OnboardingUseCaseId as SharedOnboardingUseCaseId } from '../../../shared/useCaseMapping';

export type OnboardingPrimaryStepId =
  | 'use_case'
  | 'data'
  | 'deliverables'
  | 'mode'
  | 'model'
  | 'notify'
  | 'confirm';

export type OnboardingDataChoiceId = 'upload' | 'sample' | 'database_deferred';

export type OnboardingDeliverableId =
  | 'chart_summary'
  | 'report'
  | 'notebook'
  | 'presentation';

export type OnboardingAutonomyMode = 'fast' | 'balanced' | 'controlled';

export type OnboardingExecutionMode = 'auto' | 'supervised' | 'step-by-step';

export type OnboardingQualityPreset = 'fast' | 'balanced' | 'best_quality';

export type OnboardingUseCaseId = SharedOnboardingUseCaseId;

export type OnboardingNotifyChoice = 'telegram' | 'desktop_only';

export interface OnboardingNotifyMetadata {
  choice: OnboardingNotifyChoice;
  telegramConnected: boolean;
  telegramChatId?: string;
  telegramBotUsername?: string;
}

export interface OnboardingUseCaseDefaults {
  deliverables: OnboardingDeliverableId[];
  mode: OnboardingAutonomyMode;
}

export interface OnboardingFinalizeRequest {
  sessionId?: string;
  useCaseId: OnboardingUseCaseId;
  starterPrompt: string;
  responses: {
    step1_useCase: OnboardingUseCaseId;
    step2_data: {
      type: OnboardingDataChoiceId;
      sampleId?: string;
    };
    step3_deliverables: OnboardingDeliverableId[];
    step4_mode: OnboardingAutonomyMode;
    step5_model: string;
    step6_notify: OnboardingNotifyMetadata;
    step6_confirmed: true;
    step7_confirmed: true;
  };
}

export interface OnboardingState {
  step: OnboardingPrimaryStepId;
  useCaseId: OnboardingUseCaseId | null;
  dataChoiceId: OnboardingDataChoiceId;
  deliverables: OnboardingDeliverableId[];
  autonomyMode: OnboardingAutonomyMode;
  modelId: string | null;
}

export const ONBOARDING_PRIMARY_STEP_ORDER: readonly OnboardingPrimaryStepId[] = [
  'use_case',
  'data',
  'deliverables',
  'mode',
  'model',
  'notify',
  'confirm',
];

export function buildInitialOnboardingState(args: {
  defaultDataChoice: OnboardingDataChoiceId;
}): OnboardingState {
  return {
    step: 'use_case',
    useCaseId: null,
    dataChoiceId: args.defaultDataChoice,
    deliverables: [],
    autonomyMode: 'balanced',
    modelId: null,
  };
}

export function isOnboardingPrimaryStepId(value: unknown): value is OnboardingPrimaryStepId {
  return (
    typeof value === 'string'
    && ONBOARDING_PRIMARY_STEP_ORDER.includes(value as OnboardingPrimaryStepId)
  );
}

export function deriveUseCaseDefaults(useCaseId: OnboardingUseCaseId): OnboardingUseCaseDefaults {
  switch (useCaseId) {
    case 'data_analysis':
      return { deliverables: ['chart_summary'], mode: 'balanced' };
    case 'reporting':
      return { deliverables: ['report', 'presentation'], mode: 'controlled' };
    case 'prediction':
      return { deliverables: ['report', 'notebook'], mode: 'balanced' };
    case 'dashboard':
      return { deliverables: ['chart_summary', 'presentation'], mode: 'balanced' };
    case 'sql_exploration':
      return { deliverables: ['report'], mode: 'fast' };
    case 'weekly_kpi_triage':
      return { deliverables: ['report', 'presentation'], mode: 'fast' };
    case 'ab_test_analysis':
      return { deliverables: ['report', 'presentation'], mode: 'controlled' };
    case 'general':
    default:
      return { deliverables: ['report'], mode: 'balanced' };
  }
}

export function mapAutonomyModeToExecutionMode(
  mode: OnboardingAutonomyMode,
): OnboardingExecutionMode {
  if (mode === 'fast') return 'auto';
  if (mode === 'controlled') return 'step-by-step';
  return 'supervised';
}

export function mapExecutionModeToAutonomyMode(value: unknown): OnboardingAutonomyMode {
  if (value === 'auto') return 'fast';
  if (value === 'step-by-step') return 'controlled';
  return 'balanced';
}

export function mapAutonomyModeToQualityPreset(
  mode: OnboardingAutonomyMode,
): OnboardingQualityPreset {
  if (mode === 'fast') return 'fast';
  if (mode === 'controlled') return 'best_quality';
  return 'balanced';
}

export function buildOnboardingFinalizePayload(args: {
  sessionId?: string | null;
  useCaseId: OnboardingUseCaseId;
  starterPrompt: string;
  dataChoiceId: OnboardingDataChoiceId;
  deliverables: readonly OnboardingDeliverableId[];
  autonomyMode: OnboardingAutonomyMode;
  modelId: string;
  notifyChoice?: OnboardingNotifyChoice | null;
  telegramConnected?: boolean;
  telegramChatId?: string | null;
  telegramBotUsername?: string | null;
}): OnboardingFinalizeRequest {
  const notifyMetadata: OnboardingNotifyMetadata = {
    choice: args.notifyChoice ?? 'desktop_only',
    telegramConnected: Boolean(args.telegramConnected),
    ...(args.telegramChatId ? { telegramChatId: args.telegramChatId } : {}),
    ...(args.telegramBotUsername ? { telegramBotUsername: args.telegramBotUsername } : {}),
  };

  return {
    ...(args.sessionId ? { sessionId: args.sessionId } : {}),
    useCaseId: args.useCaseId,
    starterPrompt: args.starterPrompt,
    responses: {
      step1_useCase: args.useCaseId,
      step2_data: {
        type: args.dataChoiceId,
        ...(args.dataChoiceId === 'sample' ? { sampleId: `builtin:${args.useCaseId}` } : {}),
      },
      step3_deliverables: [...args.deliverables],
      step4_mode: args.autonomyMode,
      step5_model: args.modelId,
      step6_notify: notifyMetadata,
      step6_confirmed: true,
      step7_confirmed: true,
    },
  };
}

export function nextOnboardingStep(
  current: OnboardingPrimaryStepId,
): OnboardingPrimaryStepId | null {
  const index = ONBOARDING_PRIMARY_STEP_ORDER.indexOf(current);
  if (index < 0 || index >= ONBOARDING_PRIMARY_STEP_ORDER.length - 1) {
    return null;
  }
  return ONBOARDING_PRIMARY_STEP_ORDER[index + 1];
}

export function previousOnboardingStep(
  current: OnboardingPrimaryStepId,
): OnboardingPrimaryStepId | null {
  const index = ONBOARDING_PRIMARY_STEP_ORDER.indexOf(current);
  if (index <= 0) {
    return null;
  }
  return ONBOARDING_PRIMARY_STEP_ORDER[index - 1];
}

export function canAdvanceOnboardingStep(state: OnboardingState): boolean {
  switch (state.step) {
    case 'use_case':
      return state.useCaseId !== null;
    case 'data':
      return state.dataChoiceId !== 'database_deferred' || true;
    case 'deliverables':
      return state.deliverables.length > 0;
    case 'mode':
      return true;
    case 'model':
      return state.modelId !== null;
    case 'notify':
      return true;
    case 'confirm':
      return true;
    default:
      return false;
  }
}

export function applyUseCaseSelection(
  state: OnboardingState,
  useCaseId: OnboardingUseCaseId,
): OnboardingState {
  const defaults = deriveUseCaseDefaults(useCaseId);
  return {
    ...state,
    useCaseId,
    deliverables: defaults.deliverables,
    autonomyMode: defaults.mode,
  };
}

export function toggleDeliverable(
  state: OnboardingState,
  deliverableId: OnboardingDeliverableId,
): OnboardingState {
  const next = state.deliverables.includes(deliverableId)
    ? state.deliverables.filter((entry) => entry !== deliverableId)
    : [...state.deliverables, deliverableId];
  return { ...state, deliverables: next };
}
