/**
 * Shared mutation gate for renderer call sites.
 *
 * Wraps {@link useAccessRole} so each mutation surface can ask
 * "is this resource read-only for me right now?" without duplicating role
 * resolution. Returns ``{ canMutate, reason }`` where ``reason`` is a stable
 * i18n key suitable for tooltips on disabled controls.
 *
 * The hook intentionally returns a viewer-friendly *disable* signal — pages
 * keep mutation controls visible (so the read-only state is legible) and
 * surface the explanation through ``aria-disabled`` + tooltips.
 */

import { useAccessRole, type ViewerRole } from './useAccessRole';

export interface UseCanMutateOptions {
  readonly forceRole?: ViewerRole;
}

export interface CanMutateResult {
  readonly role: ViewerRole;
  readonly canMutate: boolean;
  readonly reason?: string;
}

const VIEWER_REASON_KEY = 'share.banner.readOnlyTooltip';

export function resolveCanMutate(role: ViewerRole): CanMutateResult {
  if (role === 'owner') {
    return { role, canMutate: true };
  }
  return { role, canMutate: false, reason: VIEWER_REASON_KEY };
}

export function useCanMutate(options: UseCanMutateOptions = {}): CanMutateResult {
  const { role } = useAccessRole({ forceRole: options.forceRole });
  return resolveCanMutate(role);
}
