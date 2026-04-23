import { LearningInbox } from '../../components/learning/LearningInbox';
import { RecurringGoalsPanel } from '../../components/runtime/RecurringGoalsPanel';
import { StandingOrdersPanel } from '../../components/runtime/StandingOrdersPanel';
import { useI18n } from '../../stores/i18nStore';

export function MemoryPage() {
  const { t } = useI18n();

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="border-b border-ds-border px-6 py-4">
        <h1 className="text-lg font-semibold text-ds-text">{t('area.memory.label')}</h1>
        <p className="mt-1 text-sm text-ds-muted">{t('area.memory.description')}</p>
      </div>
      <div className="grid flex-1 gap-4 overflow-y-auto p-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
          <LearningInbox />
        </section>
        <div className="space-y-4">
          <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-3">
            <RecurringGoalsPanel />
          </section>
          <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-3">
            <StandingOrdersPanel />
          </section>
        </div>
      </div>
    </div>
  );
}
