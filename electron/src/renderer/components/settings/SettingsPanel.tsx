/**
 * Settings panel with project context and model-auth compatibility hints.
 */

import { useEffect, useState } from 'react';
import { X, Sun, Moon, Globe, LogIn, LogOut, Loader2 } from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useConfigStore } from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';
import { useProjectStore } from '../../stores/projectStore';
import { fetchAuthSnapshot } from '../../hooks/useProviderAuth';
import { PROVIDER_LABELS, describeModelAccess } from '../../utils/modelAuth';
import type { ProviderHealthStatus } from '../../stores/authStore';
import {
  getQualityPresetDefinition,
  SIMPLE_QUALITY_PRESETS,
  type SimpleQualityPreset,
} from '../../utils/qualityPreset';
import { AdminConsole } from './AdminConsole';
import { ConnectorWizard } from './ConnectorWizard';
import { CostSettings } from './CostSettings';
import { PolicyStudio } from './PolicyStudio';
import { PrivacySettings } from './PrivacySettings';
import { SkillManager } from './SkillManager';
import { SupportPanel } from './SupportPanel';
import type { RpcFn } from './types';

interface Props {
  onClose: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onRestartOnboarding: () => void;
  rpc: RpcFn;
}

const MODE_OPTIONS: { value: 'auto' | 'supervised' | 'step-by-step'; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'supervised', label: 'Supervised' },
  { value: 'step-by-step', label: 'Step-by-Step' },
];

const API_KEY_PROVIDERS = [
  'anthropic',
  'openai',
  'gemini',
  'deepseek',
  'minimax',
  'qwen',
  'zhipu',
  'moonshot',
  'groq',
];

