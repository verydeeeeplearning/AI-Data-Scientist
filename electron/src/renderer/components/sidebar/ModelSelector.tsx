/**
 * AI setup selector with simple quality presets and advanced model fallback.
 */

import { useMemo, useState } from 'react';
import { ChevronDown, Sparkles } from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import type { ModelGroup } from '../../hooks/useModels';
import { describeModelAccess } from '../../utils/modelAuth';
import {
  getQualityPresetDefinition,
  SIMPLE_QUALITY_PRESETS,
  type SimpleQualityPreset,
} from '../../utils/qualityPreset';

interface Props {
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  groups: ModelGroup[];
}

function badgeClasses(tone: 'success' | 'warning' | 'muted'): string {
  if (tone === 'success') {
    return 'bg-ds-success/15 text-ds-success';
  }
  if (tone === 'warning') {
    return 'bg-amber-500/15 text-amber-400';
  }
  return 'bg-ds-bg text-ds-muted';
}

export function ModelSelector({ onChangeModel, onChangeQualityPreset, groups }: Props) {
  const model = useAgentStore((s) => s.model);
  const qualityPreset = useAgentStore((s) => s.qualityPreset);
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const [open, setOpen] = useState(false);

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
  const currentLabel = qualityPreset === 'custom' ? customLabel : presetDefinition.label;
  const currentSummary =
    qualityPreset === 'custom'
      ? 'Direct model selection. Use presets for simpler setup.'
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
        <Sparkles size={12} />
        AI Setup
      </div>

      <button
        onClick={() => setOpen(!open)}
        className="
          w-full rounded border border-ds-border bg-ds-bg px-2 py-2 text-left
          transition-colors hover:border-ds-accent/50
        "
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-xs text-ds-text">{currentLabel}</div>
            <div className="mt-1 text-[10px] text-ds-muted">{currentSummary}</div>
            <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-ds-muted">
              <span>{currentAccess.providerLabel}</span>
              <span>|</span>
              <span
                className={`rounded-full px-1.5 py-0.5 font-medium ${badgeClasses(currentAccess.tone)}`}
              >
                {currentAccess.shortLabel}
              </span>
            </div>
          </div>
          <ChevronDown
            size={12}
            className={`mt-0.5 text-ds-muted transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {open && (
        <div
          className="
            absolute left-3 right-3 top-full z-20 mt-1 max-h-96 overflow-y-auto rounded-lg
            border border-ds-border bg-ds-surface shadow-xl
          "
        >
          <div className="border-b border-ds-border bg-ds-bg/50 px-3 py-2 text-[10px] uppercase tracking-wider text-ds-muted/70">
            Simple presets
          </div>
          <div className="space-y-2 p-2">
            {SIMPLE_QUALITY_PRESETS.map((preset) => {
              const definition = getQualityPresetDefinition(preset);
              const active = qualityPreset === preset;

              return (
                <button
                  key={preset}
                  onClick={() => handleSelectPreset(preset)}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                    active
                      ? 'border-ds-accent/60 bg-ds-accent/10'
                      : 'border-ds-border bg-ds-bg hover:border-ds-accent/40 hover:bg-ds-accent/5'
                  }`}
                >
                  <div className="text-xs font-medium text-ds-text">{definition.label}</div>
                  <div className="mt-1 text-[10px] leading-5 text-ds-muted">
                    {definition.summary}
                  </div>
                </button>
              );
            })}
          </div>

          <details className="border-t border-ds-border px-2 py-2">
            <summary className="cursor-pointer px-1 py-1 text-[10px] uppercase tracking-wider text-ds-muted/70">
              Advanced model settings
            </summary>
            <div className="mt-2">
              {groups.map((group) => (
                <div key={group.authType}>
                  <div className="sticky top-0 bg-ds-bg/50 px-2 py-1 text-[10px] uppercase tracking-wider text-ds-muted/60">
                    {group.title}
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
                        onClick={() => handleSelectModel(entry.id)}
                        className={`
                          w-full px-3 py-2 text-left transition-colors hover:bg-ds-accent/10
                          ${entry.id === model ? 'bg-ds-accent/5' : ''}
                        `}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div
                              className={`text-xs ${
                                entry.id === model ? 'text-ds-accent' : 'text-ds-text'
                              }`}
                            >
                              {entry.displayName}
                            </div>
                            <div className="mt-1 text-[10px] text-ds-muted">
                              {access.providerLabel} | {access.authTypeLabel}
                            </div>
                            <div className="mt-0.5 text-[10px] text-ds-muted/80">
                              {access.detail}
                            </div>
                          </div>
                          <span
                            className={`mt-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${badgeClasses(access.tone)}`}
                          >
                            {access.shortLabel}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ))}

              {groups.length === 0 && (
                <div className="px-3 py-2 text-xs text-ds-muted">Loading models...</div>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
