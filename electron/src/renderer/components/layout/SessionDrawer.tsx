/**
 * SessionDrawer — session-scope settings drawer (⌘;).
 *
 * Holds anything that applies *only to the current session* and takes
 * effect immediately:
 *   - Mode (auto / supervised / step-by-step)
 *   - Quality preset
 *   - Budget cap (session)
 *   - Current model
 *
 * Workspace-scope concerns (Models catalog, Connectors, Policies, Memory,
 * Secrets) live in Admin and are NOT duplicated here. Drawer surfaces a
 * "More settings…" link that navigates to /admin/settings.
 */

import { ChevronRight, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAgentStore } from '../../stores/agentStore';
import { useConfigStore } from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';
import type { ModelGroup } from '../../hooks/useModels';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';
import { formatBudget } from '../../application/mission/formatSessionSummary';
import { useUsageStore } from '../../stores/usageStore';

interface Props {
  open: boolean;
  onClose: () => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMaxBudget: (value: number, previousValue?: number) => void | Promise<void>;
  onOpenAdmin: () => void;
  modelGroups: ModelGroup[];
}

const MODES: Array<'auto' | 'supervised' | 'step-by-step'> = [
  'auto',
  'supervised',
  'step-by-step',
];

const QUALITY_PRESETS: SimpleQualityPreset[] = ['fast', 'balanced', 'best_quality'];

