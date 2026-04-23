/// <reference path="../../vite-env.d.ts" />

/**
 * Product onboarding wizard:
 * Wave 2 staged flow -> use case -> data -> deliverables -> mode -> model -> confirm.
 */

import { useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Bot,
  Check,
  ChevronRight,
  Database,
  FileText,
  LineChart,
  Loader2,
  LogIn,
  Presentation,
  Search,
  Upload,
} from 'lucide-react';
import { recommendModel } from '../../application/llm/recommendModel';
import type { OnboardingUseCaseId as SharedOnboardingUseCaseId } from '../../../shared/useCaseMapping';
import {
  NOOP_ONBOARDING_TELEMETRY,
  type OnboardingTelemetryPort,
} from '../../application/onboarding/onboardingTelemetry';
import { ONBOARDING_PRIMARY_STEP_ORDER } from '../../application/onboarding/onboardingState';
import type { ModelEntry, ModelGroup } from '../../hooks/useModels';
import { fetchAuthSnapshot } from '../../hooks/useProviderAuth';
import { configureRendererObservability } from '../../observability';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useConfigStore } from '../../stores/configStore';
import { useI18n, type Locale } from '../../stores/i18nStore';
import { describeModelAccess, type ModelAccessSummary } from '../../utils/modelAuth';
import { normalizeQualityPreset, type QualityPreset } from '../../utils/qualityPreset';
import { CapabilityBadge } from './CapabilityBadge';
import { LocaleSelector } from './LocaleSelector';

type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

export interface OnboardingResult {
  model: string;
  qualityPreset: QualityPreset;
  useCaseId: string | null;
  starterPrompt: string | null;
}

interface Props {
  onComplete: (result: OnboardingResult) => void;
  rpc: RpcFn;
  groups: ModelGroup[];
  telemetry?: OnboardingTelemetryPort;
}

export type OnboardingPrimaryStepId =
  | 'use_case'
  | 'data'
  | 'deliverables'
  | 'mode'
  | 'model'
  | 'confirm';
export type OnboardingDataChoiceId = 'upload' | 'sample' | 'database_deferred';
export type OnboardingDeliverableId = 'chart_summary' | 'report' | 'notebook' | 'presentation';
export type OnboardingAutonomyMode = 'fast' | 'balanced' | 'controlled';

type Step = OnboardingPrimaryStepId;
type ObservabilityChoice = 'none' | 'crash_only' | 'crash_and_telemetry';
type UseCaseId = SharedOnboardingUseCaseId;

interface UseCaseCard {
  id: UseCaseId;
  title: string;
  description: string;
  starterPrompt: string;
  systemContext: string;
  icon: typeof Bot;
}

interface CardOption<T extends string> {
  id: T;
  title: string;
  description: string;
  detail: string;
  icon: typeof Bot;
  disabled?: boolean;
}

interface OnboardingUseCaseDefaults {
  deliverables: OnboardingDeliverableId[];
  mode: OnboardingAutonomyMode;
}

export interface OnboardingFinalizeRequest {
  sessionId?: string;
  useCaseId: UseCaseId;
  starterPrompt: string;
  responses: {
    step1_useCase: UseCaseId;
    step2_data: {
      type: OnboardingDataChoiceId;
      sampleId?: string;
    };
    step3_deliverables: OnboardingDeliverableId[];
    step4_mode: OnboardingAutonomyMode;
    step5_model: string;
    step6_confirmed: true;
  };
}

interface OnboardingFinalizeResponse {
  sessionId: string;
  createdSession: boolean;
  goalSeeded: boolean;
  taskId?: string | null;
  mission?: Record<string, unknown>;
}

const NEEDS_API_KEY = new Set([
  'anthropic',
  'openai',
  'groq',
  'deepseek',
  'minimax',
  'qwen',
  'zhipu',
  'moonshot',
]);

const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';

export const ONBOARDING_PRIMARY_STEPS: ReadonlyArray<{
  id: OnboardingPrimaryStepId;
  label: string;
}> = [
  { id: 'use_case', label: 'Use Case' },
  { id: 'data', label: 'Data' },
  { id: 'deliverables', label: 'Deliverables' },
  { id: 'mode', label: 'Mode' },
  { id: 'model', label: 'Model' },
  { id: 'confirm', label: 'Confirm' },
];

function buildUseCases(
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): UseCaseCard[] {
  return [
    {
      id: 'data_analysis',
      title: t('onboarding.use_case.option.data_analysis.title'),
      description: t('onboarding.use_case.option.data_analysis.description'),
      starterPrompt: t('onboarding.use_case.option.data_analysis.starter_prompt'),
      systemContext: t('onboarding.use_case.option.data_analysis.system_context'),
      icon: Search,
    },
    {
      id: 'reporting',
      title: t('onboarding.use_case.option.reporting.title'),
      description: t('onboarding.use_case.option.reporting.description'),
      starterPrompt: t('onboarding.use_case.option.reporting.starter_prompt'),
      systemContext: t('onboarding.use_case.option.reporting.system_context'),
      icon: FileText,
    },
    {
      id: 'prediction',
      title: t('onboarding.use_case.option.prediction.title'),
      description: t('onboarding.use_case.option.prediction.description'),
      starterPrompt: t('onboarding.use_case.option.prediction.starter_prompt'),
      systemContext: t('onboarding.use_case.option.prediction.system_context'),
      icon: LineChart,
    },
    {
      id: 'dashboard',
      title: t('onboarding.use_case.option.dashboard.title'),
      description: t('onboarding.use_case.option.dashboard.description'),
      starterPrompt: t('onboarding.use_case.option.dashboard.starter_prompt'),
      systemContext: t('onboarding.use_case.option.dashboard.system_context'),
      icon: Presentation,
    },
    {
      id: 'sql_exploration',
      title: t('onboarding.use_case.option.sql_exploration.title'),
      description: t('onboarding.use_case.option.sql_exploration.description'),
      starterPrompt: t('onboarding.use_case.option.sql_exploration.starter_prompt'),
      systemContext: t('onboarding.use_case.option.sql_exploration.system_context'),
      icon: BarChart3,
    },
    {
      id: 'weekly_kpi_triage',
      title: t('onboarding.use_case.option.weekly_kpi_triage.title'),
      description: t('onboarding.use_case.option.weekly_kpi_triage.description'),
      starterPrompt: t('onboarding.use_case.option.weekly_kpi_triage.starter_prompt'),
      systemContext: t('onboarding.use_case.option.weekly_kpi_triage.system_context'),
      icon: BarChart3,
    },
    {
      id: 'ab_test_analysis',
      title: t('onboarding.use_case.option.ab_test_analysis.title'),
      description: t('onboarding.use_case.option.ab_test_analysis.description'),
      starterPrompt: t('onboarding.use_case.option.ab_test_analysis.starter_prompt'),
      systemContext: t('onboarding.use_case.option.ab_test_analysis.system_context'),
      icon: LineChart,
    },
    {
      id: 'general',
      title: t('onboarding.use_case.option.general.title'),
      description: t('onboarding.use_case.option.general.description'),
      starterPrompt: t('onboarding.use_case.option.general.starter_prompt'),
      systemContext: t('onboarding.use_case.option.general.system_context'),
      icon: Bot,
    },
  ];
}

