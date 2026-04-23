/**
 * useAudienceView — renderer-friendly facade over the workspace store
 * audience-view slice plus the domain-level profile lookup.
 *
 * Components consume this hook so they don't have to wire two imports
 * (zustand selector + `getAudienceViewProfile`) at every call site.
 */

import { useEffect, useRef } from 'react';
import {
  getAudienceViewProfile,
  type AudienceView,
  type AudienceViewProfile,
} from '../domain/workspace/audienceView';
import { reportAudienceSwitch } from '../infrastructure/api/cardApi';
import { useWorkspaceStore } from '../stores/workspaceStore';

export interface UseAudienceViewResult {
  readonly view: AudienceView;
  readonly profile: AudienceViewProfile;
  readonly setView: (view: AudienceView) => void;
}

export interface UseAudienceViewTelemetryOptions {
  readonly sessionId?: string | null;
}

export function useAudienceView(): UseAudienceViewResult {
  const view = useWorkspaceStore((state) => state.audienceView);
  const setView = useWorkspaceStore((state) => state.setAudienceView);
  const profile = getAudienceViewProfile(view);
  return { view, profile, setView };
}

/**
 * Best-effort audience-switch beacon that records the active workspace lens
 * through the backend runtime-event log. Used by the workspace shell after
 * the user changes audience.
 */
export function useAudienceViewTelemetry(
  view: AudienceView,
  options: UseAudienceViewTelemetryOptions = {},
): void {
  const previousView = useRef<AudienceView | null>(null);

  useEffect(() => {
    const fromAudience = previousView.current;
    previousView.current = view;
    if (fromAudience === null || fromAudience === view) {
      return;
    }

    void reportAudienceSwitch({
      fromAudience,
      toAudience: view,
      sessionId: options.sessionId ?? null,
    }).catch((error) => {
      console.warn('[useAudienceViewTelemetry] audience switch beacon failed:', error);
    });
  }, [options.sessionId, view]);
}

// Re-export so consumers reach the pure lookup through the hook module
// without grabbing the domain layer themselves.
export { getAudienceViewProfile };
export type { AudienceView, AudienceViewProfile };