export function SessionDrawer({
  open,
  onClose,
  onChangeMode,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMaxBudget,
  onOpenAdmin,
  modelGroups,
}: Props) {
  const { t } = useI18n();

  const mode = useAgentStore((s) => s.mode);
  const setMode = useAgentStore((s) => s.setMode);
  const model = useAgentStore((s) => s.model);
  const setModel = useAgentStore((s) => s.setModel);
  const qualityPreset = useAgentStore((s) => s.qualityPreset);
  const setQualityPreset = useAgentStore((s) => s.setQualityPreset);

  const cost = useUsageStore((s) => (s as unknown as { totalCost?: number }).totalCost ?? 0);
  const maxBudgetUsd = useConfigStore((s) => s.maxBudgetUsd);
  const setMaxBudget = useConfigStore((s) => s.setMaxBudget);

  const drawerRef = useRef<HTMLDivElement | null>(null);
  const budgetInteractionRef = useRef(false);
  const committedBudgetRef = useRef(maxBudgetUsd);
  const [budgetError, setBudgetError] = useState<string | null>(null);

  useEffect(() => {
    if (!budgetInteractionRef.current) {
      committedBudgetRef.current = maxBudgetUsd;
    }
  }, [maxBudgetUsd]);

  const handleMode = useCallback(
    (next: 'auto' | 'supervised' | 'step-by-step') => {
      onChangeMode(next);
      setMode(next);
    },
    [onChangeMode, setMode],
  );

  const handleModel = useCallback(
    (id: string) => {
      onChangeModel(id);
      setModel(id);
    },
    [onChangeModel, setModel],
  );

  const handleQuality = useCallback(
    (preset: SimpleQualityPreset) => {
      onChangeQualityPreset(preset);
      setQualityPreset(preset);
    },
    [onChangeQualityPreset, setQualityPreset],
  );

  const beginBudgetInteraction = useCallback(() => {
    if (!budgetInteractionRef.current) {
      committedBudgetRef.current = maxBudgetUsd;
      budgetInteractionRef.current = true;
    }
    setBudgetError(null);
  }, [maxBudgetUsd]);

  const commitBudget = useCallback(
    async (value: number) => {
      const previous = committedBudgetRef.current;
      try {
        await onChangeMaxBudget(value, previous);
        committedBudgetRef.current = value;
      } catch (err) {
        console.warn('[SessionDrawer] budget update failed:', err);
        setMaxBudget(previous);
        const message = err instanceof Error ? err.message : String(err);
        setBudgetError(t('session.drawer.budgetUpdateFailed', { message }));
      } finally {
        budgetInteractionRef.current = false;
      }
    },
    [onChangeMaxBudget, setMaxBudget, t],
  );

  // Esc to close; trap focus inside drawer when open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    drawerRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} aria-hidden />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={t('session.drawer.label')}
        tabIndex={-1}
        className="fixed bottom-0 right-0 top-0 z-50 flex w-[360px] flex-col border-l border-ds-border bg-ds-surface shadow-2xl outline-none"
      >
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-ds-border px-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-ds-text">
              {t('session.drawer.title')}
            </span>
            <span className="rounded bg-ds-bg px-1.5 py-0.5 font-mono text-[10px] text-ds-muted">
              {t('session.drawer.scope')}
            </span>
          </div>
          <button
            type="button"
            aria-label={t('common.close')}
            onClick={onClose}
            className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
          >
            <X size={16} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          {/* Mode */}
          <section className="mb-5">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ds-muted">
              {t('session.drawer.modeHeading')}
            </h3>
            <div className="grid grid-cols-3 gap-1">
              {MODES.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleMode(value)}
                  className={`rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                    mode === value
                      ? 'bg-ds-accent/10 text-ds-accent'
                      : 'bg-ds-bg text-ds-muted hover:text-ds-text'
                  }`}
                >
                  {t(`mode.${value}.short` as never) || value}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-ds-muted">
              {t(`mode.${mode}.description` as never)}
            </p>
          </section>

          {/* Quality */}
          <section className="mb-5">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ds-muted">
              {t('session.drawer.qualityHeading')}
            </h3>
            <div className="grid grid-cols-3 gap-1">
              {QUALITY_PRESETS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleQuality(value)}
                  className={`rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                    qualityPreset === value
                      ? 'bg-ds-accent/10 text-ds-accent'
                      : 'bg-ds-bg text-ds-muted hover:text-ds-text'
                  }`}
                >
                  {t(`quality.${value}.short` as never) || value}
                </button>
              ))}
            </div>
          </section>

          {/* Budget */}
          <section className="mb-5">
            <div className="mb-2 flex items-baseline justify-between">
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ds-muted">
                {t('session.drawer.budgetHeading')}
              </h3>
              <span className="font-mono text-[11px] text-ds-muted">
                {formatBudget(cost, maxBudgetUsd)}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={50}
              step={1}
              value={maxBudgetUsd}
              onPointerDown={beginBudgetInteraction}
              onKeyDown={beginBudgetInteraction}
              onChange={(e) => {
                setBudgetError(null);
                setMaxBudget(Number(e.target.value));
              }}
              onPointerUp={(e) => void commitBudget(Number((e.target as HTMLInputElement).value))}
              onKeyUp={(e) => void commitBudget(Number((e.target as HTMLInputElement).value))}
              className="w-full accent-ds-accent"
              aria-label={t('session.drawer.budgetHeading')}
            />
            {budgetError ? (
              <p
                role="alert"
                className="mt-2 text-[11px] text-ds-error"
                data-testid="session-budget-error"
              >
                {budgetError}
              </p>
            ) : null}
            <div className="mt-1 flex justify-between font-mono text-[10px] text-ds-muted">
              <span>$1</span>
              <span>$50</span>
            </div>
          </section>

          {/* Model */}
          <section className="mb-5">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ds-muted">
              {t('session.drawer.modelHeading')}
            </h3>
            <div className="space-y-3">
              {modelGroups.map((group) => (
                <div key={group.titleKey}>
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ds-muted">
                    {t(group.titleKey)}
                  </div>
                  <div className="space-y-1">
                    {group.models.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => handleModel(m.id)}
                        className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[11px] transition-colors ${
                          model === m.id
                            ? 'bg-ds-accent/10 text-ds-accent'
                            : 'text-ds-text hover:bg-ds-bg'
                        }`}
                      >
                        <span className="truncate">{m.displayName}</span>
                        {model === m.id && (
                          <span className="ml-2 font-mono text-[10px] text-ds-accent">●</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <footer className="shrink-0 border-t border-ds-border px-4 py-3">
          <button
            type="button"
            onClick={onOpenAdmin}
            className="flex w-full items-center justify-between rounded px-2 py-1.5 text-[11px] text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text"
          >
            <span>{t('session.drawer.openAdmin')}</span>
            <ChevronRight size={14} />
          </button>
        </footer>
      </aside>
    </>
  );
}
