import type { ExternalReferenceView, WorkObjectListItemView, WorkObjectPhase } from '../../types/workObject';

export function formatWorkObjectPhaseLabel(phase: WorkObjectPhase): string {
  switch (phase) {
    case 'intake':
      return 'Intake';
    case 'executing':
      return 'Executing';
    case 'review':
      return 'Review';
    case 'documenting':
      return 'Documenting';
    case 'followup':
      return 'Follow-up';
    case 'closed':
      return 'Closed';
    case 'failed':
      return 'Failed';
  }
}

export function filterWorkObjectItems(
  items: WorkObjectListItemView[],
  searchText: string,
): WorkObjectListItemView[] {
  const needle = searchText.trim().toLowerCase();
  if (!needle) {
    return items;
  }
  return items.filter((item) =>
    item.work_object_id.toLowerCase().includes(needle)
    || item.task_contract_id.toLowerCase().includes(needle)
    || item.title.toLowerCase().includes(needle),
  );
}

export function formatExternalReferenceLabel(reference: ExternalReferenceView | null | undefined): string {
  if (!reference) {
    return '-';
  }
  return `${reference.system}:${reference.resource_type}:${reference.resource_id}`;
}

const PHASE_ORDER: WorkObjectPhase[] = [
  'intake',
  'executing',
  'review',
  'documenting',
  'followup',
  'closed',
];

const TERMINAL_PHASES: ReadonlySet<WorkObjectPhase> = new Set(['closed', 'failed']);

export function nextPhase(current: WorkObjectPhase): WorkObjectPhase | null {
  if (TERMINAL_PHASES.has(current)) {
    return null;
  }
  const idx = PHASE_ORDER.indexOf(current);
  if (idx < 0 || idx >= PHASE_ORDER.length - 1) {
    return null;
  }
  return PHASE_ORDER[idx + 1];
}

export function canAdvance(phase: WorkObjectPhase): boolean {
  return nextPhase(phase) !== null;
}

export function canClose(phase: WorkObjectPhase): boolean {
  return !TERMINAL_PHASES.has(phase);
}

export function getPendingPolicyActionCount(metadata: Record<string, unknown>): number {
  const pending = metadata.pending_policy_actions;
  if (!Array.isArray(pending)) {
    return 0;
  }
  return pending.filter((item) => {
    if (!item || typeof item !== 'object') {
      return false;
    }
    return (item as { status?: unknown }).status === 'pending';
  }).length;
}
