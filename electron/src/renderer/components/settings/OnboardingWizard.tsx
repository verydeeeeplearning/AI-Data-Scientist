/**
 * Product onboarding wizard:
 * welcome -> use case -> AI connection -> ready.
 */

import { useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Bot,
  Check,
  ChevronRight,
  FileText,
  Globe,
  Key,
  LineChart,
  Loader2,
  LogIn,
  Monitor,
  Presentation,
  Search,
} from 'lucide-react';
import type { ModelEntry, ModelGroup } from '../../hooks/useModels';
import { fetchAuthSnapshot } from '../../hooks/useProviderAuth';
import { configureRendererObservability } from '../../observability';
import { useAuthStore } from '../../stores/authStore';
import { useConfigStore } from '../../stores/configStore';
import { describeModelAccess } from '../../utils/modelAuth';
import { normalizeQualityPreset, type QualityPreset } from '../../utils/qualityPreset';

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
}

type Step = 'welcome' | 'use_case' | 'connect' | 'apikey' | 'oauth' | 'done';
type ObservabilityChoice = 'none' | 'crash_only' | 'crash_and_telemetry';
type UseCaseId =
  | 'data_analysis'
  | 'reporting'
  | 'prediction'
  | 'dashboard'
  | 'sql_exploration'
  | 'general';

interface UseCaseCard {
  id: UseCaseId;
  title: string;
  description: string;
  starterPrompt: string;
  systemContext: string;
  icon: typeof Bot;
}

const PRIMARY_STEPS: Array<{ id: 'welcome' | 'use_case' | 'connect' | 'done'; label: string }> = [
  { id: 'welcome', label: 'Start' },
  { id: 'use_case', label: 'Goal' },
  { id: 'connect', label: 'Connect' },
  { id: 'done', label: 'Ready' },
];

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

const GROUP_ICONS: Record<string, typeof Globe> = {
  oauth: Globe,
  free_api_key: Key,
  api_key: Key,
  local: Monitor,
};

const GROUP_TITLES: Record<string, string> = {
  oauth: 'Sign in',
  free_api_key: 'Use a free key',
  api_key: 'Use an account key',
  local: 'Run on this computer',
};

const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';

const USE_CASES: UseCaseCard[] = [
  {
    id: 'data_analysis',
    title: 'Explore uploaded data',
    description: 'Start with CSV or Excel files, inspect quality, and surface the most useful patterns.',
    starterPrompt:
      'Summarize my dataset, highlight quality issues, and tell me which patterns are worth checking first.',
    systemContext:
      'The user mainly wants fast exploratory analysis of CSV or Excel data. Prefer plain language, quick wins, and concrete next steps over heavy theory.',
    icon: Search,
  },
  {
    id: 'reporting',
    title: 'Write a report',
    description: 'Turn analysis into a concise memo, business summary, or stakeholder update.',
    starterPrompt:
      'Turn the key findings into a short business report with the main takeaways, risks, and recommended actions.',
    systemContext:
      'The user is focused on communicating results. Favor concise summaries, decision-ready structure, and clear recommendations.',
    icon: FileText,
  },
  {
    id: 'prediction',
    title: 'Build a prediction',
    description: 'Train a baseline model, compare options, and explain what drives performance.',
    starterPrompt:
      'Help me set up a predictive modeling plan, build a strong baseline, and explain the main drivers of performance.',
    systemContext:
      'The user is interested in predictive modeling. Establish simple baselines first, explain tradeoffs clearly, and keep methodology rigorous but approachable.',
    icon: LineChart,
  },
  {
    id: 'dashboard',
    title: 'Plan charts or dashboards',
    description: 'Find the right visual story, metrics, and layout for a recurring reporting view.',
    starterPrompt:
      'Recommend the right charts, headline metrics, and dashboard structure for this analysis.',
    systemContext:
      'The user wants visual communication support. Emphasize chart selection, metric framing, and dashboard-friendly outputs.',
    icon: Presentation,
  },
  {
    id: 'sql_exploration',
    title: 'Explore warehouse data',
    description: 'Work from database tables, ask better questions, and validate findings carefully.',
    starterPrompt:
      'Help me inspect the available tables, form the right questions, and validate the first useful SQL analysis steps.',
    systemContext:
      'The user is likely exploring warehouse data. Favor schema discovery, careful validation, and readable explanations of joins, filters, and caveats.',
    icon: BarChart3,
  },
  {
    id: 'general',
    title: 'General help',
    description: 'Keep the setup flexible and start with a broad assistant that adapts as the work becomes clearer.',
    starterPrompt:
      'Help me figure out the best next step for this data task and guide me through the most sensible workflow.',
    systemContext:
      'The user has a broad or still-forming goal. Start by clarifying the task, suggest a sensible first step, and adapt from there.',
    icon: Bot,
  },
];