export function SettingsPanel({
  onClose,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMode,
  onRestartOnboarding,
  rpc,
}: Props) {
  const model = useAgentStore((s) => s.model);
  const qualityPreset = useAgentStore((s) => s.qualityPreset);
  const mode = useAgentStore((s) => s.mode);
  const { theme, toggleTheme } = useConfigStore();
  const { locale, setLocale } = useI18n();
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const providerHealth = useAuthStore((s) => s.providerHealth);
  const maskedKeys = useAuthStore((s) => s.maskedKeys);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const authLoading = useAuthStore((s) => s.loading);
  const authLastUpdatedAt = useAuthStore((s) => s.lastUpdatedAt);
  const setAuthSnapshot = useAuthStore((s) => s.setSnapshot);
  const projects = useProjectStore((s) => s.projects);
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [advancedModelDraft, setAdvancedModelDraft] = useState(model);
  const [newKey, setNewKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);
  const [vaultStatus, setVaultStatus] = useState<{
    available: boolean;
    persistent: boolean;
    backend: 'safeStorage' | 'unavailable';
    error?: string;
  } | null>(null);

  const selectedProject =
    projects.find((project) => project.projectId === selectedProjectId) ?? null;
  const qualityPresetDef = getQualityPresetDefinition(qualityPreset);
  const modelAccess = describeModelAccess({
    modelId: model,
    providerStatuses,
    oauthStatuses,
  });
  const currentProviderHealth = providerHealth[modelAccess.provider] ?? null;

  const refreshAuth = async () => {
    setAuthSnapshot(await fetchAuthSnapshot(rpc));
  };

  useEffect(() => {
    if (!window.electronAPI?.getSecretVaultStatus) {
      return;
    }

    void window.electronAPI
      .getSecretVaultStatus()
      .then((result) => setVaultStatus(result))
      .catch((error) => {
        console.warn('[SettingsPanel] vault status lookup failed:', error);
      });
  }, []);

  useEffect(() => {
    setAdvancedModelDraft(model);
  }, [model]);

  // P1-13: Reconcile UI locale with the backend agent.language on mount so
  // the LLM system prompt language directive stays in sync across sessions.
  useEffect(() => {
    let cancelled = false;
    void rpc('config.get')
      .then((result) => {
        if (cancelled) return;
        const config = (result as { config?: Record<string, unknown> }).config ?? {};
        const agentCfg = (config.agent ?? {}) as Record<string, unknown>;
        const value = agentCfg.language;
        if (value === 'ko' || value === 'en') {
          if (value !== locale) setLocale(value);
        }
      })
      .catch((error) => {
        console.warn('[SettingsPanel] agent.language lookup failed:', error);
      });
    return () => {
      cancelled = true;
    };
    // Intentionally run once on mount — subsequent user changes are pushed
    // via handleLanguageChange.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLanguageChange = async (next: 'ko' | 'en') => {
    setLocale(next);
    try {
      await rpc('config.set', { path: 'agent.language', value: next });
    } catch (error) {
      console.warn('[SettingsPanel] failed to sync agent.language:', error);
    }
  };

  const handleOAuthLogin = async (provider: string) => {
    setOauthLoading(provider);
    try {
      await rpc('oauth.startLogin', { provider });
      for (let i = 0; i < 300; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const data = await rpc('oauth.status');
        const statuses = (data.providers as Record<string, { authenticated: boolean }>) ?? {};
        if (statuses[provider]?.authenticated) {
          break;
        }
      }
      await refreshAuth();
    } catch (error) {
      console.error('OAuth login failed:', error);
    } finally {
      setOauthLoading(null);
    }
  };

  const handleOAuthDisconnect = async (provider: string) => {
    try {
      await rpc('oauth.disconnect', { provider });
      await refreshAuth();
    } catch (error) {
      console.error('OAuth disconnect failed:', error);
    }
  };

  const handleSaveKey = async (provider: string) => {
    if (!newKey.trim()) return;
    setSaving(true);
    try {
      if (window.electronAPI?.setApiKey) {
        const result = await window.electronAPI.setApiKey(provider, newKey.trim());
        if (!result.ok) {
          throw new Error(result.error ?? 'Failed to save API key.');
        }
      } else {
        await rpc('config.setApiKey', { provider, key: newKey.trim() });
      }
      setEditingProvider(null);
      setNewKey('');
      window.setTimeout(() => {
        void refreshAuth().catch((error) => {
          console.warn('[SettingsPanel] auth refresh after key save failed:', error);
        });
      }, 800);
    } catch (error) {
      console.error('Failed to save key:', error);
      window.alert(`Failed to save key: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setSaving(false);
    }
  };

  const applyAdvancedModel = () => {
    const nextModel = advancedModelDraft.trim();
    if (!nextModel || nextModel === model) {
      return;
    }
    void onChangeModel(nextModel);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
      className="fixed inset-0 z-40 flex justify-end"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />

      <div
        className="relative h-full w-full max-w-2xl overflow-y-auto border-l border-ds-border bg-ds-surface"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-ds-border px-4 py-3">
          <h2 id="settings-title" className="text-sm font-semibold text-ds-text">Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text"
          >
            <X size={16} />
          </button>
        </div>

        <div className="space-y-6 p-4">
          <Section title="Operator Context">
            <div className="space-y-2 rounded-lg border border-ds-border bg-ds-bg p-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ds-muted">AI Setup</div>
                <div className="mt-1 text-xs font-medium text-ds-text">
                  {qualityPresetDef.label}
                </div>
                <div className="mt-1 text-[10px] text-ds-muted">{qualityPresetDef.summary}</div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-ds-muted">
                <span>{modelAccess.providerLabel}</span>
                <span>|</span>
                <span>{modelAccess.authTypeLabel}</span>
                <span className={modelAccess.ready ? 'text-ds-success' : 'text-amber-400'}>
                  {modelAccess.shortLabel}
                </span>
                {currentProviderHealth && <HealthBadge health={currentProviderHealth} />}
              </div>
              <p className="text-[11px] text-ds-muted/90">{modelAccess.detail}</p>
              {currentProviderHealth && (
                <p className="text-[11px] text-ds-muted/90">
                  {currentProviderHealth.message}
                  {typeof currentProviderHealth.latencyMs === 'number'
                    ? ` (${currentProviderHealth.latencyMs}ms)`
                    : ''}
                </p>
              )}
              <details className="rounded border border-ds-border/50 bg-ds-surface px-2 py-1.5">
                <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-ds-muted">
                  Advanced model
                </summary>
                <div className="mt-2 break-all font-mono text-[11px] text-ds-text">{model}</div>
              </details>

              {selectedProject && (
                <div className="border-t border-ds-border/50 pt-2">
                  <div className="text-[10px] uppercase tracking-wider text-ds-muted">
                    Selected Project
                  </div>
                  <div className="mt-1 text-xs font-medium text-ds-text">
                    {selectedProject.name}
                  </div>
                  <div className="mt-1 text-[10px] text-ds-muted">
                    {(selectedProject.taskType ?? 'general')} | {selectedProject.artifactCount}{' '}
                    artifacts
                  </div>
                </div>
              )}
            </div>
          </Section>

          <Section title="Appearance">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ds-text">Theme</span>
              <button
                onClick={toggleTheme}
                className="
                  flex items-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-1.5
                  text-xs text-ds-text transition-colors hover:border-ds-accent/50
                "
              >
                {theme === 'dark' ? <Moon size={12} /> : <Sun size={12} />}
                {theme === 'dark' ? 'Dark' : 'Light'}
              </button>
            </div>
          </Section>

          <Section title="Onboarding">
            <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
              <p className="text-xs text-ds-muted">
                Re-run the first-run guide to update your default use case and AI setup.
              </p>
              <button
                onClick={() => {
                  onClose();
                  onRestartOnboarding();
                }}
                className="
                  mt-3 rounded-lg border border-ds-border px-3 py-1.5 text-xs font-medium
                  text-ds-text transition-colors hover:border-ds-accent/50 hover:text-ds-accent
                "
              >
                Restart Onboarding
              </button>
            </div>
          </Section>

          <Section title="AI Setup">
            <div className="grid gap-2 sm:grid-cols-2">
              {SIMPLE_QUALITY_PRESETS.map((preset) => {
                const definition = getQualityPresetDefinition(preset);
                const active = qualityPreset === preset;

                return (
                  <button
                    key={preset}
                    onClick={() => void onChangeQualityPreset(preset)}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      active
                        ? 'border-ds-accent/60 bg-ds-accent/10'
                        : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                    }`}
                  >
                    <div className="text-xs font-medium text-ds-text">{definition.label}</div>
                    <div className="mt-1 text-[11px] leading-5 text-ds-muted">
                      {definition.summary}
                    </div>
                  </button>
                );
              })}
            </div>

            <details className="mt-3 rounded-lg border border-ds-border bg-ds-bg p-3">
              <summary className="cursor-pointer text-xs font-medium text-ds-text">
                Advanced model settings
              </summary>
              <div className="mt-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={advancedModelDraft}
                    onChange={(e) => setAdvancedModelDraft(e.target.value)}
                    className="
                      flex-1 rounded border border-ds-border bg-ds-surface px-3 py-1.5
                      text-xs font-mono text-ds-text
                      focus:border-ds-accent focus:outline-none
                    "
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        applyAdvancedModel();
                      }
                    }}
                  />
                  <button
                    onClick={applyAdvancedModel}
                    disabled={!advancedModelDraft.trim() || advancedModelDraft.trim() === model}
                    className="
                      rounded border border-ds-border px-3 py-1.5 text-xs font-medium
                      text-ds-text transition-colors hover:border-ds-accent/50 hover:text-ds-accent
                      disabled:cursor-not-allowed disabled:opacity-40
                    "
                  >
                    Apply
                  </button>
                </div>
                <p className="mt-1 text-[10px] text-ds-muted">
                  e.g. anthropic/claude-sonnet-4-6, codex/gpt-5.4, deepseek/deepseek-chat
                </p>
              </div>
            </details>
          </Section>

          <Section title="Mode">
            <div className="flex gap-1">
              {MODE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => onChangeMode(option.value)}
                  className={`
                    flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors
                    ${
                      mode === option.value
                        ? 'bg-ds-accent text-white'
                        : 'border border-ds-border bg-ds-bg text-ds-muted hover:text-ds-text'
                    }
                  `}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Policy Studio">
            <PolicyStudio />
          </Section>

          <Section title="Provider Status">
            <div className="space-y-2">
              {Array.from(new Set([
                ...Object.keys(providerStatuses),
                ...Object.keys(providerHealth),
              ]))
                .sort((left, right) =>
                  (PROVIDER_LABELS[left] ?? left).localeCompare(PROVIDER_LABELS[right] ?? right)
                )
                .map((provider) => {
                  const status = providerStatuses[provider] ?? 'unknown';
                  const oauth = oauthStatuses[provider];
                  const maskedKey = maskedKeys[provider];
                  const health = providerHealth[provider];
                  const detail = oauth?.authenticated
                    ? oauth.email ?? oauth.accountId ?? 'OAuth connected'
                    : maskedKey ?? statusDetail(status);

                  return (
                    <div
                      key={provider}
                      className="rounded-lg border border-ds-border/50 bg-ds-bg p-2.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <div className="text-xs font-medium text-ds-text">
                              {PROVIDER_LABELS[provider] ?? provider}
                            </div>
                            {health && <HealthBadge health={health} />}
                          </div>
                          <div className="text-[10px] text-ds-muted">{detail}</div>
                          {health && (
                            <div className="text-[10px] text-ds-muted/80">
                              {health.message}
                              {typeof health.latencyMs === 'number' ? ` (${health.latencyMs}ms)` : ''}
                            </div>
                          )}
                        </div>
                        <StatusBadge status={status} />
                      </div>
                    </div>
                  );
                })}

              {(authLoading || Object.keys(providerStatuses).length === 0) && (
                <p className="text-xs text-ds-muted">Loading auth snapshot...</p>
              )}

              {authLastUpdatedAt && (
                <p className="text-[10px] text-ds-muted/70">
                  Last synced {new Date(authLastUpdatedAt).toLocaleTimeString()}
                </p>
              )}
            </div>
          </Section>

          <Section title="OAuth Accounts">
            <div className="space-y-2">
              {[
                {
                  id: 'codex',
                  label: 'ChatGPT (Codex)',
                  desc: 'OpenAI ChatGPT Plus/Pro account',
                },
                {
                  id: 'gemini',
                  label: 'Google Gemini',
                  desc: 'Google account or Gemini-compatible flow',
                },
              ].map(({ id, label, desc }) => {
                const oauth = oauthStatuses[id];
                const isAuth = oauth?.authenticated;
                const isLoading = oauthLoading === id;

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-ds-border/50 bg-ds-bg p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <span className="text-xs font-medium text-ds-text">{label}</span>
                        <p className="text-[10px] text-ds-muted">{desc}</p>
                      </div>
                      {isAuth ? (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-green-400">
                            {oauth?.email ?? oauth?.accountId ?? 'Connected'}
                          </span>
                          <button
                            onClick={() => void handleOAuthDisconnect(id)}
                            className="p-1 text-ds-muted transition-colors hover:text-red-400"
                            title="Disconnect"
                          >
                            <LogOut size={12} />
                          </button>
                        </div>
                      ) : isLoading ? (
                        <Loader2 size={14} className="animate-spin text-ds-accent" />
                      ) : (
                        <button
                          onClick={() => void handleOAuthLogin(id)}
                          className="
                            flex items-center gap-1 rounded bg-ds-accent px-2.5 py-1
                            text-[10px] font-medium text-white transition-colors hover:bg-ds-accent-hover
                          "
                        >
                          <LogIn size={10} />
                          Login
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Section>

          <Section title="API Keys">
            <div className="space-y-2">
              {window.electronAPI?.getSecretVaultStatus && (
                <div className="rounded-lg border border-ds-border/50 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
                  {vaultStatus?.available
                    ? 'Stored securely by the desktop app and applied by restarting the local AI engine.'
                    : vaultStatus?.error ?? 'Checking desktop secure storage...'}
                </div>
              )}
              {API_KEY_PROVIDERS.map((provider) => (
                <div
                  key={provider}
                  className="rounded-lg border border-ds-border/50 bg-ds-bg p-2.5"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-medium text-ds-text">
                      {PROVIDER_LABELS[provider] ?? provider}
                    </span>
                    {editingProvider !== provider ? (
                      <button
                        onClick={() => {
                          setEditingProvider(provider);
                          setNewKey('');
                        }}
                        className="text-[10px] text-ds-accent hover:underline"
                      >
                        {maskedKeys[provider] ? 'Change' : 'Set Key'}
                      </button>
                    ) : (
                      <button
                        onClick={() => setEditingProvider(null)}
                        className="text-[10px] text-ds-muted hover:text-ds-text"
                      >
                        Cancel
                      </button>
                    )}
                  </div>

                  {editingProvider === provider ? (
                    <div className="mt-1 flex gap-1.5">
                      <input
                        type="password"
                        value={newKey}
                        onChange={(e) => setNewKey(e.target.value)}
                        placeholder="Enter API key..."
                        className="
                          flex-1 rounded border border-ds-border bg-ds-surface px-2 py-1
                          text-xs font-mono text-ds-text
                          focus:border-ds-accent focus:outline-none
                        "
                        onKeyDown={(e) => e.key === 'Enter' && void handleSaveKey(provider)}
                        autoFocus
                      />
                      <button
                        onClick={() => void handleSaveKey(provider)}
                        disabled={!newKey.trim() || saving}
                        className="
                          rounded bg-ds-accent px-2.5 py-1 text-xs font-medium text-white
                          transition-colors disabled:opacity-30
                        "
                      >
                        Save
                      </button>
                    </div>
                  ) : (
                    <div className="font-mono text-[10px] text-ds-muted">
                      {maskedKeys[provider] ?? 'Not set'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Database Connectors">
            <ConnectorWizard rpc={rpc} />
          </Section>

          <Section title="Cost Governance">
            <CostSettings rpc={rpc} />
          </Section>

          <Section title="Team & Enterprise">
            <AdminConsole rpc={rpc} />
          </Section>

          <Section title="Custom Skills">
            <SkillManager rpc={rpc} />
          </Section>

          <Section title="Privacy">
            <PrivacySettings rpc={rpc} />
          </Section>

          <Section title="Support">
            <SupportPanel />
          </Section>

          <Section title="Keyboard Shortcuts">
            <div className="space-y-1.5">
              <ShortcutRow keys="Enter" desc="Send message" />
              <ShortcutRow keys="Shift+Enter" desc="New line" />
              <ShortcutRow keys="Ctrl+C" desc="Abort current run" />
              <ShortcutRow keys="Ctrl+M" desc="Cycle mode" />
              <ShortcutRow keys="Ctrl+," desc="Open settings" />
            </div>
          </Section>

          <Section title="Language">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-ds-text">
                <Globe size={12} className="text-ds-muted" />
                Language
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => void handleLanguageChange('en')}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    locale === 'en'
                      ? 'bg-ds-accent text-white'
                      : 'border border-ds-border bg-ds-bg text-ds-muted hover:text-ds-text'
                  }`}
                >
                  EN
                </button>
                <button
                  onClick={() => void handleLanguageChange('ko')}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    locale === 'ko'
                      ? 'bg-ds-accent text-white'
                      : 'border border-ds-border bg-ds-bg text-ds-muted hover:text-ds-text'
                  }`}
                >
                  KO
                </button>
              </div>
            </div>
          </Section>

          <div className="pt-4 text-center text-[10px] text-ds-muted/40">DS Agent v0.1.0</div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-ds-muted">
        {title}
      </h3>
      {children}
    </div>
  );
}

function ShortcutRow({ keys, desc }: { keys: string; desc: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-ds-muted">{desc}</span>
      <kbd className="rounded border border-ds-border bg-ds-bg px-1.5 py-0.5 text-[10px] font-mono text-ds-text">
        {keys}
      </kbd>
    </div>
  );
}

function statusDetail(status: string): string {
  if (status === 'active') return 'Credentials available';
  if (status === 'local') return 'Local runtime';
  if (status === 'need_key') return 'API key required';
  if (status === 'not_configured') return 'OAuth login required';
  return 'Not configured';
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'active' || status === 'local') {
    return (
      <span className="flex items-center gap-1 text-[10px] text-ds-success">
        <span className="h-1.5 w-1.5 rounded-full bg-ds-success" />
        {status === 'local' ? 'Local' : 'Ready'}
      </span>
    );
  }
  if (status === 'need_key' || status === 'not_configured') {
    return (
      <span className="flex items-center gap-1 text-[10px] text-amber-400">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        {status === 'need_key' ? 'Need Key' : 'Need Login'}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[10px] text-ds-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-ds-muted/40" />
      Unknown
    </span>
  );
}

function HealthBadge({ health }: { health: ProviderHealthStatus }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${healthBadgeClasses(health.status)}`}
      title={health.message}
    >
      {healthLabel(health.status)}
    </span>
  );
}

function healthBadgeClasses(status: ProviderHealthStatus['status']): string {
  if (status === 'ok') {
    return 'bg-ds-success/15 text-ds-success';
  }
  if (status === 'degraded') {
    return 'bg-amber-400/15 text-amber-300';
  }
  return 'bg-ds-error/15 text-ds-error';
}

function healthLabel(status: ProviderHealthStatus['status']): string {
  if (status === 'ok') {
    return 'Healthy';
  }
  if (status === 'degraded') {
    return 'Degraded';
  }
  return 'Unavailable';
}
