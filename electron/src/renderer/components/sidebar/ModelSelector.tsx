import { useId, useMemo, useState } from 'react';
import { ChevronDown, Sparkles } from 'lucide-react';

import { recommendModel } from '../../application/llm/recommendModel';
import { Badge, Button, Card } from '../../design-system/primitives';
import { getCapabilityGroupDefinition } from '../../domain/llm/modelCapability';
import type { ModelGroup } from '../../hooks/useModels';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useI18n } from '../../stores/i18nStore';
import { describeModelAccess } from '../../utils/modelAuth';
import {
  getQualityPresetDefinition,
  SIMPLE_QUALITY_PRESETS,
  type SimpleQualityPreset,
} from '../../utils/qualityPreset';
import { CapabilityBadge } from '../settings/CapabilityBadge';

interface Props {
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  groups: ModelGroup[];
}

function statusBadgeTone(
  tone: 'success' | 'warning' | 'muted',
): 'success' | 'warning' | 'neutral' {
  if (tone === 'success') {
    return 'success';
  }
  if (tone === 'warning') {
    return 'warning';
  }
  return 'neutral';
}

export function ModelSelector({ onChangeModel, onChangeQualityPreset, groups }: Props) {
  const model = useAgentStore((s) => s.model);
  const qualityPreset = useAgentStore((s) => s.qualityPreset);
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const generatedId = useId().replace(/:/g, '');
  const panelId = `sidebar-model-selector-panel-${generatedId}`;

  const allModels = useMemo(() => groups.flatMap((group) => group.models), [groups]);
  const currentModel = allModels.find((entry) => entry.id === model) ?? null;
  const currentAccess = describeModelAccess({
    modelId: model,
    modelEntry: currentModel,
    providerStatuses,
    oauthStatuses,
  });
  const presetDefinition = getQualityPresetDefinition(qualityPreset);
  const customLabel =
    currentModel?.displayName ?? (model.includes('/') ? model.split('/')[1] : model);
  const currentGroupDefinition = currentModel
    ? getCapabilityGroupDefinition(currentModel.capabilityGroup)
    : null;

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

  const recommendation = useMemo(
    () =>
      recommendModel(allModels, {
        locale,
        qualityPreset,
        readyModelIds,
      }),
    [allModels, locale, qualityPreset, readyModelIds],
  );

  const recommendationReason =
    recommendation?.reasons.map((reason) => t(`llm.recommend.reason.${reason}`)).join(' · ') ?? '';
  const currentLabel = qualityPreset === 'custom' ? customLabel : presetDefinition.label;
  const currentSummary =
    qualityPreset === 'custom'
      ? currentGroupDefinition
        ? t(currentGroupDefinition.descriptionKey)
        : t('llm.current.customDescription')
      : presetDefinition.summary;

  const handleSelectModel = (modelId: string) => {
    onChangeModel(modelId);
    setOpen(false);
  };

  const handleSelectPreset = (preset: SimpleQualityPreset) => {
    onChangeQualityPreset(preset);
    setOpen(false);
  };

  return (
    <div className="relative px-3 py-1.5">
      <div className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
        <Sparkles size={12} aria-hidden="true" />
        {t('sidebar.model')}
      </div>

      <Button
        variant="secondary"
        size="md"
        aria-controls={panelId}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="w-full justify-between !rounded-ds-xl px-ds-3 py-ds-3 text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-xs text-ds-text">{currentLabel}</div>
            <div className="mt-1 text-[10px] text-ds-muted">{currentSummary}</div>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-ds-muted">
              {currentGroupDefinition ? <span>{t(currentGroupDefinition.titleKey)}</span> : null}
              <Badge compact tone={statusBadgeTone(currentAccess.tone)}>
                {currentAccess.shortLabel}
              </Badge>
            </div>
            {currentModel ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {currentModel.badges.slice(0, 3).map((badge) => (
                  <CapabilityBadge key={`${currentModel.id}-${badge}`} badge={badge} />
                ))}
              </div>
            ) : null}
          </div>
          <ChevronDown
            size={12}
            aria-hidden="true"
            className={`mt-0.5 text-ds-muted transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </Button>

      {open ? (
        <Card
          id={panelId}
          role="dialog"
          aria-modal="false"
          aria-label={t('sidebar.model')}
          className="absolute left-3 right-3 top-full z-20 mt-1 max-h-96 overflow-y-auto border-ds-border bg-ds-surface p-0 shadow-xl"
        >
          <div className="border-b border-ds-border bg-ds-bg/50 px-3 py-2 text-[10px] uppercase tracking-wider text-ds-muted/70">
            {t('llm.section.simplePresets')}
          </div>
          <div className="space-y-2 p-2">
            {SIMPLE_QUALITY_PRESETS.map((preset) => {
              const definition = getQualityPresetDefinition(preset);
              const active = qualityPreset === preset;

              return (
                <Button
                  key={preset}
                  variant={active ? 'primary' : 'secondary'}
                  size="md"
                  className="w-full justify-start rounded-ds-lg px-ds-3 py-ds-3 text-left"
                  onClick={() => handleSelectPreset(preset)}
                >
                  <div className="min-w-0">
                    <div className="text-xs font-medium">{definition.label}</div>
                    <div className="mt-1 text-[10px] leading-5 text-ds-muted">
                      {definition.summary}
                    </div>
                  </div>
                </Button>
              );
            })}
          </div>

          <div className="border-t border-ds-border bg-ds-bg/50 px-3 py-2 text-[10px] uppercase tracking-wider text-ds-muted/70">
            {t('llm.section.capabilityGroups')}
          </div>
          <div className="space-y-3 p-2">
            {groups.map((group) => (
              <Card
                key={group.id}
                role="group"
                aria-label={t(group.titleKey)}
                className="overflow-hidden border-ds-border bg-ds-bg p-0 shadow-none"
              >
                <div className="border-b border-ds-border/60 px-3 py-2">
                  <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-ds-muted">
                    {t(group.titleKey)}
                  </div>
                  <div className="mt-1 text-[10px] leading-5 text-ds-muted/90">
                    {t(group.descriptionKey)}
                  </div>
                </div>

                {group.models.length === 0 ? (
                  <div className="px-3 py-3 text-[11px] text-ds-muted">
                    <div className="font-medium text-ds-text">{t(group.emptyTitleKey)}</div>
                    <div className="mt-1">{t(group.emptyDescriptionKey)}</div>
                  </div>
                ) : (
                  group.models.map((entry) => {
                    const access = describeModelAccess({
                      modelId: entry.id,
                      modelEntry: entry,
                      providerStatuses,
                      oauthStatuses,
                    });
                    const isRecommended = recommendation?.model.id === entry.id;

                    return (
                      <button
                        key={entry.id}
                        type="button"
                        aria-pressed={entry.id === model}
                        className={`
                          w-full border-t border-ds-border/40 px-3 py-3 text-left transition-colors
                          first:border-t-0 hover:bg-ds-accent/10
                          ${entry.id === model ? 'bg-ds-accent/5' : ''}
                        `}
                        onClick={() => handleSelectModel(entry.id)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <div
                                className={`text-xs font-medium ${
                                  entry.id === model ? 'text-ds-accent' : 'text-ds-text'
                                }`}
                              >
                                {entry.displayName}
                              </div>
                              {isRecommended ? (
                                <Badge compact tone="accent">
                                  {t('llm.recommend.badge')}
                                </Badge>
                              ) : null}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {entry.badges.map((badge) => (
                                <CapabilityBadge key={`${entry.id}-${badge}`} badge={badge} />
                              ))}
                            </div>
                            {isRecommended && recommendationReason ? (
                              <div className="mt-1.5 text-[10px] text-ds-accent">
                                {recommendationReason}
                              </div>
                            ) : null}
                            <div className="mt-1.5 text-[10px] text-ds-muted">
                              {access.providerLabel} · {access.authTypeLabel}
                            </div>
                            <div className="mt-0.5 text-[10px] text-ds-muted/80">
                              {access.detail}
                            </div>
                          </div>
                          <Badge compact tone={statusBadgeTone(access.tone)} className="mt-0.5">
                            {access.shortLabel}
                          </Badge>
                        </div>
                      </button>
                    );
                  })
                )}
              </Card>
            ))}

            {allModels.length === 0 ? (
              <div className="px-3 py-2 text-xs text-ds-muted">{t('onboarding.connect.loading')}</div>
            ) : null}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
