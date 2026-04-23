import { useExecutionTimeline } from '../../hooks/useExecutionTimeline';
import { useChatStore } from '../../stores/chatStore';
import { CertificationBoard } from '../../components/runtime/CertificationBoard';
import { ExecutionTimeline } from '../../components/runtime/ExecutionTimeline';
import { GatewayStatusPanel } from '../../components/runtime/GatewayStatusPanel';
import { RegressionBoard } from '../../components/runtime/RegressionBoard';
import { RunDetailDrawer } from '../../components/runtime/RunDetailDrawer';
import { RunsCompareBoard } from '../../components/runtime/RunsCompareBoard';
import { RunsPanel } from '../../components/runtime/RunsPanel';
import { RuntimeAlertsPanel } from '../../components/runtime/RuntimeAlertsPanel';
import { SessionsPanel } from '../../components/runtime/SessionsPanel';
import { TasksPanel } from '../../components/runtime/TasksPanel';
import { useI18n } from '../../stores/i18nStore';
import { useRuntimeStore } from '../../stores/runtimeStore';

export function RunsPage() {
  const { t } = useI18n();
  const { stages } = useExecutionTimeline();
  const selectedRunId = useRuntimeStore((state) => state.selectedRunId);
  const latestAssistantMessageId =
    useChatStore((state) =>
      [...state.messages].reverse().find((message) => message.role === 'assistant')?.id ?? null,
    );

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="border-b border-ds-border px-6 py-4">
        <h1 className="text-lg font-semibold text-ds-text">{t('area.runs.label')}</h1>
        <p className="mt-1 text-sm text-ds-muted">{t('area.runs.description')}</p>
      </div>
      <div className="grid flex-1 gap-4 overflow-y-auto p-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
            <ExecutionTimeline
              stages={stages}
              defaultExpandedKeys={['data_loading']}
              latestAssistantMessageId={latestAssistantMessageId}
            />
          </section>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <GatewayStatusPanel />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <RuntimeAlertsPanel />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <SessionsPanel />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <RunsPanel />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <TasksPanel />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <CertificationBoard />
            </section>
          </div>
          <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
            <RegressionBoard />
          </section>
        </div>
        <div className="min-w-0 space-y-4">
          <section className="overflow-hidden rounded-2xl border border-ds-border bg-ds-surface/70">
            <RunsCompareBoard />
          </section>
          <div className="min-h-[400px] overflow-hidden rounded-2xl border border-ds-border bg-ds-surface/70">
            {selectedRunId ? (
              <RunDetailDrawer />
            ) : (
              <div className="flex h-full min-h-[400px] items-center justify-center px-6 text-center text-sm text-ds-muted">
                Select a run to inspect scorecards, task context, and execution details.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
