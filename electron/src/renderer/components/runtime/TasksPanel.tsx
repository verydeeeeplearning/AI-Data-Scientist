/**
 * Runtime tasks panel.
 */

import { TimerReset } from 'lucide-react';
import { useRuntimeStore } from '../../stores/runtimeStore';

const STATUS_STYLES: Record<string, string> = {
  running: 'text-ds-accent',
  succeeded: 'text-ds-success',
  failed: 'text-ds-error',
  cancelled: 'text-ds-muted',
};

export function TasksPanel() {
  const tasks = useRuntimeStore((s) => s.tasks);
  const selectedRunId = useRuntimeStore((s) => s.selectedRunId);
  const selectRun = useRuntimeStore((s) => s.selectRun);

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        <TimerReset size={12} />
        Tasks
        <span className="ml-auto text-ds-text normal-case text-xs">{tasks.length}</span>
      </div>

      {tasks.length === 0 ? (
        <div className="text-xs text-ds-muted">No tracked tasks.</div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div
              key={task.taskId}
              className={`rounded-md border p-2 ${
                selectedRunId === task.runId
                  ? 'border-ds-accent bg-ds-bg/90'
                  : 'border-ds-border bg-ds-bg/70'
              }`}
            >
              <div className="flex items-center gap-2">
                <div className="text-xs font-mono text-ds-text truncate">{task.taskId}</div>
                <span
                  className={`ml-auto text-[10px] uppercase ${STATUS_STYLES[task.status] ?? 'text-ds-muted'}`}
                >
                  {task.status}
                </span>
              </div>
              <div className="mt-1 text-[10px] font-mono text-ds-muted truncate">
                run {task.runId}
              </div>
              {task.error && (
                <div className="mt-1 text-[10px] text-ds-error line-clamp-2">{task.error}</div>
              )}
              <div className="mt-2">
                <button
                  onClick={() => selectRun(task.runId)}
                  className="rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text"
                >
                  Inspect run
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
