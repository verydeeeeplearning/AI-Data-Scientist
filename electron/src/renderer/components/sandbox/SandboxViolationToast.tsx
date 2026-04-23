/**
 * Non-blocking toast stack for sandbox violations.
 *
 * The sandbox preamble blocks/flags actions like writing outside the
 * workspace, hitting an unapproved network host, or exceeding the memory
 * cap. These violations used to live only in tool-output JSON; this stack
 * surfaces them to the user the moment they happen, with an 8s auto-dismiss.
 */

import { ShieldAlert, Network, FolderX, MemoryStick, Terminal } from 'lucide-react';
import { useEffect } from 'react';
import { Toast, ToastViewport } from '../../design-system/primitives';
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
    <ToastViewport
      placement="bottom-right"
      label="Sandbox violations"
      className="z-40 max-w-[360px]"
    >
      {visible.map((v) => (
        <Toast
          key={v.id}
          title={KIND_LABEL[v.kind] ?? 'Sandbox violation'}
          description={v.detail}
          meta={v.tool}
          tone={v.blocked ? 'danger' : 'warning'}
          leadingIcon={<KindIcon kind={v.kind} />}
          announce="polite"
          onDismiss={() => acknowledge(v.id)}
          dismissLabel="Dismiss sandbox violation"
          className="text-xs"
        >
          <div className="text-[11px] leading-snug text-ds-text/90">
            {v.blocked ? 'Action was blocked by policy.' : 'Action was flagged before completion.'}
          </div>
        </Toast>
      ))}
    </ToastViewport>
  );
}
