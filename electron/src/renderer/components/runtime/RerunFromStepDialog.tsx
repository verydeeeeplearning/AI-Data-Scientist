import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { rerunFromStep } from '../../application/run/rerunFromStep';
import { Button, DialogShell } from '../../design-system/primitives';
import { useRerunFromStep } from '../../hooks/useRerunFromStep';
import { useReasoningTraceStore } from '../../stores/reasoningTraceStore';
import type { PlanNode } from '../../types/events';
import { createRuntimeDialogA11yController } from './runtimeDialogA11y';

interface FlatNode {
  readonly id: string;
  readonly label: string;
  readonly status: string;
  readonly depth: number;
}

interface Props {
  readonly parentRunId: string;
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onRerunStarted?: (newRunId: string, planNodeId: string) => void;
}

export const RERUN_FROM_STEP_DIALOG_IDS = {
  shell: 'run-rerun-from-step-shell',
  title: 'run-rerun-from-step-title',
  description: 'run-rerun-from-step-description',
} as const;

function flattenPlan(node: PlanNode | null, depth = 0): FlatNode[] {
  if (node == null) {
    return [];
  }
  const head: FlatNode = {
    id: node.id,
    label: node.label,
    status: node.status,
    depth,
  };
  const rest = node.children.flatMap((child) => flattenPlan(child, depth + 1));
  return [head, ...rest];
}

export function RerunFromStepDialog({
  parentRunId,
  open,
  onClose,
  onRerunStarted,
}: Props) {
  const planTree = useReasoningTraceStore((state) => state.planState.planTree);
  const port = useRerunFromStep();
  const dialogRef = useRef<HTMLElement | null>(null);
  const a11yRef = useRef<ReturnType<typeof createRuntimeDialogA11yController> | null>(null);
  const [busyNodeId, setBusyNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const nodes = useMemo(() => flattenPlan(planTree), [planTree]);

  useEffect(() => {
    if (!open) {
      setBusyNodeId(null);
      setError(null);
      setStatus(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const element = document.getElementById(RERUN_FROM_STEP_DIALOG_IDS.shell);
    if (!(element instanceof HTMLElement)) {
      return undefined;
    }
    dialogRef.current = element;
    const controller = createRuntimeDialogA11yController(element);
    a11yRef.current = controller;
    controller.activate();
    return () => {
      controller.deactivate();
      a11yRef.current = null;
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const handleSelect = async (nodeId: string) => {
    if (!parentRunId.trim()) {
      setError('parentRunId is required');
      return;
    }
    setBusyNodeId(nodeId);
    setError(null);
    setStatus(null);
    try {
      const result = await rerunFromStep(port, {
        parentRunId,
        planNodeId: nodeId,
      });
      setStatus(`Rerun ${result.runId} started from node ${nodeId}.`);
      onRerunStarted?.(result.runId, nodeId);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(`Rerun failed: ${detail}`);
    } finally {
      setBusyNodeId(null);
    }
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const action = a11yRef.current?.handleKeyDown(event.nativeEvent);
    if (action === 'escape' && busyNodeId === null) {
      onClose();
    }
  };

  const footer = (
    <Button variant="secondary" onClick={onClose} disabled={busyNodeId !== null}>
      Close
    </Button>
  );

  return (
    <DialogShell
      id={RERUN_FROM_STEP_DIALOG_IDS.shell}
      open={open}
      size="sm"
      title={<span id={RERUN_FROM_STEP_DIALOG_IDS.title}>Rerun from a plan step</span>}
      description={
        <span id={RERUN_FROM_STEP_DIALOG_IDS.description}>
          Pick a node from the current plan tree. The new run is anchored at
          that step and inherits this run as its parent.
        </span>
      }
      footer={footer}
      dismissLabel="Close rerun dialog"
      onDismiss={busyNodeId === null ? onClose : undefined}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      {nodes.length === 0 ? (
        <div className="rounded-ds-lg border border-dashed border-ds-border bg-ds-bg/40 px-ds-3 py-ds-4 text-ds-xs text-ds-muted">
          No plan tree is available for the current run. Wait until the
          agent has emitted a plan, then try again.
        </div>
      ) : (
        <ul className="max-h-72 space-y-ds-2 overflow-y-auto pr-ds-1">
          {nodes.map((node) => {
            const busy = busyNodeId === node.id;
            return (
              <li key={node.id}>
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={busyNodeId !== null}
                  onClick={() => void handleSelect(node.id)}
                  className="w-full justify-between rounded-ds-lg bg-ds-bg/40 px-ds-3 py-ds-2 text-left shadow-none"
                  style={{ paddingLeft: `${0.75 + node.depth * 0.75}rem` }}
                >
                  <span className="min-w-0 truncate">{node.label}</span>
                  <span className="ml-ds-2 shrink-0 text-[10px] uppercase tracking-widest text-ds-muted">
                    {busy ? 'Starting...' : node.status}
                  </span>
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      {error && (
        <div className="mt-ds-3 text-ds-xs text-rose-300" role="alert">
          {error}
        </div>
      )}
      {status && (
        <div
          className="mt-ds-3 text-ds-xs text-emerald-300"
          role="status"
          aria-live="polite"
        >
          {status}
        </div>
      )}
    </DialogShell>
  );
}
