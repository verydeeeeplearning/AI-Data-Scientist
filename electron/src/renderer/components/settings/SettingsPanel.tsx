/**
 * Settings panel with project context and model-auth compatibility hints.
 */

import { useEffect, useState } from 'react';
import { X, LogIn, LogOut, Loader2 } from 'lucide-react';
import { Button, Select } from '../../design-system/primitives';
import { THEME_OPTIONS } from '../../design-system/themes';
import { DENSITY_MODES, type DensityMode } from '../../domain/layout/density';
import { DeepLinkSettings } from './DeepLinkSettings';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useConfigStore } from '../../stores/configStore';
import { getLocaleOption, useI18n, type Locale } from '../../stores/i18nStore';
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
import { LocaleSelector } from './LocaleSelector';
import { PolicyStudio } from './PolicyStudio';
import { PrivacySettings } from './PrivacySettings';
import { SkillManager } from './SkillManager';
import { SupportPanel } from './SupportPanel';
import { TelegramNotificationSettings } from './TelegramNotificationSettings';
import type { RpcFn } from './types';

interface Props {
  onClose: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onRestartOnboarding: () => void;
  rpc: RpcFn;
}

const MODE_OPTIONS: { value: 'auto' | 'supervised' | 'step-by-step'; labelKey: string }[] = [
  { value: 'auto', labelKey: 'mode.auto' },
  { value: 'supervised', labelKey: 'mode.supervised' },
  { value: 'step-by-step', labelKey: 'mode.step' },
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
  const { theme, setTheme, density, setDensity } = useConfigStore();
  const { locale, setLocale, t } = useI18n();
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
  const localeTag = getLocaleOption(locale).bcp47;

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
        if (value === 'ko' || value === 'en' || value === 'ja') {
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

  const handleLanguageChange = async (next: Locale) => {
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
      window.alert(
        t('settings.apiKeys.saveFailed', {
          message: error instanceof Error ? error.message : String(error),
        }),
      );
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
          <h2 id="settings-title" className="text-sm font-semibold text-ds-text">
            {t('settings.title')}
          </h2>
          <button
            onClick={onClose}
            aria-label={t('settings.close')}
            className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text"
          >
            <X size={16} />
          </button>
        </div>

        <div className="space-y-6 p-4">
          <Section title={t('settings.section.operatorContext')}>
            <div className="space-y-2 rounded-lg border border-ds-border bg-ds-bg p-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ds-muted">
                  {t('settings.operatorContext.aiSetup')}
                </div>
                <div className="mt-1 text-xs font-medium text-ds-text">
                  {qualityPresetDef.label}
                </div>
                <div className="mt-1 text-[10px] text-ds-muted">{qualityPresetDef.summary}</div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-ds-muted">
                <span>{modelAccess.providerLabel}</span>
                <span>|</span>
                <span>{modelAccess.authTypeLabel}</span>
                <span className={modelAccess.ready ? 'text-ds-success' : 'text-ds-warning'}>
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
                  {t('settings.operatorContext.advancedModel')}
                </summary>
                <div className="mt-2 break-all font-mono text-[11px] text-ds-text">{model}</div>
              </details>

              {selectedProject && (
                <div className="border-t border-ds-border/50 pt-2">
                  <div className="text-[10px] uppercase tracking-wider text-ds-muted">
                    {t('settings.operatorContext.selectedProject')}
                  </div>
                  <div className="mt-1 text-xs font-medium text-ds-text">
                    {selectedProject.name}
                  </div>
                  <div className="mt-1 text-[10px] text-ds-muted">
                    {(selectedProject.taskType ?? 'general')} | {t('settings.operatorContext.artifactCount', {
                      count: selectedProject.artifactCount,
                    })}
                  </div>
                </div>
              )}
            </div>
          </Section>

          <Section title={t('settings.section.appearance')}>
            <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
              <Select
                id="theme-selector"
                label={t('settings.theme')}
                description={t('settings.themeDescription')}
                value={theme}
                onChange={(event) => setTheme(event.target.value as typeof theme)}
                options={THEME_OPTIONS.map((option) => ({
                  value: option.value,
                  label: t(option.labelKey),
                }))}
              />
              <p className="mt-2 text-[11px] text-ds-muted">
                {t(THEME_OPTIONS.find((option) => option.value === theme)?.descriptionKey ?? 'settings.themeOption.dark')}
              </p>
            </div>
            <div className="mt-3 rounded-lg border border-ds-border bg-ds-bg p-3">
              <Select
                id="density-selector"
                label={t('settings.density')}
                description={t('settings.densityDescription')}
                value={density}
                onChange={(event) => setDensity(event.target.value as DensityMode)}
                options={DENSITY_MODES.map((mode) => ({
                  value: mode,
                  label: t(`settings.densityOption.${mode}`),
                }))}
              />
              <p className="mt-2 text-[11px] text-ds-muted">
                {t(`settings.densityOption.${density}.description`)}
              </p>
            </div>
          </Section>

          <Section title={t('settings.section.deepLink')}>
            <DeepLinkSettings />
          </Section>

          <Section title={t('settings.section.telegramNotifications')}>
            <TelegramNotificationSettings rpc={rpc} />
          </Section>

          <Section title={t('settings.section.onboarding')}>
            <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
              <p className="text-xs text-ds-muted">{t('settings.onboarding.description')}</p>
              <Button
                onClick={() => {
                  onClose();
                  onRestartOnboarding();
                }}
                variant="secondary"
                size="md"
                className="mt-3"
              >
                {t('settings.onboarding.restart')}
              </Button>
            </div>
          </Section>

          <Section title={t('settings.section.aiSetup')}>
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
                {t('settings.aiSetup.advancedModel')}
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
                    {t('settings.aiSetup.apply')}
                  </button>
                </div>
                <p className="mt-1 text-[10px] text-ds-muted">
                  {t('settings.aiSetup.examples')}
                </p>
              </div>
            </details>
          </Section>

          <Section title={t('settings.section.mode')}>
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
                  {t(option.labelKey)}
                </button>
              ))}
            </div>
          </Section>

          <Section title={t('settings.section.policyStudio')}>
            <PolicyStudio />
          </Section>

          <Section title={t('settings.section.providerStatus')}>
            <div className="space-y-2">
              {Array.from(new Set([
                ...Object.keys(providerStatuses),
                ...Object.keys(providerHealth),
              ]))
                .sort((left, right) =>
                  (PROVIDER_LABELS[left] ?? left).localeCompare(PROVIDER_LABELS[right] ?? right, localeTag)
                )
                .map((provider) => {
                  const status = providerStatuses[provider] ?? 'unknown';
                  const oauth = oauthStatuses[provider];
                  const maskedKey = maskedKeys[provider];
                  const health = providerHealth[provider];
                  const detail = oauth?.authenticated
                    ? oauth.email ?? oauth.accountId ?? t('settings.oauth.connected')
                    : maskedKey ?? statusDetail(status, t);

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
                <p className="text-xs text-ds-muted">{t('settings.providerStatus.loading')}</p>
              )}

              {authLastUpdatedAt && (
                <p className="text-[10px] text-ds-muted/70">
                  {t('settings.providerStatus.lastSynced', {
                    time: new Date(authLastUpdatedAt).toLocaleTimeString(localeTag),
                  })}
                </p>
              )}
            </div>
          </Section>

          <Section title={t('settings.section.oauthAccounts')}>
            <div className="space-y-2">
              {[
                {
                  id: 'codex',
                  label: t('settings.oauth.codex.label'),
                  desc: t('settings.oauth.codex.description'),
                },
                {
                  id: 'gemini',
                  label: t('settings.oauth.gemini.label'),
                  desc: t('settings.oauth.gemini.description'),
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
                            {oauth?.email ?? oauth?.accountId ?? t('settings.oauth.connected')}
                          </span>
                          <button
                            onClick={() => void handleOAuthDisconnect(id)}
                            className="p-1 text-ds-muted transition-colors hover:text-red-400"
                            title={t('settings.oauth.disconnect')}
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
                          {t('settings.oauth.login')}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Section>

          <Section title={t('settings.section.apiKeys')}>
            <div className="space-y-2">
              {window.electronAPI?.getSecretVaultStatus && (
                <div className="rounded-lg border border-ds-border/50 bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
                  {vaultStatus?.available
                    ? t('settings.apiKeys.vault.ready')
                    : vaultStatus?.error ?? t('settings.apiKeys.vault.checking')}
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
                        {maskedKeys[provider] ? t('settings.apiKeys.change') : t('settings.apiKeys.set')}
                      </button>
                    ) : (
                      <button
                        onClick={() => setEditingProvider(null)}
                        className="text-[10px] text-ds-muted hover:text-ds-text"
                      >
                        {t('settings.apiKeys.cancel')}
                      </button>
                    )}
                  </div>

                  {editingProvider === provider ? (
                    <div className="mt-1 flex gap-1.5">
                      <input
                        type="password"
                        value={newKey}
                        onChange={(e) => setNewKey(e.target.value)}
                        placeholder={t('settings.apiKeys.placeholder')}
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
                        {t('common.save')}
                      </button>
                    </div>
                  ) : (
                    <div className="font-mono text-[10px] text-ds-muted">
                      {maskedKeys[provider] ?? t('settings.apiKeys.notSet')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>

          <Section title={t('settings.section.databaseConnectors')}>
            <ConnectorWizard rpc={rpc} />
          </Section>

          <Section title={t('settings.section.costGovernance')}>
            <CostSettings rpc={rpc} />
          </Section>

          <Section title={t('settings.section.teamEnterprise')}>
            <AdminConsole rpc={rpc} />
          </Section>

          <Section title={t('settings.section.customSkills')}>
            <SkillManager rpc={rpc} />
          </Section>

          <Section title={t('settings.section.privacy')}>
            <PrivacySettings rpc={rpc} />
          </Section>

          <Section title={t('settings.section.support')}>
            <SupportPanel />
          </Section>

          <Section title={t('settings.section.shortcuts')}>
            <div className="space-y-1.5">
              <ShortcutRow keys="Enter" desc={t('settings.send')} />
              <ShortcutRow keys="Shift+Enter" desc={t('settings.newline')} />
              <ShortcutRow keys="Ctrl+C" desc={t('settings.abort')} />
              <ShortcutRow keys="Ctrl+M" desc={t('settings.cycleMode')} />
              <ShortcutRow keys="Ctrl+," desc={t('settings.openSettings')} />
            </div>
          </Section>

          <Section title={t('settings.section.language')}>
            <LocaleSelector value={locale} onChange={handleLanguageChange} compact />
          </Section>

          <div className="pt-4 text-center text-[10px] text-ds-muted/40">
            {t('settings.version')}
          </div>
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

function statusDetail(
  status: string,
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): string {
  if (status === 'active') return t('settings.status.credentialsAvailable');
  if (status === 'local') return t('settings.status.localRuntime');
  if (status === 'need_key') return t('settings.status.apiKeyRequired');
  if (status === 'not_configured') return t('settings.status.oauthRequired');
  return t('settings.status.unknown');
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();

  if (status === 'active' || status === 'local') {
    return (
      <span className="flex items-center gap-1 text-[10px] text-ds-success">
        <span className="h-1.5 w-1.5 rounded-full bg-ds-success" />
        {status === 'local' ? t('settings.status.local') : t('settings.status.ready')}
      </span>
    );
  }
  if (status === 'need_key' || status === 'not_configured') {
    return (
      <span className="flex items-center gap-1 text-[10px] text-ds-warning">
        <span className="h-1.5 w-1.5 rounded-full bg-ds-warning" />
        {status === 'need_key' ? t('settings.status.needKey') : t('settings.status.needLogin')}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[10px] text-ds-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-ds-muted/40" />
      {t('settings.status.unknown')}
    </span>
  );
}

function HealthBadge({ health }: { health: ProviderHealthStatus }) {
  const { t } = useI18n();

  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${healthBadgeClasses(health.status)}`}
      title={health.message}
    >
      {healthLabel(health.status, t)}
    </span>
  );
}

function healthBadgeClasses(status: ProviderHealthStatus['status']): string {
  if (status === 'ok') {
    return 'bg-ds-success/15 text-ds-success';
  }
  if (status === 'degraded') {
    return 'bg-ds-warning/15 text-ds-warning';
  }
  return 'bg-ds-error/15 text-ds-error';
}

function healthLabel(
  status: ProviderHealthStatus['status'],
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): string {
  if (status === 'ok') {
    return t('settings.health.ok');
  }
  if (status === 'degraded') {
    return t('settings.health.degraded');
  }
  return t('settings.health.error');
}
