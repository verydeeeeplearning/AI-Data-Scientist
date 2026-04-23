export interface SidebarLayoutState {
  collapsed: boolean;
  collapsedByUser: boolean;
}

export const SIDEBAR_STORAGE_KEY = 'ds-agent-sidebar-layout';
export const SIDEBAR_BREAKPOINT = 768;
export const SIDEBAR_EXPANDED_WIDTH = 240;
export const SIDEBAR_COLLAPSED_WIDTH = 56;

export function createInitialSidebarLayoutState(viewportWidth: number): SidebarLayoutState {
  return {
    collapsed: viewportWidth < SIDEBAR_BREAKPOINT,
    collapsedByUser: false,
  };
}

export function toggleSidebarLayoutState(state: SidebarLayoutState): SidebarLayoutState {
  return {
    collapsed: !state.collapsed,
    collapsedByUser: true,
  };
}

export function resolveResponsiveSidebarLayoutState(
  state: SidebarLayoutState,
  viewportWidth: number,
): SidebarLayoutState {
  if (state.collapsedByUser) {
    return state;
  }
  return createInitialSidebarLayoutState(viewportWidth);
}

export function serializeSidebarLayoutState(state: SidebarLayoutState): string {
  return JSON.stringify(state);
}

export function parseStoredSidebarLayoutState(
  raw: string | null | undefined,
): SidebarLayoutState | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<SidebarLayoutState>;
    if (typeof parsed.collapsed !== 'boolean' || typeof parsed.collapsedByUser !== 'boolean') {
      return null;
    }
    return {
      collapsed: parsed.collapsed,
      collapsedByUser: parsed.collapsedByUser,
    };
  } catch {
    return null;
  }
}