function buildObservabilityChoices(
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): Array<{ id: ObservabilityChoice; title: string; description: string }> {
  return [
    {
      id: 'none',
      title: t('onboarding.privacy.option.none.title'),
      description: t('onboarding.privacy.option.none.description'),
    },
    {
      id: 'crash_only',
      title: t('onboarding.privacy.option.crash_only.title'),
      description: t('onboarding.privacy.option.crash_only.description'),
    },
    {
      id: 'crash_and_telemetry',
      title: t('onboarding.privacy.option.crash_and_telemetry.title'),
      description: t('onboarding.privacy.option.crash_and_telemetry.description'),
    },
  ];
}

function buildDataChoices(sampleApiAvailable: boolean): CardOption<OnboardingDataChoiceId>[] {
  return [
    {
      id: 'upload',
      title: 'Bring my own file',
      description: 'Start the mission now and upload your dataset in the workspace.',
      detail: 'Keeps the first handoff lightweight while preserving the current file-upload path.',
      icon: Upload,
    },
    {
      id: 'sample',
      title: 'Load a sample',
      description: sampleApiAvailable
        ? 'Seed the workspace with a sample dataset that matches this use case.'
        : 'Sample data is unavailable in this runtime.',
      detail: sampleApiAvailable
        ? 'Best for a fast first result and a guided starter prompt.'
        : 'Desktop sample assets are required for this option.',
      icon: BarChart3,
      disabled: !sampleApiAvailable,
    },
    {
      id: 'database_deferred',
      title: 'Connect data later',
      description: 'Define the mission first, then wire up a database or connector after launch.',
      detail: 'Aligned with PLAN_05 deferred database connection scope.',
      icon: Database,
    },
  ];
}

function buildDeliverableChoices(): CardOption<OnboardingDeliverableId>[] {
  return [
    {
      id: 'chart_summary',
      title: 'Chart summary',
      description: 'A compact visual readout with the key trends and drivers.',
      detail: 'Good for EDA, dashboard framing, and quick reviews.',
      icon: BarChart3,
    },
    {
      id: 'report',
      title: 'Report',
      description: 'A narrative analysis with findings, evidence, and recommended actions.',
      detail: 'Best when you need a decision-ready written deliverable.',
      icon: FileText,
    },
    {
      id: 'notebook',
      title: 'Notebook',
      description: 'A reproducible technical artifact with code, analysis, and outputs.',
      detail: 'Fits modeling, experimentation, and deployment preparation.',
      icon: LineChart,
    },
    {
      id: 'presentation',
      title: 'Presentation',
      description: 'A stakeholder-facing summary oriented around slides and talk tracks.',
      detail: 'Useful for reporting, leadership reviews, and dashboard narratives.',
      icon: Presentation,
    },
  ];
}

function buildAutonomyChoices(): CardOption<OnboardingAutonomyMode>[] {
  return [
    {
      id: 'fast',
      title: 'Fast',
      description: 'Move quickly with lighter checks and quicker model recommendations.',
      detail: 'Maps to the current auto execution mode.',
      icon: ChevronRight,
    },
    {
      id: 'balanced',
      title: 'Balanced',
      description: 'Default pace for most data-science work with practical guardrails.',
      detail: 'Maps to the current supervised execution mode.',
      icon: Bot,
    },
    {
      id: 'controlled',
      title: 'Controlled',
      description: 'Favor careful handoffs, deeper review, and stronger model quality.',
      detail: 'Maps to the current step-by-step execution mode.',
      icon: Check,
    },
  ];
}

export function deriveUseCaseDefaults(useCaseId: UseCaseId): OnboardingUseCaseDefaults {
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
): 'auto' | 'supervised' | 'step-by-step' {
  if (mode === 'fast') {
    return 'auto';
  }
  if (mode === 'controlled') {
    return 'step-by-step';
  }
  return 'supervised';
}

export function mapExecutionModeToAutonomyMode(value: unknown): OnboardingAutonomyMode {
  if (value === 'auto') {
    return 'fast';
  }
  if (value === 'step-by-step') {
    return 'controlled';
  }
  return 'balanced';
}

export function mapAutonomyModeToQualityPreset(mode: OnboardingAutonomyMode): QualityPreset {
  if (mode === 'fast') {
    return 'fast';
  }
  if (mode === 'controlled') {
    return 'best_quality';
  }
  return 'balanced';
}

export function buildOnboardingFinalizePayload(args: {
  sessionId?: string | null;
  useCaseId: UseCaseId;
  starterPrompt: string;
  dataChoiceId: OnboardingDataChoiceId;
  deliverables: readonly OnboardingDeliverableId[];
  autonomyMode: OnboardingAutonomyMode;
  modelId: string;
}): OnboardingFinalizeRequest {
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
      step6_confirmed: true,
    },
  };
}

export function canContinueFromModelSelection(args: {
  model: Pick<ModelEntry, 'provider'> | null;
  access: Pick<ModelAccessSummary, 'ready' | 'authType'> | null;
  apiKey: string;
  vaultAvailable: boolean;
}): boolean {
  if (!args.model || !args.access) {
    return false;
  }
  if (args.access.ready) {
    return true;
  }
  if (args.access.authType === 'oauth') {
    return false;
  }
  if (NEEDS_API_KEY.has(args.model.provider)) {
    return args.apiKey.trim().length > 0 && args.vaultAvailable;
  }
  return true;
}

function badgeClasses(ready: boolean): string {
  return ready ? 'bg-ds-success/15 text-ds-success' : 'bg-amber-500/15 text-amber-300';
}

function findUseCase(useCases: UseCaseCard[], useCaseId: string | null | undefined): UseCaseCard | null {
  if (!useCaseId) {
    return null;
  }
  return useCases.find((entry) => entry.id === useCaseId) ?? null;
}

function getConnectionHint(
  model: ModelEntry,
  ready: boolean,
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): string {
  if (ready) {
    return t('onboarding.connect.hint.ready');
  }
  if (model.authType === 'oauth') {
    return t('onboarding.connect.hint.oauth');
  }
  if (model.authType === 'local') {
    return t('onboarding.connect.hint.local');
  }
  return t('onboarding.connect.hint.api_key');
}

