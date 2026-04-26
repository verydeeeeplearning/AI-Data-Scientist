import { useState } from 'react';

import { useConfigStore } from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';
import { useUsageStore } from '../../stores/usageStore';
import type { RpcFn } from './types';

export function CostSettings({ rpc }: { rpc: RpcFn }) {
  const { t } = useI18n();
  const {
    maxBudgetUsd,
    budgetWarningThresholdPct,
    setMaxBudget,
    setBudgetWarningThresholdPct,
  } = useConfigStore();
  const summary = useUsageStore((s) => s.summary);
  const [saving, setSaving] = useState(false);

  const persistBudget = async (value: number) => {
    setSaving(true);
    try {
      await rpc('config.set', { path: 'provider.max_budget_usd', value });
    } finally {
      setSaving(false);
    }
  };

  const persistWarningThreshold = async (value: number) => {
    setSaving(true);
    try {
      await rpc('config.set', { path: 'provider.budget_warning_threshold_pct', value });
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = async (value: number) => {
    setMaxBudget(value);
    await persistBudget(value);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium text-ds-text">
              {t('settings.cost.monthlyBudget.title')}
            </div>
            <div className="text-[11px] text-ds-muted">
              {t('settings.cost.monthlyBudget.description')}
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-semibold text-ds-text">
              ${summary?.monthlyCostUsd.toFixed(2) ?? '0.00'}
            </div>
            <div className="text-[11px] text-ds-muted">
              {summary?.monthlyBudgetUsd == null
                ? t('settings.cost.unlimited')
                : t('settings.cost.limit', { value: summary.monthlyBudgetUsd.toFixed(0) })}
            </div>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-ds-muted">$</span>
          <input
            type="number"
            value={maxBudgetUsd}
            min={0}
            step={1}
            aria-label={t('settings.cost.maxBudgetAria')}
            onChange={(event) => setMaxBudget(parseFloat(event.target.value) || 0)}
            onBlur={(event) => {
              const value = parseFloat(event.target.value) || 0;
              void persistBudget(value);
            }}
            className="w-28 rounded border border-ds-border bg-ds-surface px-3 py-1.5 text-xs font-mono text-ds-text focus:border-ds-accent focus:outline-none"
          />
          <span className="text-xs text-ds-muted">{t('settings.cost.unlimitedHint')}</span>
          {saving && <span className="text-[11px] text-ds-muted">{t('settings.cost.saving')}</span>}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-ds-muted">{t('settings.cost.warnAt')}</span>
          <select
            value={budgetWarningThresholdPct}
            aria-label={t('settings.cost.warningThresholdAria')}
            onChange={(event) => {
              const value = Number(event.target.value) || 80;
              setBudgetWarningThresholdPct(value);
              void persistWarningThreshold(value);
            }}
            className="rounded border border-ds-border bg-ds-surface px-3 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          >
            {[60, 80, 90].map((value) => (
              <option key={value} value={value}>
                {value}%{value === 60 ? ` (${t('settings.cost.recommended')})` : ''}
              </option>
            ))}
          </select>
          <span className="text-xs text-ds-muted">{t('settings.cost.blockHint')}</span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {[5, 10, 20, 50, 0].map((value) => (
            <button
              key={value}
              onClick={() => void applyPreset(value)}
              className="rounded-full border border-ds-border bg-ds-surface px-3 py-1 text-[11px] text-ds-text transition-colors hover:border-ds-accent/50"
            >
              {value === 0
                ? t('settings.cost.unlimited')
                : t('settings.cost.presetMonthly', { value })}
            </button>
          ))}
        </div>
      </div>

      {summary && (
        <div className="grid gap-3 md:grid-cols-3">
          <StatCard label={t('settings.cost.stat.thisMonth')} value={`$${summary.monthlyCostUsd.toFixed(2)}`} />
          <StatCard label={t('settings.cost.stat.today')} value={`$${summary.todayCostUsd.toFixed(2)}`} />
          <StatCard label={t('settings.cost.stat.currentSession')} value={`$${summary.sessionCostUsd.toFixed(2)}`} />
        </div>
      )}

      {summary && summary.cacheSavingsUsd > 0 && (
        <div className="rounded-lg border border-ds-success/30 bg-ds-success/10 px-3 py-2 text-[11px] text-ds-success">
          {t('settings.cost.cacheSavings', { value: summary.cacheSavingsUsd.toFixed(2) })}
        </div>
      )}

      {summary && summary.byModel.length > 0 && (
        <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
          <div className="text-xs font-medium text-ds-text">{t('settings.cost.byModel')}</div>
          <div className="mt-2 space-y-2">
            {summary.byModel.slice(0, 4).map((item) => (
              <div key={item.model} className="flex items-center justify-between gap-3 text-[11px]">
                <div className="min-w-0">
                  <div className="truncate text-ds-text">{item.model}</div>
                  <div className="text-ds-muted">
                    {t('settings.cost.runCount', { count: item.runCount })}
                  </div>
                </div>
                <div className="font-mono text-ds-text">${item.costUsd.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2">
      <div className="text-[11px] text-ds-muted">{label}</div>
      <div className="mt-1 text-sm font-semibold text-ds-text">{value}</div>
    </div>
  );
}
