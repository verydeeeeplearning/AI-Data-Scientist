import { RotateCcw } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { Button, Select } from '../../design-system/primitives';
import { THEME_OPTIONS } from '../../design-system/themes';
import { getLocaleOption, useI18n } from '../../stores/i18nStore';
import { ApprovalGrantsPanel } from '../../components/admin/ApprovalGrantsPanel';
import {
  fetchApprovalGrants,
  revokeApprovalGrant,
} from '../../infrastructure/api/approvalGrantsApi';
import { ConnectorWizard } from '../../components/settings/ConnectorWizard';
import { CostSettings } from '../../components/settings/CostSettings';
import { LocaleSelector } from '../../components/settings/LocaleSelector';
import { PolicyStudio } from '../../components/settings/PolicyStudio';
import { PrivacySettings } from '../../components/settings/PrivacySettings';
import { SkillManager } from '../../components/settings/SkillManager';
import { SupportPanel } from '../../components/settings/SupportPanel';
import { ModelSelector } from '../../components/sidebar/ModelSelector';
import { ModeSelector } from '../../components/sidebar/ModeSelector';
import type { RpcFn } from '../../components/settings/types';
import type { AreaSelection } from '../../domain/navigation/area';
import type { ModelGroup } from '../../hooks/useModels';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';

interface Props {
  selection: AreaSelection;
  onNavigate: (path: string) => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onRestartOnboarding: () => void;
  rpc: RpcFn;
  modelGroups: ModelGroup[];
}

function CardSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
      <h2 className="text-sm font-semibold text-ds-text">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function AdminPage({
  selection,
  onNavigate,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMode,
  onRestartOnboarding,
  rpc,
  modelGroups,
}: Props) {
  const { theme, setTheme, useIaV2, setUseIaV2 } = useConfigStore();
  const { locale, setLocale, t } = useI18n();
  const currentSection = selection.adminSectionId ?? 'models';

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="border-b border-ds-border px-6 py-4">
        <h1 className="text-lg font-semibold text-ds-text">{t('area.admin.label')}</h1>
        <p className="mt-1 text-sm text-ds-muted">{t('area.admin.description')}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {(['models', 'connectors', 'policies', 'settings'] as const).map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() => onNavigate(`/admin/${candidate}`)}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                currentSection === candidate
                  ? 'border-ds-accent bg-ds-accent/10 text-ds-accent'
                  : 'border-ds-border bg-ds-surface text-ds-muted hover:text-ds-text'
              }`}
            >
              {t(`area.admin.${candidate}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {currentSection === 'models' && (
          <div className="grid gap-4 xl:grid-cols-2">
            <CardSection title={t('area.admin.models')}>
              <ModelSelector
                onChangeModel={onChangeModel}
                onChangeQualityPreset={onChangeQualityPreset}
                groups={modelGroups}
              />
            </CardSection>
            <CardSection title={t('settings.section.mode')}>
              <ModeSelector onChange={onChangeMode} />
            </CardSection>
            <CardSection title={t('settings.section.language')}>
              <LocaleSelector value={locale} onChange={setLocale} compact />
            </CardSection>
            <CardSection title={t('settings.section.onboarding')}>
              <div className="space-y-3 text-sm text-ds-muted">
                <div>{t('settings.onboarding.description')}</div>
                <Button
                  type="button"
                  onClick={onRestartOnboarding}
                  variant="secondary"
                  size="md"
                >
                  <RotateCcw size={14} />
                  {t('settings.onboarding.restart')}
                </Button>
              </div>
            </CardSection>
          </div>
        )}

        {currentSection === 'connectors' && <ConnectorWizard rpc={rpc} />}

        {currentSection === 'policies' && <PolicyStudio />}

        {currentSection === 'settings' && (
          <div className="grid gap-4 xl:grid-cols-2">
            <CardSection title={t('area.admin.iaV2.title')}>
              <div className="space-y-3 text-sm text-ds-muted">
                <div>{t('area.admin.iaV2.description')}</div>
                <button
                  type="button"
                  onClick={() => setUseIaV2(!useIaV2)}
                  className="inline-flex items-center gap-2 rounded-lg border border-ds-border px-3 py-2 text-xs text-ds-text transition-colors hover:border-ds-accent hover:text-ds-accent"
                >
                  {useIaV2 ? t('area.admin.iaV2.disable') : t('area.admin.iaV2.enable')}
                </button>
              </div>
            </CardSection>
            <CardSection title={t('settings.section.appearance')}>
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-ds-text">{t('settings.theme')}</div>
                  <div className="mt-1 text-[11px] text-ds-muted">{getLocaleOption(locale).nativeLabel}</div>
                </div>
                <Select
                  id="admin-theme-selector"
                  label={t('settings.theme')}
                  value={theme}
                  onChange={(event) => setTheme(event.target.value as typeof theme)}
                  options={THEME_OPTIONS.map((option) => ({
                    value: option.value,
                    label: t(option.labelKey),
                  }))}
                />
                <p className="text-[11px] text-ds-muted">
                  {t(THEME_OPTIONS.find((option) => option.value === theme)?.descriptionKey ?? 'settings.themeOption.dark')}
                </p>
              </div>
            </CardSection>
            <CardSection title={t('settings.section.language')}>
              <LocaleSelector value={locale} onChange={setLocale} compact />
            </CardSection>
            <CardSection title={t('settings.section.costGovernance')}>
              <CostSettings rpc={rpc} />
            </CardSection>
            <CardSection title={t('settings.section.privacy')}>
              <PrivacySettings rpc={rpc} />
            </CardSection>
            <CardSection title={t('settings.section.customSkills')}>
              <SkillManager rpc={rpc} />
            </CardSection>
            <CardSection title={t('settings.section.support')}>
              <SupportPanel />
            </CardSection>
            <CardSection title={t('approval:grant.list.title')}>
              <ApprovalGrantsPanel
                listGrants={fetchApprovalGrants}
                revokeGrant={revokeApprovalGrant}
              />
            </CardSection>
          </div>
        )}
      </div>
    </div>
  );
}