function getKeyPlaceholder(provider: string): string {
  const placeholders: Record<string, string> = {
    anthropic: 'sk-ant-...',
    openai: 'sk-...',
    groq: 'gsk_...',
    deepseek: 'sk-...',
    minimax: 'eyJ...',
    qwen: 'sk-...',
    zhipu: 'your-api-key',
    moonshot: 'sk-...',
  };
  return placeholders[provider] ?? 'your-api-key';
}

function hasCompletedOnboardingBefore(): boolean {
  try {
    return (
      localStorage.getItem(ONBOARDING_STORAGE_KEY) === 'true'
      || localStorage.getItem(LEGACY_ONBOARDING_STORAGE_KEY) === 'true'
    );
  } catch {
    return false;
  }
}

function observabilityChoiceFromSettings(
  errorReportingEnabled: boolean,
  telemetryEnabled: boolean,
): ObservabilityChoice {
  if (!errorReportingEnabled) {
    return 'none';
  }
  return telemetryEnabled ? 'crash_and_telemetry' : 'crash_only';
}

function observabilitySettingsFromChoice(choice: ObservabilityChoice): {
  errorReportingEnabled: boolean;
  telemetryEnabled: boolean;
} {
  if (choice === 'crash_and_telemetry') {
    return { errorReportingEnabled: true, telemetryEnabled: true };
  }
  if (choice === 'crash_only') {
    return { errorReportingEnabled: true, telemetryEnabled: false };
  }
  return { errorReportingEnabled: false, telemetryEnabled: false };
}

function getBackendBaseUrl(search = window.location.search): string {
  const params = new URLSearchParams(search);
  const rawPort = params.get('port');
  const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
  return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}

function extractApiErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }
  return fallback;
}

