/**
 * Pure presenter that adapts the desktop runtime/agent/workflow shapes
 * to the mobile mission summary view.
 *
 * Centralising this lets us assert the contract: the mobile presenter
 * accepts the same data shape as the desktop renderer reads, and degrades
 * gracefully when fields are missing on the wire.
 */

import type { RuntimeStatusSnapshot } from '../../renderer/stores/runtimeStore';
import type { ApprovalRequest } from '../../renderer/stores/workflowStore';

export interface MobileMissionStat {
  readonly id: 'sessions' | 'runs' | 'tasks' | 'approvals';
  readonly value: number;
}

export interface MobileMissionViewInput {
  readonly status: RuntimeStatusSnapshot | null | undefined;
  readonly approvals: readonly ApprovalRequest[] | null | undefined;
  readonly model?: string | null;
  readonly mode?: string | null;
}

export interface MobileMissionView {
  readonly stats: readonly MobileMissionStat[];
  readonly model: string | null;
  readonly mode: string | null;
  readonly hasRuntime: boolean;
}

function safeNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

export function buildMobileMissionView(
  input: MobileMissionViewInput,
): MobileMissionView {
  const status = input.status ?? null;
  const approvals = input.approvals ?? [];
  const pendingApprovals = approvals.filter((a) => a.status === 'pending').length;

  const stats: MobileMissionStat[] = [
    { id: 'sessions', value: safeNumber(status?.activeSessions) },
    { id: 'runs', value: safeNumber(status?.activeRuns) },
    { id: 'tasks', value: safeNumber(status?.activeTasks) },
    { id: 'approvals', value: pendingApprovals },
  ];

  const trim = (raw: string | null | undefined): string | null => {
    if (typeof raw !== 'string') {
      return null;
    }
    const value = raw.trim();
    return value.length > 0 ? value : null;
  };

  return {
    stats,
    model: trim(input.model),
    mode: trim(input.mode),
    hasRuntime: status !== null,
  };
}
