import { useCallback, useEffect, useState } from 'react';

import {
  SIDEBAR_STORAGE_KEY,
  createInitialSidebarLayoutState,
  parseStoredSidebarLayoutState,
  resolveResponsiveSidebarLayoutState,
  serializeSidebarLayoutState,
  toggleSidebarLayoutState,
  type SidebarLayoutState,
} from '../utils/sidebarLayout';

function getViewportWidth(): number {
  if (typeof window === 'undefined') {
    return 1024;
  }
  return window.innerWidth;
}

function loadStoredState(): SidebarLayoutState | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return parseStoredSidebarLayoutState(window.localStorage.getItem(SIDEBAR_STORAGE_KEY));
  } catch {
    return null;
  }
}

function saveStoredState(state: SidebarLayoutState): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, serializeSidebarLayoutState(state));
  } catch {
    // Ignore localStorage write failures and keep the in-memory state.
  }
}

export function useSidebarCollapse() {
  const [layoutState, setLayoutState] = useState<SidebarLayoutState>(() => {
    const stored = loadStoredState();
    return stored ?? createInitialSidebarLayoutState(getViewportWidth());
  });

  useEffect(() => {
    const handleResize = () => {
      setLayoutState((current) => {
        const next = resolveResponsiveSidebarLayoutState(current, getViewportWidth());
        if (next.collapsed === current.collapsed && next.collapsedByUser === current.collapsedByUser) {
          return current;
        }
        return next;
      });
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  useEffect(() => {
    saveStoredState(layoutState);
  }, [layoutState]);

  const toggleSidebar = useCallback(() => {
    setLayoutState((current) => toggleSidebarLayoutState(current));
  }, []);

  return {
    collapsed: layoutState.collapsed,
    collapsedByUser: layoutState.collapsedByUser,
    toggleSidebar,
  };
}
