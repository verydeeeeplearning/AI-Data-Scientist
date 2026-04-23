import { useEffect, useMemo, useState } from 'react';
import type { AreaSelection } from '../domain/navigation/area';
import {
  buildNavigationHash,
  resolveNavigationState,
  type ResolvedNavigationState,
} from '../application/navigation/resolveNavigationState';

const MIGRATION_NOTICE_STARTED_AT_KEY = 'ds-agent-ia-v2-migration-started-at';
const MIGRATION_NOTICE_WINDOW_MS = 28 * 24 * 60 * 60 * 1000;

export interface MigrationNoticeState {
  fromPath: string;
  toPath: string;
}

function readMigrationNoticeStart(): number | null {
  try {
    const raw = window.localStorage.getItem(MIGRATION_NOTICE_STARTED_AT_KEY);
    if (!raw) {
      return null;
    }
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function shouldShowMigrationNotice(state: ResolvedNavigationState): boolean {
  if (!state.migration.showMigrationToast || !state.migration.migratedFrom) {
    return false;
  }
  const now = Date.now();
  const startedAt = readMigrationNoticeStart();
  const effectiveStartedAt = startedAt ?? now;
  if (startedAt === null) {
    try {
      window.localStorage.setItem(MIGRATION_NOTICE_STARTED_AT_KEY, String(now));
    } catch {
      // ignore storage failures
    }
  }
  return now - effectiveStartedAt <= MIGRATION_NOTICE_WINDOW_MS;
}

function replaceHash(path: string): void {
  const nextHash = buildNavigationHash(path);
  if (window.location.hash === nextHash) {
    return;
  }
  window.history.replaceState(null, '', `${window.location.search}${nextHash}`);
}

export interface HashNavigationState {
  currentPath: string;
  selection: AreaSelection;
  migrationNotice: MigrationNoticeState | null;
  navigate: (path: string) => void;
  dismissMigrationNotice: () => void;
}

export function useHashNavigation(): HashNavigationState {
  const [dismissedNoticeKey, setDismissedNoticeKey] = useState<string | null>(null);
  const [routeState, setRouteState] = useState<ResolvedNavigationState>(() =>
    resolveNavigationState(window.location.hash),
  );

  useEffect(() => {
    const handleHashChange = () => {
      setRouteState(resolveNavigationState(window.location.hash));
    };
    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    replaceHash(routeState.path);
  }, [routeState.path]);

  const migrationNotice = useMemo(() => {
    if (!shouldShowMigrationNotice(routeState) || !routeState.migration.migratedFrom) {
      return null;
    }
    const noticeKey = `${routeState.migration.migratedFrom}:${routeState.path}`;
    if (dismissedNoticeKey === noticeKey) {
      return null;
    }
    return {
      fromPath: routeState.migration.migratedFrom,
      toPath: routeState.path,
    };
  }, [dismissedNoticeKey, routeState]);

  return {
    currentPath: routeState.path,
    selection: routeState.selection,
    migrationNotice,
    navigate: (path: string) => {
      const next = resolveNavigationState(path);
      setRouteState(next);
      window.location.hash = buildNavigationHash(next.path);
    },
    dismissMigrationNotice: () => {
      if (!migrationNotice) {
        return;
      }
      setDismissedNoticeKey(`${migrationNotice.fromPath}:${migrationNotice.toPath}`);
    },
  };
}