async function finalizeOnboardingHandoff(
  payload: OnboardingFinalizeRequest,
  search = window.location.search,
): Promise<OnboardingFinalizeResponse> {
  const response = await fetch(`${getBackendBaseUrl(search)}/api/onboarding/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(
      extractApiErrorMessage(body, `Onboarding finalize failed with status ${response.status}`),
    );
  }

  return (await response.json()) as OnboardingFinalizeResponse;
}

function formatDataChoiceTitle(choiceId: OnboardingDataChoiceId): string {
  if (choiceId === 'sample') {
    return 'Sample data';
  }
  if (choiceId === 'database_deferred') {
    return 'Connect later';
  }
  return 'Bring my own file';
}

function formatDeliverableTitle(choiceId: OnboardingDeliverableId): string {
  if (choiceId === 'chart_summary') {
    return 'Chart summary';
  }
  if (choiceId === 'report') {
    return 'Report';
  }
  if (choiceId === 'notebook') {
    return 'Notebook';
  }
  return 'Presentation';
}

function formatAutonomyModeTitle(choiceId: OnboardingAutonomyMode): string {
  if (choiceId === 'fast') {
    return 'Fast';
  }
  if (choiceId === 'controlled') {
    return 'Controlled';
  }
  return 'Balanced';
}

function SummaryCard({
  selectedUseCase,
  selectedDataChoiceId,
  selectedDeliverables,
  selectedAutonomyMode,
  selectedModel,
  selectedModelAccess,
}: {
  selectedUseCase: UseCaseCard | null;
  selectedDataChoiceId: OnboardingDataChoiceId;
  selectedDeliverables: OnboardingDeliverableId[];
  selectedAutonomyMode: OnboardingAutonomyMode;
  selectedModel: ModelEntry | null;
  selectedModelAccess: ModelAccessSummary | null;
}) {
  return (
    <div className="rounded-2xl border border-ds-border bg-ds-bg p-5">
      <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Mission Draft</div>
      <div className="mt-4 space-y-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Use case</div>
          <div className="mt-1 text-sm font-medium text-ds-text">
            {selectedUseCase?.title ?? 'Choose one goal to anchor the mission.'}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Data plan</div>
          <div className="mt-1 text-sm text-ds-text">{formatDataChoiceTitle(selectedDataChoiceId)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Deliverables</div>
          <div className="mt-1 text-sm text-ds-text">
            {selectedDeliverables.length > 0
              ? selectedDeliverables.map((entry) => formatDeliverableTitle(entry)).join(', ')
              : 'Pick at least one output.'}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Mode</div>
          <div className="mt-1 text-sm text-ds-text">{formatAutonomyModeTitle(selectedAutonomyMode)}</div>
          <div className="mt-1 text-[11px] leading-5 text-ds-muted">
            Runtime: {mapAutonomyModeToExecutionMode(selectedAutonomyMode)} / Model preference:{' '}
            {mapAutonomyModeToQualityPreset(selectedAutonomyMode)}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Model</div>
          <div className="mt-1 text-sm text-ds-text">
            {selectedModel?.displayName ?? 'Choose the model and connection path.'}
          </div>
          {selectedModelAccess && (
            <div className="mt-1 text-[11px] leading-5 text-ds-muted">
              {selectedModelAccess.providerLabel} / {selectedModelAccess.shortLabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function OnboardingWizard({ onComplete, rpc, groups, telemetry = NOOP_ONBOARDING_TELEMETRY }: Props) {
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const setAuthSnapshot = useAuthStore((s) => s.setSnapshot);
  const setPendingStarterPrompt = useConfigStore((s) => s.setPendingStarterPrompt);
  const setMode = useAgentStore((s) => s.setMode);
  const currentSessionId = useChatStore((s) => s.sessionId);
  const setSessionId = useChatStore((s) => s.setSessionId);
  const { locale, setLocale, t } = useI18n();
  const sampleApiAvailable = Boolean(window.electronAPI?.loadSampleForUseCase);

  const [step, setStep] = useState<Step>('use_case');
  const [selectedUseCaseId, setSelectedUseCaseId] = useState<UseCaseId | null>(null);
  const [selectedDataChoiceId, setSelectedDataChoiceId] = useState<OnboardingDataChoiceId>(
    sampleApiAvailable ? 'sample' : 'upload',
  );
  const [selectedDeliverables, setSelectedDeliverables] = useState<OnboardingDeliverableId[]>([]);
  const [selectedAutonomyMode, setSelectedAutonomyMode] = useState<OnboardingAutonomyMode>('balanced');
  const [selectedModel, setSelectedModel] = useState<ModelEntry | null>(null);
  const [observabilityChoice, setObservabilityChoice] = useState<ObservabilityChoice | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [oauthWaiting, setOauthWaiting] = useState(false);
  const [oauthError, setOauthError] = useState('');
  const [apiKeyError, setApiKeyError] = useState('');
  const [finishError, setFinishError] = useState('');
  const [vaultAvailable, setVaultAvailable] = useState(true);
  const [sentryConfigured, setSentryConfigured] = useState(false);
  const [finalizedSessionId, setFinalizedSessionId] = useState<string | null>(null);

  const allModels = useMemo(() => groups.flatMap((group) => group.models), [groups]);
  const useCases = useMemo(() => buildUseCases(t), [locale, t]);
  const dataChoices = useMemo(() => buildDataChoices(sampleApiAvailable), [sampleApiAvailable]);
  const deliverableChoices = useMemo(() => buildDeliverableChoices(), []);
  const autonomyChoices = useMemo(() => buildAutonomyChoices(), []);
  const observabilityChoices = useMemo(() => buildObservabilityChoices(t), [locale, t]);
  const selectedUseCase = useMemo(
    () => findUseCase(useCases, selectedUseCaseId),
    [selectedUseCaseId, useCases],
  );
  const selectedModelAccess = useMemo(
    () =>
      selectedModel
        ? describeModelAccess({
            modelId: selectedModel.id,
            modelEntry: selectedModel,
            providerStatuses,
            oauthStatuses,
          })
        : null,
    [oauthStatuses, providerStatuses, selectedModel],
  );
  const completedOnboardingBefore = useMemo(() => hasCompletedOnboardingBefore(), []);
  const readyModelIds = useMemo(
    () =>
      new Set(
        allModels
          .filter((entry) =>
            describeModelAccess({
              modelId: entry.id,
              modelEntry: entry,
              providerStatuses,
              oauthStatuses,
            }).ready,
          )
          .map((entry) => entry.id),
      ),
    [allModels, oauthStatuses, providerStatuses],
  );
  const recommendedModel = useMemo(
    () =>
      recommendModel(allModels, {
        locale,
        taskType: selectedUseCaseId,
        qualityPreset: mapAutonomyModeToQualityPreset(selectedAutonomyMode),
        readyModelIds,
      }),
    [allModels, locale, readyModelIds, selectedAutonomyMode, selectedUseCaseId],
  );
  const recommendedReason =
    recommendedModel?.reasons.map((reason) => t(`llm.recommend.reason.${reason}`)).join(' / ') ?? '';
  const canContinueFromModel = useMemo(
    () =>
      canContinueFromModelSelection({
        model: selectedModel,
        access: selectedModelAccess,
        apiKey,
        vaultAvailable: !window.electronAPI?.getSecretVaultStatus || vaultAvailable,
      }),
    [apiKey, selectedModel, selectedModelAccess, vaultAvailable],
  );

  useEffect(() => {
    telemetry({
      type: 'onboarding.started',
      alreadyCompletedBefore: completedOnboardingBefore,
    });
    // Telemetry "started" should fire exactly once per wizard mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const stepIndex = ONBOARDING_PRIMARY_STEP_ORDER.indexOf(step);
    if (stepIndex >= 0) {
      telemetry({ type: 'onboarding.step_entered', step, stepIndex });
    }
  }, [step, telemetry]);

  useEffect(() => {
    if (!window.electronAPI?.getSecretVaultStatus) {
      return;
    }

    void window.electronAPI
      .getSecretVaultStatus()
      .then((status) => {
        setVaultAvailable(status.available);
        if (!status.available) {
          setApiKeyError(status.error ?? t('onboarding.api_key.vault_unavailable'));
        }
      })
      .catch((error) => {
        console.warn('[OnboardingWizard] vault status lookup failed:', error);
      });
  }, [t]);

  useEffect(() => {
    let cancelled = false;

    void rpc('config.get')
      .then((result) => {
        if (cancelled) {
          return;
        }

        const config = result.config;
        if (!config || typeof config !== 'object') {
          return;
        }

        const configRecord = config as Record<string, unknown>;
        const agent =
          configRecord.agent && typeof configRecord.agent === 'object'
            ? (configRecord.agent as Record<string, unknown>)
            : null;
        const provider =
          configRecord.provider && typeof configRecord.provider === 'object'
            ? (configRecord.provider as Record<string, unknown>)
            : null;
        const observability =
          configRecord.observability && typeof configRecord.observability === 'object'
            ? (configRecord.observability as Record<string, unknown>)
            : null;

        const language = agent?.language;
        if (language === 'ko' || language === 'en' || language === 'ja') {
          if (language !== locale) {
            setLocale(language);
          }
        }

        const configuredMode = mapExecutionModeToAutonomyMode(agent?.mode);
        if (selectedUseCaseId === null) {
          setSelectedAutonomyMode(configuredMode);
        }

        if (!selectedUseCaseId) {
          const useCaseHint = typeof agent?.use_case_hint === 'string' ? agent.use_case_hint : null;
          const preselectedUseCase = findUseCase(useCases, useCaseHint);
          if (preselectedUseCase) {
            const defaults = deriveUseCaseDefaults(preselectedUseCase.id);
            setSelectedUseCaseId(preselectedUseCase.id);
            setSelectedDeliverables(defaults.deliverables);
            setSelectedAutonomyMode(configuredMode ?? defaults.mode);
          }
        }

        if (!selectedModel) {
          const defaultModel =
            typeof provider?.default_model === 'string' ? provider.default_model : null;
          const preselectedModel =
            defaultModel === null
              ? null
              : allModels.find((entry) => entry.id === defaultModel) ?? null;
          if (preselectedModel) {
            setSelectedModel(preselectedModel);
          }
        }

        const hasSentryDsn =
          typeof observability?.sentry_dsn === 'string' && observability.sentry_dsn.trim().length > 0;
        const nextErrorReporting = Boolean(observability?.error_reporting_enabled);
        const nextTelemetry = Boolean(observability?.telemetry_enabled);

        setSentryConfigured(hasSentryDsn);
        configureRendererObservability({
          sentryConfigured: hasSentryDsn,
          errorReportingEnabled: nextErrorReporting,
          telemetryEnabled: nextTelemetry,
        });
        setObservabilityChoice((current) => {
          if (current !== null) {
            return current;
          }
          if (completedOnboardingBefore || nextErrorReporting || nextTelemetry) {
            return observabilityChoiceFromSettings(nextErrorReporting, nextTelemetry);
          }
          return null;
        });
      })
      .catch((error) => {
        console.warn('[OnboardingWizard] config preload failed:', error);
      });

    return () => {
      cancelled = true;
    };
  }, [allModels, completedOnboardingBefore, locale, rpc, selectedModel, selectedUseCaseId, setLocale, useCases]);

  const handleLocaleChange = async (next: Locale) => {
    setLocale(next);
    try {
      await rpc('config.set', { path: 'agent.language', value: next });
    } catch (error) {
      console.warn('[OnboardingWizard] failed to sync agent.language:', error);
    }
  };

  const handleUseCaseSelect = (useCaseId: UseCaseId) => {
    const defaults = deriveUseCaseDefaults(useCaseId);
    setSelectedUseCaseId(useCaseId);
    setSelectedDeliverables(defaults.deliverables);
    setSelectedAutonomyMode(defaults.mode);
    setFinishError('');
    telemetry({ type: 'onboarding.use_case_selected', useCaseId });
  };

  const handleModelSelect = (model: ModelEntry) => {
    setSelectedModel(model);
    setApiKey('');
    setApiKeyError('');
    setOauthError('');
    setFinishError('');
  };

  const toggleDeliverable = (deliverableId: OnboardingDeliverableId) => {
    setFinishError('');
    setSelectedDeliverables((current) =>
      current.includes(deliverableId)
        ? current.filter((entry) => entry !== deliverableId)
        : [...current, deliverableId],
    );
  };

  const handleOAuthLogin = async () => {
    if (!selectedModel) {
      return;
    }

    setOauthWaiting(true);
    setOauthError('');

    try {
      await rpc('oauth.startLogin', { provider: selectedModel.provider });
      for (let index = 0; index < 300; index += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const statusResult = await rpc('oauth.status');
        const providerStatus =
          (statusResult.providers as Record<string, { authenticated: boolean }>)?.[
            selectedModel.provider
          ];
        if (providerStatus?.authenticated) {
          setAuthSnapshot(await fetchAuthSnapshot(rpc));
          return;
        }
      }
      setOauthError(t('onboarding.oauth.timeout'));
    } catch (error) {
      setOauthError(error instanceof Error ? error.message : String(error));
    } finally {
      setOauthWaiting(false);
    }
  };

  const handleFinish = async () => {
    if (!selectedModel || !selectedUseCase || observabilityChoice === null) {
      setFinishError(t('onboarding.error.choose_privacy'));
      return;
    }
    if (selectedDeliverables.length === 0) {
      setFinishError('Choose at least one deliverable before starting the mission.');
      return;
    }

    const qualityPreset = mapAutonomyModeToQualityPreset(selectedAutonomyMode);
    const executionMode = mapAutonomyModeToExecutionMode(selectedAutonomyMode);
    const observabilitySettings = observabilitySettingsFromChoice(observabilityChoice);
    const handoffSessionId = finalizedSessionId ?? currentSessionId;
    const shouldLoadSample = selectedDataChoiceId === 'sample' && sampleApiAvailable;

    setLoading(true);
    setApiKeyError('');
    setFinishError('');
    let starterPromptForChat = selectedUseCase.starterPrompt;
    const finalizeStartedAt = Date.now();
    telemetry({
      type: 'onboarding.finalize_started',
      useCaseId: selectedUseCase.id,
      dataChoiceId: selectedDataChoiceId,
      deliverables: selectedDeliverables,
      autonomyMode: selectedAutonomyMode,
      modelId: selectedModel.id,
    });

    try {
      if (
        apiKey.trim()
        && NEEDS_API_KEY.has(selectedModel.provider)
        && selectedModelAccess?.ready !== true
      ) {
        if (window.electronAPI?.setApiKey) {
          const result = await window.electronAPI.setApiKey(selectedModel.provider, apiKey.trim());
          if (!result.ok) {
            throw new Error(result.error ?? t('onboarding.error.api_key_save_failed'));
          }
        } else {
          await rpc('config.setApiKey', { provider: selectedModel.provider, key: apiKey.trim() });
        }
        setAuthSnapshot(await fetchAuthSnapshot(rpc));
      }

      await Promise.all([
        rpc('config.set', { path: 'provider.default_model', value: selectedModel.id }),
        rpc('config.set', { path: 'provider.quality_preset', value: qualityPreset }),
        rpc('config.set', { path: 'agent.mode', value: executionMode }),
        rpc('config.set', { path: 'agent.use_case_hint', value: selectedUseCase.id }),
        rpc('config.set', {
          path: 'agent.use_case_context',
          value: selectedUseCase.systemContext,
        }),
        rpc('config.set', {
          path: 'observability.error_reporting_enabled',
          value: observabilitySettings.errorReportingEnabled,
        }),
        rpc('config.set', {
          path: 'observability.telemetry_enabled',
          value: observabilitySettings.telemetryEnabled,
        }),
      ]);
      configureRendererObservability({
        sentryConfigured,
        errorReportingEnabled: observabilitySettings.errorReportingEnabled,
        telemetryEnabled: observabilitySettings.telemetryEnabled,
      });
      if (window.electronAPI?.updateObservability) {
        await window.electronAPI.updateObservability({
          errorReportingEnabled: observabilitySettings.errorReportingEnabled,
          telemetryEnabled: observabilitySettings.telemetryEnabled,
        });
      }

      if (shouldLoadSample) {
        if (!window.electronAPI?.loadSampleForUseCase) {
          throw new Error(t('onboarding.error.sample_desktop_only'));
        }
        const sampleResult = await window.electronAPI.loadSampleForUseCase(selectedUseCase.id);
        if (!sampleResult.ok) {
          throw new Error(sampleResult.error || t('onboarding.error.sample_load_failed'));
        }
        const uploaded = await rpc('files.upload', {
          name: sampleResult.sample.filename,
          data: sampleResult.sample.data,
        });
        const uploadedPath =
          typeof uploaded.path === 'string' ? uploaded.path : sampleResult.sample.filename;
        starterPromptForChat = t('onboarding.sample.prompt_anchor', {
          filename: sampleResult.sample.filename,
          path: uploadedPath,
          prompt: selectedUseCase.starterPrompt,
        });
      }

      const finalizePayload = buildOnboardingFinalizePayload({
        sessionId: handoffSessionId,
        useCaseId: selectedUseCase.id,
        starterPrompt: starterPromptForChat,
        dataChoiceId: selectedDataChoiceId,
        deliverables: selectedDeliverables,
        autonomyMode: selectedAutonomyMode,
        modelId: selectedModel.id,
      });
      const finalizeResult = await finalizeOnboardingHandoff(finalizePayload);
      if (!finalizeResult.sessionId || finalizeResult.sessionId.trim().length === 0) {
        throw new Error('Onboarding finalize did not return a session id.');
      }

      setFinalizedSessionId(finalizeResult.sessionId);
      setSessionId(finalizeResult.sessionId);
      setMode(executionMode);

      try {
        localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
        localStorage.setItem(LEGACY_ONBOARDING_STORAGE_KEY, 'true');
      } catch {
        // Ignore storage failures. The config write already succeeded.
      }

      setPendingStarterPrompt(starterPromptForChat);
      telemetry({
        type: 'onboarding.finalize_succeeded',
        useCaseId: selectedUseCase.id,
        modelId: selectedModel.id,
        durationMs: Date.now() - finalizeStartedAt,
      });
      onComplete({
        model: selectedModel.id,
        qualityPreset: normalizeQualityPreset(qualityPreset),
        useCaseId: selectedUseCase.id,
        starterPrompt: starterPromptForChat,
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setFinishError(reason);
      setLoading(false);
      telemetry({
        type: 'onboarding.finalize_failed',
        useCaseId: selectedUseCase?.id ?? null,
        modelId: selectedModel?.id ?? null,
        reason,
        durationMs: Date.now() - finalizeStartedAt,
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ds-bg px-4 py-8">
      <div className="w-full max-w-6xl">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-ds-accent/20">
            <Bot size={32} className="text-ds-accent" />
          </div>
          <h1 className="text-3xl font-bold text-ds-text">{t('onboarding.title')}</h1>
          <p className="mt-2 text-sm text-ds-muted">{t('onboarding.appSubtitle')}</p>
          <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ds-muted">
            Wave 2 onboarding: use case / data / deliverables / mode / model / mission start
          </p>
          <div className="mx-auto mt-5 max-w-xl rounded-2xl border border-ds-border bg-ds-surface p-4 text-left">
            <LocaleSelector
              value={locale}
              onChange={handleLocaleChange}
              labelKey="onboarding.locale.label"
              descriptionKey="onboarding.locale.description"
            />
          </div>
        </div>

        <div className="mb-6 grid gap-2 md:grid-cols-6">
          {ONBOARDING_PRIMARY_STEPS.map((entry, index) => {
            const activeIndex = ONBOARDING_PRIMARY_STEPS.findIndex(
              (stepEntry) => stepEntry.id === step,
            );
            const complete = index < activeIndex;
            const active = entry.id === step;

            return (
              <div
                key={entry.id}
                className={`rounded-xl border px-4 py-3 text-left ${
                  active || complete
                    ? 'border-ds-accent/40 bg-ds-accent/10'
                    : 'border-ds-border bg-ds-surface'
                }`}
              >
                <div className="text-[10px] uppercase tracking-[0.2em] text-ds-muted">
                  {t('onboarding.steps.label', { step: index + 1 })}
                </div>
                <div className="mt-1 text-sm font-medium text-ds-text">{entry.label}</div>
              </div>
            );
          })}
        </div>

        {step === 'use_case' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="mb-6">
              <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">
                {t('onboarding.use_case.eyebrow')}
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-ds-text">{t('onboarding.use_case.title')}</h2>
              <p className="mt-2 text-sm text-ds-muted">
                {t('onboarding.use_case.description')}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {useCases.map((useCase) => {
                const Icon = useCase.icon;
                const selected = selectedUseCase?.id === useCase.id;

                return (
                  <button
                    key={useCase.id}
                    type="button"
                    onClick={() => handleUseCaseSelect(useCase.id)}
                    className={`rounded-2xl border p-5 text-left transition-colors ${
                      selected
                        ? 'border-ds-accent/60 bg-ds-accent/10'
                        : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent">
                        <Icon size={18} />
                      </div>
                      <ChevronRight size={16} className="mt-1 text-ds-muted" />
                    </div>
                    <div className="mt-4 text-base font-medium text-ds-text">{useCase.title}</div>
                    <p className="mt-2 text-sm leading-6 text-ds-muted">{useCase.description}</p>
                    <div className="mt-4 rounded-xl border border-ds-border/60 bg-ds-surface p-3">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                        {t('onboarding.use_case.starter_prompt')}
                      </div>
                      <p className="mt-2 text-xs leading-5 text-ds-muted">{useCase.starterPrompt}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setStep('data')}
                disabled={!selectedUseCase}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
              >
                Continue
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {step === 'data' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Step 2</div>
                <h2 className="mt-2 text-2xl font-semibold text-ds-text">How will you start with data?</h2>
                <p className="mt-2 text-sm leading-6 text-ds-muted">
                  PLAN_05 targets three first-run paths here: bring your own file, load a sample, or
                  defer database setup until the mission is already framed.
                </p>

                <div className="mt-6 grid gap-4 md:grid-cols-3">
                  {dataChoices.map((choice) => {
                    const Icon = choice.icon;
                    const selected = selectedDataChoiceId === choice.id;

                    return (
                      <button
                        key={choice.id}
                        type="button"
                        disabled={choice.disabled}
                        onClick={() => {
                          setFinishError('');
                          setSelectedDataChoiceId(choice.id);
                        }}
                        className={`rounded-2xl border p-5 text-left transition-colors ${
                          selected
                            ? 'border-ds-accent/60 bg-ds-accent/10'
                            : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                        } ${choice.disabled ? 'cursor-not-allowed opacity-50' : ''}`}
                      >
                        <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent">
                          <Icon size={18} />
                        </div>
                        <div className="mt-4 text-base font-medium text-ds-text">{choice.title}</div>
                        <p className="mt-2 text-sm leading-6 text-ds-muted">{choice.description}</p>
                        <p className="mt-3 text-xs leading-5 text-ds-muted/80">{choice.detail}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <SummaryCard
                selectedUseCase={selectedUseCase}
                selectedDataChoiceId={selectedDataChoiceId}
                selectedDeliverables={selectedDeliverables}
                selectedAutonomyMode={selectedAutonomyMode}
                selectedModel={selectedModel}
                selectedModelAccess={selectedModelAccess}
              />
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep('use_case')}
                className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
              >
                Back to use case
              </button>
              <button
                type="button"
                onClick={() => setStep('deliverables')}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover"
              >
                Continue
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {step === 'deliverables' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Step 3</div>
                <h2 className="mt-2 text-2xl font-semibold text-ds-text">Which outputs matter first?</h2>
                <p className="mt-2 text-sm leading-6 text-ds-muted">
                  Select the deliverables that should shape the mission. You can choose more than one.
                </p>

                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  {deliverableChoices.map((choice) => {
                    const Icon = choice.icon;
                    const selected = selectedDeliverables.includes(choice.id);

                    return (
                      <button
                        key={choice.id}
                        type="button"
                        onClick={() => toggleDeliverable(choice.id)}
                        className={`rounded-2xl border p-5 text-left transition-colors ${
                          selected
                            ? 'border-ds-accent/60 bg-ds-accent/10'
                            : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent">
                            <Icon size={18} />
                          </div>
                          {selected && (
                            <span className="rounded-full bg-ds-success/15 px-2 py-0.5 text-[10px] font-medium text-ds-success">
                              Selected
                            </span>
                          )}
                        </div>
                        <div className="mt-4 text-base font-medium text-ds-text">{choice.title}</div>
                        <p className="mt-2 text-sm leading-6 text-ds-muted">{choice.description}</p>
                        <p className="mt-3 text-xs leading-5 text-ds-muted/80">{choice.detail}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <SummaryCard
                selectedUseCase={selectedUseCase}
                selectedDataChoiceId={selectedDataChoiceId}
                selectedDeliverables={selectedDeliverables}
                selectedAutonomyMode={selectedAutonomyMode}
                selectedModel={selectedModel}
                selectedModelAccess={selectedModelAccess}
              />
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep('data')}
                className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
              >
                Back to data
              </button>
              <button
                type="button"
                onClick={() => setStep('mode')}
                disabled={selectedDeliverables.length === 0}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
              >
                Continue
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {step === 'mode' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Step 4</div>
                <h2 className="mt-2 text-2xl font-semibold text-ds-text">How much autonomy should the agent use?</h2>
                <p className="mt-2 text-sm leading-6 text-ds-muted">
                  This step keeps the new Fast / Balanced / Controlled language aligned with the current
                  runtime modes and model-quality presets.
                </p>

                <div className="mt-6 grid gap-4 md:grid-cols-3">
                  {autonomyChoices.map((choice) => {
                    const Icon = choice.icon;
                    const selected = selectedAutonomyMode === choice.id;

                    return (
                      <button
                        key={choice.id}
                        type="button"
                        onClick={() => {
                          setFinishError('');
                          setSelectedAutonomyMode(choice.id);
                        }}
                        className={`rounded-2xl border p-5 text-left transition-colors ${
                          selected
                            ? 'border-ds-accent/60 bg-ds-accent/10'
                            : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                        }`}
                      >
                        <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ds-surface text-ds-accent">
                          <Icon size={18} />
                        </div>
                        <div className="mt-4 text-base font-medium text-ds-text">{choice.title}</div>
                        <p className="mt-2 text-sm leading-6 text-ds-muted">{choice.description}</p>
                        <p className="mt-3 text-xs leading-5 text-ds-muted/80">{choice.detail}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <SummaryCard
                selectedUseCase={selectedUseCase}
                selectedDataChoiceId={selectedDataChoiceId}
                selectedDeliverables={selectedDeliverables}
                selectedAutonomyMode={selectedAutonomyMode}
                selectedModel={selectedModel}
                selectedModelAccess={selectedModelAccess}
              />
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep('deliverables')}
                className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
              >
                Back to deliverables
              </button>
              <button
                type="button"
                onClick={() => setStep('model')}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover"
              >
                Continue
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {step === 'model' && selectedUseCase && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[0.95fr_1.45fr]">
              <SummaryCard
                selectedUseCase={selectedUseCase}
                selectedDataChoiceId={selectedDataChoiceId}
                selectedDeliverables={selectedDeliverables}
                selectedAutonomyMode={selectedAutonomyMode}
                selectedModel={selectedModel}
                selectedModelAccess={selectedModelAccess}
              />

              <div>
                <div className="mb-6">
                  <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Step 5</div>
                  <h2 className="mt-2 text-2xl font-semibold text-ds-text">Choose the model and connection path</h2>
                  <p className="mt-2 text-sm text-ds-muted">
                    Capability-first groups stay intact. Authentication remains inline here so the Wave 2
                    flow does not break the current provider path.
                  </p>
                </div>

                <div className="space-y-4">
                  {groups.map((group) => (
                    <div
                      key={group.id}
                      role="group"
                      aria-label={t(group.titleKey)}
                      className="overflow-hidden rounded-2xl border border-ds-border bg-ds-bg"
                    >
                      <div className="border-b border-ds-border px-4 py-3">
                        <div className="text-xs font-medium uppercase tracking-[0.18em] text-ds-muted">
                          {t(group.titleKey)}
                        </div>
                        <div className="mt-1 text-xs leading-5 text-ds-muted">
                          {t(group.descriptionKey)}
                        </div>
                      </div>

                      {group.models.length === 0 ? (
                        <div className="px-4 py-4 text-sm text-ds-muted">
                          <div className="font-medium text-ds-text">{t(group.emptyTitleKey)}</div>
                          <div className="mt-1 text-xs leading-5 text-ds-muted">
                            {t(group.emptyDescriptionKey)}
                          </div>
                        </div>
                      ) : (
                        group.models.map((entry) => {
                          const access = describeModelAccess({
                            modelId: entry.id,
                            modelEntry: entry,
                            providerStatuses,
                            oauthStatuses,
                          });
                          const isRecommended = recommendedModel?.model.id === entry.id;

                          return (
                            <button
                              key={entry.id}
                              type="button"
                              onClick={() => handleModelSelect(entry)}
                              className={`
                                flex w-full items-start justify-between gap-4 border-b border-ds-border/40
                                px-4 py-4 text-left transition-colors last:border-b-0
                                hover:bg-ds-accent/5
                                ${selectedModel?.id === entry.id ? 'bg-ds-accent/10' : ''}
                              `}
                            >
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <div className="text-sm font-medium text-ds-text">
                                    {entry.displayName}
                                  </div>
                                  {isRecommended && (
                                    <span className="rounded-full bg-ds-accent/10 px-2 py-0.5 text-[10px] font-medium text-ds-accent">
                                      {t('llm.recommend.badge')}
                                    </span>
                                  )}
                                </div>
                                <div className="mt-1 text-xs leading-5 text-ds-muted">
                                  {getConnectionHint(entry, access.ready, t)}
                                </div>
                                <div className="mt-2 flex flex-wrap gap-1">
                                  {entry.badges.map((badge) => (
                                    <CapabilityBadge key={`${entry.id}-${badge}`} badge={badge} />
                                  ))}
                                </div>
                                {isRecommended && recommendedReason && (
                                  <div className="mt-2 text-[11px] leading-5 text-ds-accent">
                                    {recommendedReason}
                                  </div>
                                )}
                                <div className="mt-2 text-[11px] leading-5 text-ds-muted/80">
                                  {access.providerLabel} / {access.authTypeLabel}
                                </div>
                                <div className="mt-1 text-[11px] leading-5 text-ds-muted/80">
                                  {access.detail}
                                </div>
                              </div>
                              <div className="flex shrink-0 flex-col items-end gap-2">
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeClasses(
                                    access.ready,
                                  )}`}
                                >
                                  {access.shortLabel}
                                </span>
                                <ChevronRight size={16} className="text-ds-muted" />
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  ))}

                  {groups.length === 0 && (
                    <div className="rounded-2xl border border-ds-border bg-ds-bg p-8 text-center">
                      <Loader2 size={20} className="mx-auto mb-3 animate-spin text-ds-accent" />
                      <p className="text-sm text-ds-muted">{t('onboarding.connect.loading')}</p>
                    </div>
                  )}
                </div>

                {selectedModel && selectedModelAccess && (
                  <div className="mt-6 rounded-2xl border border-ds-border bg-ds-bg p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="text-sm font-medium text-ds-text">{selectedModel.displayName}</div>
                        <p className="mt-1 text-xs leading-5 text-ds-muted">{selectedModelAccess.detail}</p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeClasses(
                          selectedModelAccess.ready,
                        )}`}
                      >
                        {selectedModelAccess.shortLabel}
                      </span>
                    </div>

                    {selectedModelAccess.authType === 'oauth' && !selectedModelAccess.ready && (
                      <div className="mt-5">
                        {oauthWaiting ? (
                          <div className="rounded-xl border border-ds-border bg-ds-surface px-4 py-5 text-center">
                            <Loader2 size={20} className="mx-auto mb-3 animate-spin text-ds-accent" />
                            <p className="text-sm text-ds-muted">{t('onboarding.oauth.waiting')}</p>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void handleOAuthLogin()}
                            className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover"
                          >
                            <LogIn size={16} />
                            {t('onboarding.oauth.start')}
                          </button>
                        )}
                        {oauthError && <p className="mt-4 text-xs text-red-400">{oauthError}</p>}
                      </div>
                    )}

                    {selectedModelAccess.authType !== 'oauth' && !selectedModelAccess.ready && NEEDS_API_KEY.has(selectedModel.provider) && (
                      <div className="mt-5">
                        {!vaultAvailable && window.electronAPI?.getSecretVaultStatus && (
                          <p className="mb-3 text-xs text-red-400">
                            {apiKeyError || t('onboarding.api_key.vault_unavailable')}
                          </p>
                        )}

                        <label className="block text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                          API key
                        </label>
                        <input
                          type="password"
                          value={apiKey}
                          onChange={(event) => setApiKey(event.target.value)}
                          placeholder={getKeyPlaceholder(selectedModel.provider)}
                          className="mt-3 w-full rounded-xl border border-ds-border bg-ds-surface px-4 py-3 text-sm text-ds-text placeholder:text-ds-muted/50 focus:border-ds-accent focus:outline-none"
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' && canContinueFromModel) {
                              setStep('confirm');
                            }
                          }}
                        />
                        <p className="mt-3 text-xs leading-5 text-ds-muted">
                          The key is stored during the final handoff so the current provider connection
                          flow stays unchanged.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-6 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setStep('mode')}
                    className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
                  >
                    Back to mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep('confirm')}
                    disabled={!canContinueFromModel}
                    className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Continue
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 'confirm' && selectedModel && selectedUseCase && (
          <div className="mx-auto max-w-4xl rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-ds-success/20">
              <Check size={24} className="text-ds-success" />
            </div>
            <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Step 6</div>
            <h2 className="mt-2 text-2xl font-semibold text-ds-text">Confirm the mission handoff</h2>
            <p className="mt-3 text-sm leading-6 text-ds-muted">
              This final step bootstraps the backend session, preserves the current provider connection
              path, and stages the first prompt so Mission can take over immediately.
            </p>

            <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-2xl border border-ds-border bg-ds-bg p-5">
                <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Mission card</div>
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="text-sm font-medium text-ds-text">{selectedUseCase.title}</div>
                    <p className="mt-1 text-xs leading-5 text-ds-muted">{selectedUseCase.description}</p>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Data</div>
                    <p className="mt-1 text-sm text-ds-text">{formatDataChoiceTitle(selectedDataChoiceId)}</p>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Deliverables</div>
                    <p className="mt-1 text-sm text-ds-text">
                      {selectedDeliverables.map((entry) => formatDeliverableTitle(entry)).join(', ')}
                    </p>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Autonomy</div>
                    <p className="mt-1 text-sm text-ds-text">
                      {formatAutonomyModeTitle(selectedAutonomyMode)} / {mapAutonomyModeToExecutionMode(selectedAutonomyMode)}
                    </p>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Model</div>
                    <p className="mt-1 text-sm text-ds-text">{selectedModel.displayName}</p>
                    {selectedModelAccess && (
                      <p className="mt-1 text-[11px] leading-5 text-ds-muted">
                        {selectedModelAccess.providerLabel} / {selectedModelAccess.shortLabel}
                      </p>
                    )}
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                      {t('onboarding.done.suggested_prompt')}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ds-text">{selectedUseCase.starterPrompt}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-ds-border bg-ds-bg p-5 text-left">
                <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                  {t('onboarding.privacy.eyebrow')}
                </div>
                <div className="mt-2 text-base font-medium text-ds-text">{t('onboarding.privacy.title')}</div>
                <p className="mt-2 text-sm leading-6 text-ds-muted">{t('onboarding.privacy.description')}</p>
                {!sentryConfigured && (
                  <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                    {t('onboarding.privacy.not_configured')}
                  </div>
                )}
                <div className="mt-4 grid gap-3">
                  {observabilityChoices.map((choice) => {
                    const selected = observabilityChoice === choice.id;
                    return (
                      <button
                        key={choice.id}
                        type="button"
                        onClick={() => {
                          setFinishError('');
                          setObservabilityChoice(choice.id);
                        }}
                        className={`rounded-2xl border p-4 text-left transition-colors ${
                          selected
                            ? 'border-ds-accent/60 bg-ds-accent/10'
                            : 'border-ds-border bg-ds-surface hover:border-ds-accent/40 hover:bg-ds-accent/5'
                        }`}
                      >
                        <div className="text-sm font-medium text-ds-text">{choice.title}</div>
                        <p className="mt-2 text-xs leading-5 text-ds-muted">{choice.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {selectedDataChoiceId === 'sample' && sampleApiAvailable && (
              <div className="mt-4 rounded-2xl border border-ds-accent/30 bg-ds-accent/5 p-5 text-left">
                <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                  {t('onboarding.sample.eyebrow')}
                </div>
                <p className="mt-2 text-sm leading-6 text-ds-text">{t('onboarding.sample.description')}</p>
              </div>
            )}

            {finishError && <p className="mt-4 text-xs text-red-400">{finishError}</p>}

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={() => setStep('model')}
                className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
              >
                Back to model
              </button>
              <button
                type="button"
                onClick={() => void handleFinish()}
                disabled={loading || observabilityChoice === null}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-ds-accent px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    {selectedDataChoiceId === 'sample' && sampleApiAvailable
                      ? t('onboarding.sample.preparing')
                      : t('onboarding.done.start')}
                  </>
                ) : (
                  selectedDataChoiceId === 'sample' && sampleApiAvailable
                    ? t('onboarding.sample.try')
                    : t('onboarding.done.start')
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