const OBSERVABILITY_CHOICES: Array<{
  id: ObservabilityChoice;
  title: string;
  description: string;
}> = [
  {
    id: 'none',
    title: 'Keep both off',
    description: 'Do not send crash reports or performance telemetry.',
  },
  {
    id: 'crash_only',
    title: 'Share crash reports only',
    description: 'Send redacted exceptions so repeated failures can be fixed faster.',
  },
  {
    id: 'crash_and_telemetry',
    title: 'Share crash reports and telemetry',
    description: 'Also share low-rate traces for startup, RPC, and UI performance.',
  },
];

function badgeClasses(ready: boolean): string {
  return ready ? 'bg-ds-success/15 text-ds-success' : 'bg-amber-500/15 text-amber-300';
}

function majorStep(step: Step): 'welcome' | 'use_case' | 'connect' | 'done' {
  if (step === 'apikey' || step === 'oauth') {
    return 'connect';
  }
  return step;
}

function findUseCase(useCaseId: string | null | undefined): UseCaseCard | null {
  if (!useCaseId) {
    return null;
  }
  return USE_CASES.find((entry) => entry.id === useCaseId) ?? null;
}

function getConnectionHint(model: ModelEntry, ready: boolean): string {
  if (ready) {
    return 'Ready to use right away.';
  }
  if (model.authType === 'oauth') {
    return 'Sign in once in your browser to continue.';
  }
  if (model.authType === 'local') {
    return 'Runs on this computer without a cloud account.';
  }
  return 'Add your key once, then start analyzing.';
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
  telemetryEnabled: boolean
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

export function OnboardingWizard({ onComplete, rpc, groups }: Props) {
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const setAuthSnapshot = useAuthStore((s) => s.setSnapshot);
  const setPendingStarterPrompt = useConfigStore((s) => s.setPendingStarterPrompt);
  const [step, setStep] = useState<Step>('welcome');
  const [selectedUseCase, setSelectedUseCase] = useState<UseCaseCard | null>(null);
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

  const allModels = useMemo(() => groups.flatMap((group) => group.models), [groups]);
  const activePrimaryStep = majorStep(step);
  const completedOnboardingBefore = useMemo(() => hasCompletedOnboardingBefore(), []);

  useEffect(() => {
    if (!window.electronAPI?.getSecretVaultStatus) {
      return;
    }

    void window.electronAPI
      .getSecretVaultStatus()
      .then((status) => {
        setVaultAvailable(status.available);
        if (!status.available) {
          setApiKeyError(status.error ?? 'Desktop secure storage is unavailable.');
        }
      })
      .catch((error) => {
        console.warn('[OnboardingWizard] vault status lookup failed:', error);
      });
  }, []);

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

        if (!selectedUseCase) {
          const useCaseHint = typeof agent?.use_case_hint === 'string' ? agent.use_case_hint : null;
          const preselectedUseCase = findUseCase(useCaseHint);
          if (preselectedUseCase) {
            setSelectedUseCase(preselectedUseCase);
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
  }, [allModels, completedOnboardingBefore, rpc, selectedModel, selectedUseCase]);

  const handleModelSelect = (model: ModelEntry) => {
    setFinishError('');
    setSelectedModel(model);
    const access = describeModelAccess({
      modelId: model.id,
      modelEntry: model,
      providerStatuses,
      oauthStatuses,
    });

    if (access.ready) {
      setStep('done');
      return;
    }

    if (NEEDS_API_KEY.has(model.provider)) {
      setStep('apikey');
      return;
    }

    if (access.authType === 'oauth') {
      setStep('oauth');
      return;
    }

    setStep('done');
  };

  const handleOAuthLogin = async () => {
    if (!selectedModel) {
      return;
    }

    setOauthWaiting(true);
    setOauthError('');

    try {
      await rpc('oauth.startLogin', { provider: selectedModel.provider });
      for (let i = 0; i < 300; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const statusResult = await rpc('oauth.status');
        const providerStatus =
          (statusResult.providers as Record<string, { authenticated: boolean }>)?.[
            selectedModel.provider
          ];
        if (providerStatus?.authenticated) {
          setAuthSnapshot(await fetchAuthSnapshot(rpc));
          setStep('done');
          return;
        }
      }
      setOauthError('Login timed out. Please try again.');
    } catch (error) {
      setOauthError(error instanceof Error ? error.message : String(error));
    } finally {
      setOauthWaiting(false);
    }
  };

  const handleApiKeySubmit = () => {
    if (!apiKey.trim()) {
      return;
    }
    setApiKeyError('');
    setFinishError('');
    setStep('done');
  };

  const sampleApiAvailable = Boolean(window.electronAPI?.loadSampleForUseCase);

  const handleFinish = async (options: { withSample?: boolean } = {}) => {
    const withSample = options.withSample === true;
    if (!selectedModel || !selectedUseCase || observabilityChoice === null) {
      setFinishError('Choose a privacy setting before you continue.');
      return;
    }

    const observabilitySettings = observabilitySettingsFromChoice(observabilityChoice);
    setLoading(true);
    setApiKeyError('');
    setFinishError('');
    let onboardingResult: OnboardingResult | null = null;
    let starterPromptForChat = selectedUseCase.starterPrompt;

    try {
      if (apiKey.trim() && NEEDS_API_KEY.has(selectedModel.provider)) {
        if (window.electronAPI?.setApiKey) {
          const result = await window.electronAPI.setApiKey(selectedModel.provider, apiKey.trim());
          if (!result.ok) {
            throw new Error(result.error ?? 'Failed to save API key.');
          }
        } else {
          await rpc('config.setApiKey', { provider: selectedModel.provider, key: apiKey.trim() });
        }
        setAuthSnapshot(await fetchAuthSnapshot(rpc));
      }

      await Promise.all([
        rpc('config.set', { path: 'provider.default_model', value: selectedModel.id }),
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

      // Phase 3: load a use-case-specific sample CSV and upload it into the
      // agent's workspace so the very first analysis has data to act on.
      if (withSample) {
        if (!window.electronAPI?.loadSampleForUseCase) {
          throw new Error('Sample datasets are only available in the desktop app.');
        }
        const sampleResult = await window.electronAPI.loadSampleForUseCase(selectedUseCase.id);
        if (!sampleResult.ok) {
          throw new Error(sampleResult.error || 'Failed to load sample dataset.');
        }
        const uploaded = await rpc('files.upload', {
          name: sampleResult.sample.filename,
          data: sampleResult.sample.data,
        });
        const uploadedPath =
          typeof uploaded.path === 'string' ? uploaded.path : sampleResult.sample.filename;
        // Anchor the starter prompt to the file we just uploaded so the agent
        // doesn't have to guess what dataset the user means.
        starterPromptForChat = `Use the file ${sampleResult.sample.filename} that was just uploaded (${uploadedPath}). ${selectedUseCase.starterPrompt}`;
      }

      const status = await rpc('status.get');
      onboardingResult = {
        model: selectedModel.id,
        qualityPreset: normalizeQualityPreset(status.qualityPreset),
        useCaseId: selectedUseCase.id,
        starterPrompt: starterPromptForChat,
      };
    } catch (error) {
      setFinishError(error instanceof Error ? error.message : String(error));
      setLoading(false);
      return;
    }

    try {
      localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
      localStorage.setItem(LEGACY_ONBOARDING_STORAGE_KEY, 'true');
    } catch {
      // Ignore storage failures. The config write already succeeded.
    }

    // Hand the chat input a starter prompt so the first analysis is one click away.
    setPendingStarterPrompt(starterPromptForChat);

    if (onboardingResult) {
      onComplete(onboardingResult);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ds-bg px-4 py-8">
      <div className="w-full max-w-5xl">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-ds-accent/20">
            <Bot size={32} className="text-ds-accent" />
          </div>
          <h1 className="text-3xl font-bold text-ds-text">DS Agent</h1>
          <p className="mt-2 text-sm text-ds-muted">
            Set your goal first. The agent will adapt its tone and outputs around that context.
          </p>
        </div>

        <div className="mb-6 grid gap-2 md:grid-cols-4">
          {PRIMARY_STEPS.map((entry, index) => {
            const activeIndex = PRIMARY_STEPS.findIndex((stepEntry) => stepEntry.id === activePrimaryStep);
            const complete = index < activeIndex;
            const active = entry.id === activePrimaryStep;

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
                  Step {index + 1}
                </div>
                <div className="mt-1 text-sm font-medium text-ds-text">{entry.label}</div>
              </div>
            );
          })}
        </div>

        {step === 'welcome' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]">
              <div>
                <div className="text-xs uppercase tracking-[0.25em] text-ds-muted">First run</div>
                <h2 className="mt-3 text-2xl font-semibold text-ds-text">
                  Start with the kind of work you want to do.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-ds-muted">
                  This setup does not lock the agent into a fixed workflow. It gives the agent better
                  context so it can explain results in the right tone, surface the right outputs, and
                  start from the most useful framing.
                </p>
                <button
                  onClick={() => setStep('use_case')}
                  className="
                    mt-6 inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3
                    text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover
                  "
                >
                  Continue
                  <ChevronRight size={16} />
                </button>
              </div>

              <div className="rounded-2xl border border-ds-border/60 bg-ds-bg p-5">
                <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">What changes</div>
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="text-sm font-medium text-ds-text">Clearer language</div>
                    <p className="mt-1 text-xs leading-5 text-ds-muted">
                      Exploration, reporting, and modeling each get different wording and emphasis.
                    </p>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-ds-text">Better default outputs</div>
                    <p className="mt-1 text-xs leading-5 text-ds-muted">
                      The agent leans toward the report, chart, summary, or modeling artifacts that fit
                      your job to be done.
                    </p>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-ds-text">Still fully autonomous</div>
                    <p className="mt-1 text-xs leading-5 text-ds-muted">
                      The setup influences context only. It does not hard-code a path through the
                      workflow.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 'use_case' && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="mb-6">
              <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Goal</div>
              <h2 className="mt-2 text-2xl font-semibold text-ds-text">
                What do you want the agent to help with most often?
              </h2>
              <p className="mt-2 text-sm text-ds-muted">
                Pick the closest fit. You can change this later from Settings.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {USE_CASES.map((useCase) => {
                const Icon = useCase.icon;
                const selected = selectedUseCase?.id === useCase.id;

                return (
                  <button
                    key={useCase.id}
                    onClick={() => {
                      setSelectedUseCase(useCase);
                      setStep('connect');
                    }}
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
                        Starter prompt
                      </div>
                      <p className="mt-2 text-xs leading-5 text-ds-muted">{useCase.starterPrompt}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {step === 'connect' && selectedUseCase && (
          <div className="rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_1.4fr]">
              <div className="rounded-2xl border border-ds-border bg-ds-bg p-5">
                <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Selected goal</div>
                <div className="mt-3 text-xl font-semibold text-ds-text">{selectedUseCase.title}</div>
                <p className="mt-2 text-sm leading-6 text-ds-muted">{selectedUseCase.description}</p>

                <div className="mt-5 rounded-xl border border-ds-border/60 bg-ds-surface p-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                    Starter prompt
                  </div>
                  <p className="mt-2 text-xs leading-5 text-ds-muted">
                    {selectedUseCase.starterPrompt}
                  </p>
                </div>

                <button
                  onClick={() => setStep('use_case')}
                  className="mt-5 text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
                >
                  Back to goal selection
                </button>
              </div>

              <div>
                <div className="mb-6">
                  <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Connect</div>
                  <h2 className="mt-2 text-2xl font-semibold text-ds-text">
                    Choose how you want to connect AI.
                  </h2>
                  <p className="mt-2 text-sm text-ds-muted">
                    You can change this later. The agent will keep the goal context you just chose.
                  </p>
                </div>

                <div className="space-y-4">
                  {groups.map((group) => {
                    const Icon = GROUP_ICONS[group.authType] ?? Key;
                    return (
                      <div
                        key={group.authType}
                        className="overflow-hidden rounded-2xl border border-ds-border bg-ds-bg"
                      >
                        <div className="flex items-center gap-2 border-b border-ds-border px-4 py-3">
                          <Icon size={14} className="text-ds-muted" />
                          <span className="text-xs font-medium uppercase tracking-[0.18em] text-ds-muted">
                            {GROUP_TITLES[group.authType] ?? group.title}
                          </span>
                        </div>

                        {group.models.map((entry) => {
                          const access = describeModelAccess({
                            modelId: entry.id,
                            modelEntry: entry,
                            providerStatuses,
                            oauthStatuses,
                          });

                          return (
                            <button
                              key={entry.id}
                              onClick={() => handleModelSelect(entry)}
                              className={`
                                flex w-full items-start justify-between gap-4 border-b border-ds-border/40
                                px-4 py-4 text-left transition-colors last:border-b-0
                                hover:bg-ds-accent/5
                                ${selectedModel?.id === entry.id ? 'bg-ds-accent/10' : ''}
                              `}
                            >
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-ds-text">
                                  {entry.displayName}
                                </div>
                                <div className="mt-1 text-xs leading-5 text-ds-muted">
                                  {getConnectionHint(entry, access.ready)}
                                </div>
                                <div className="mt-2 text-[11px] leading-5 text-ds-muted/80">
                                  {access.detail}
                                </div>
                              </div>
                              <div className="flex shrink-0 flex-col items-end gap-2">
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeClasses(
                                    access.ready
                                  )}`}
                                >
                                  {access.shortLabel}
                                </span>
                                <ChevronRight size={16} className="text-ds-muted" />
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    );
                  })}

                  {groups.length === 0 && (
                    <div className="rounded-2xl border border-ds-border bg-ds-bg p-8 text-center">
                      <Loader2 size={20} className="mx-auto mb-3 animate-spin text-ds-accent" />
                      <p className="text-sm text-ds-muted">Loading connection options...</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 'oauth' && selectedModel && (
          <div className="mx-auto max-w-xl rounded-2xl border border-ds-border bg-ds-surface p-8 text-center">
            <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Connect</div>
            <h2 className="mt-2 text-2xl font-semibold text-ds-text">
              Sign in to continue with {selectedModel.displayName}.
            </h2>
            <p className="mt-2 text-sm leading-6 text-ds-muted">
              This opens a browser-based sign-in flow. When it completes, the desktop app will return
              here automatically.
            </p>

            {oauthWaiting ? (
              <div className="py-8">
                <Loader2 size={24} className="mx-auto mb-3 animate-spin text-ds-accent" />
                <p className="text-sm text-ds-muted">Waiting for sign-in to complete...</p>
              </div>
            ) : (
              <button
                onClick={() => void handleOAuthLogin()}
                className="
                  mt-6 inline-flex items-center gap-2 rounded-xl bg-ds-accent px-5 py-3
                  text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover
                "
              >
                <LogIn size={16} />
                Start sign-in
              </button>
            )}

            {oauthError && <p className="mt-4 text-xs text-red-400">{oauthError}</p>}

            <button
              onClick={() => {
                setOauthError('');
                setStep('connect');
              }}
              className="mt-5 text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
            >
              Back
            </button>
          </div>
        )}

        {step === 'apikey' && selectedModel && (
          <div className="mx-auto max-w-xl rounded-2xl border border-ds-border bg-ds-surface p-8">
            <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Connect</div>
            <h2 className="mt-2 text-2xl font-semibold text-ds-text">
              Add your key for {selectedModel.displayName}.
            </h2>
            <p className="mt-2 text-sm leading-6 text-ds-muted">
              The desktop app stores this locally and only uses it for requests to the selected AI
              provider.
            </p>

            {!vaultAvailable && window.electronAPI?.getSecretVaultStatus && (
              <p className="mt-4 text-xs text-red-400">
                {apiKeyError || 'Desktop secure storage is unavailable.'}
              </p>
            )}

            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={getKeyPlaceholder(selectedModel.provider)}
              className="
                mt-5 w-full rounded-xl border border-ds-border bg-ds-bg px-4 py-3
                text-sm text-ds-text placeholder:text-ds-muted/50
                focus:border-ds-accent focus:outline-none
              "
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleApiKeySubmit();
                }
              }}
              autoFocus
            />

            <div className="mt-5 flex items-center justify-between">
              <button
                onClick={() => {
                  setApiKey('');
                  setApiKeyError('');
                  setStep('connect');
                }}
                className="text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
              >
                Back
              </button>
              <button
                onClick={handleApiKeySubmit}
                disabled={!apiKey.trim() || (window.electronAPI?.getSecretVaultStatus && !vaultAvailable)}
                className="
                  rounded-xl bg-ds-accent px-5 py-3 text-sm font-medium text-white
                  transition-colors hover:bg-ds-accent-hover disabled:cursor-not-allowed disabled:opacity-40
                "
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {step === 'done' && selectedModel && selectedUseCase && (
          <div className="mx-auto max-w-3xl rounded-2xl border border-ds-border bg-ds-surface p-8 text-center">
            <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-ds-success/20">
              <Check size={24} className="text-ds-success" />
            </div>
            <div className="text-xs uppercase tracking-[0.2em] text-ds-muted">Ready</div>
            <h2 className="mt-2 text-2xl font-semibold text-ds-text">Your default setup is ready.</h2>
            <p className="mt-3 text-sm leading-6 text-ds-muted">
              The agent will start with <span className="font-medium text-ds-text">{selectedUseCase.title}</span>
              {' '}as its user-context hint and use <span className="font-medium text-ds-text">{selectedModel.displayName}</span>
              {' '}as the default AI connection.
            </p>

            <div className="mt-6 rounded-2xl border border-ds-border bg-ds-bg p-5 text-left">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                Suggested first prompt
              </div>
              <p className="mt-2 text-sm leading-6 text-ds-text">{selectedUseCase.starterPrompt}</p>
            </div>

            <div className="mt-4 rounded-2xl border border-ds-border bg-ds-bg p-5 text-left">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">Privacy</div>
              <div className="mt-2 text-base font-medium text-ds-text">
                Choose whether to share redacted diagnostics.
              </div>
              <p className="mt-2 text-sm leading-6 text-ds-muted">
                Crash reports and performance telemetry stay off until you opt in. API keys, OAuth
                tokens, and backend handshake secrets are redacted before anything is sent.
              </p>
              {!sentryConfigured && (
                <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                  Remote crash reporting is not configured for this build yet. Your preference will
                  still be saved and applied automatically once a Sentry DSN is configured.
                </div>
              )}
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {OBSERVABILITY_CHOICES.map((choice) => {
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

            {sampleApiAvailable && (
              <div className="mt-4 rounded-2xl border border-ds-accent/30 bg-ds-accent/5 p-5 text-left">
                <div className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
                  No data yet?
                </div>
                <p className="mt-2 text-sm leading-6 text-ds-text">
                  We can drop a small sample dataset into your workspace so you can see the agent
                  in action without uploading anything first.
                </p>
              </div>
            )}

            {finishError && <p className="mt-4 text-xs text-red-400">{finishError}</p>}

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
              {sampleApiAvailable && (
                <button
                  onClick={() => void handleFinish({ withSample: true })}
                  disabled={loading || observabilityChoice === null}
                  className="
                    inline-flex items-center justify-center gap-2 rounded-xl bg-ds-accent px-6 py-3
                    text-sm font-medium text-white transition-colors hover:bg-ds-accent-hover
                    disabled:opacity-50
                  "
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Preparing sample...
                    </>
                  ) : (
                    'Try with sample data'
                  )}
                </button>
              )}
              <button
                onClick={() => void handleFinish()}
                disabled={loading || observabilityChoice === null}
                className={`
                  inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3
                  text-sm font-medium transition-colors disabled:opacity-50
                  ${
                    sampleApiAvailable
                      ? 'border border-ds-border bg-ds-bg text-ds-text hover:border-ds-accent/50'
                      : 'bg-ds-accent text-white hover:bg-ds-accent-hover'
                  }
                `}
              >
                {sampleApiAvailable ? "I'll bring my own data" : 'Start DS Agent'}
              </button>
            </div>

            <button
              onClick={() => setStep('connect')}
              className="mt-4 block w-full text-xs font-medium text-ds-muted transition-colors hover:text-ds-text"
            >
              Change AI connection
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
