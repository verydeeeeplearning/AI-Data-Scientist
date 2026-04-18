/**
 * Non-blocking toast stack for sandbox violations.
 *
 * The sandbox preamble blocks/flags actions like writing outside the
 * workspace, hitting an unapproved network host, or exceeding the memory
 * cap. These violations used to live only in tool-output JSON; this stack
 * surfaces them to the user the moment they happen, with an 8s auto-dismiss.
 */

import { ShieldAlert, Network, FolderX, MemoryStick, Terminal, X } from 'lucide-react';
import { useEffect } from 'react';
import { useWorkflowStore } from '../../stores/workflowStore';
import type { SandboxViolationRecord } from '../../stores/workflowStore';

const TOAST_TTL_MS = 8000;
const VISIBLE_LIMIT = 3;

const KIND_LABEL: Record<SandboxViolationRecord['kind'], string> = {
  filesystem: 'Filesystem blocked',
  network: 'Network blocked',
  subprocess: 'Subprocess blocked',
  resource: 'Resource limit hit',
};

function KindIcon({ kind }: { kind: SandboxViolationRecord['kind'] }) {
  const props = { size: 14, className: 'shrink-0' };
  switch (kind) {
    case 'filesystem':
      return <FolderX {...props} />;
    case 'network':
      return <Network {...props} />;
    case 'subprocess':
      return <Terminal {...props} />;
    case 'resource':
      return <MemoryStick {...props} />;
    default:
      return <ShieldAlert {...props} />;
  }
}

export function SandboxViolationToast() {
  const violations = useWorkflowStore((s) => s.sandboxViolations);
  const acknowledge = useWorkflowStore((s) => s.acknowledgeSandboxViolation);

  const visible = violations
    .filter((v) => !v.acknowledged)
    .slice(0, VISIBLE_LIMIT);

  // Auto-dismiss each toast after TTL.
  useEffect(() => {
    if (visible.length === 0) return;
    const timers = visible.map((v) =>
      window.setTimeout(() => acknowledge(v.id), TOAST_TTL_MS)
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [visible, acknowledge]);

  if (visible.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-40 flex flex-col gap-2 max-w-[360px]"
    >
      {visible.map((v) => (
        <div
          key={v.id}
          className={`rounded-md border px-3 py-2 shadow-lg text-xs animate-in fade-in slide-in-from-bottom-2 ${
            v.blocked
              ? 'bg-ds-error/10 border-ds-error/40 text-ds-text'
              : 'bg-ds-warn/10 border-ds-warn/40 text-ds-text'
          }`}
        >
          <div className="flex items-start gap-2">
            <KindIcon kind={v.kind} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">
                  {KIND_LABEL[v.kind] ?? 'Sandbox violation'}
                </span>
                <span className="text-[10px] text-ds-muted font-mono shrink-0">{v.tool}</span>
              </div>
              <div className="mt-1 text-[11px] text-ds-text/90 break-words leading-snug">
                {v.detail}
              </div>
            </div>
            <button
              onClick={() => acknowledge(v.id)}
              aria-label="Dismiss"
              className="text-ds-muted hover:text-ds-text shrink-0"
            >
              <X size={12} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
