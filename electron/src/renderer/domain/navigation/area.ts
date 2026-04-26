export type AreaId =
  | 'mission'
  | 'runs'
  | 'artifacts'
  | 'governance'
  | 'memory'
  | 'admin';

export type AdminSectionId =
  | 'models'
  | 'connectors'
  | 'policies'
  | 'notifications'
  | 'settings';

export interface AreaDescriptor {
  id: AreaId;
  labelKey: string;
  descriptionKey: string;
  defaultPath: string;
  shortcut: string;
  /**
   * Visual grouping in the sidebar. v3 separates `primary` (Artifacts/Runs/
   * Governance) from `admin` with a divider. v2 ignores this field.
   */
  ring?: 'primary' | 'admin';
  /**
   * When true, this area is part of v2 only — v3 routes redirect away from it.
   * `mission` (chat is now floating) and `memory` (folded into Admin) qualify.
   */
  legacyInV3?: boolean;
}

export interface AdminSectionDescriptor {
  id: AdminSectionId;
  labelKey: string;
  defaultPath: string;
}

export interface AreaSelection {
  areaId: AreaId;
  path: string;
  adminSectionId?: AdminSectionId;
  subPath?: string;
}

export const DEFAULT_AREA_PATH = '/mission';

/** v3 default landing — Artifacts is where data scientists actually start. */
export const DEFAULT_AREA_PATH_V3 = '/artifacts/files';

export const AREA_DESCRIPTORS: readonly AreaDescriptor[] = [
  {
    id: 'mission',
    labelKey: 'area.mission.label',
    descriptionKey: 'area.mission.description',
    defaultPath: '/mission',
    shortcut: 'mod+1',
    ring: 'primary',
    legacyInV3: true,
  },
  {
    id: 'runs',
    labelKey: 'area.runs.label',
    descriptionKey: 'area.runs.description',
    defaultPath: '/runs',
    shortcut: 'mod+2',
    ring: 'primary',
  },
  {
    id: 'artifacts',
    labelKey: 'area.artifacts.label',
    descriptionKey: 'area.artifacts.description',
    defaultPath: '/artifacts/files',
    shortcut: 'mod+3',
    ring: 'primary',
  },
  {
    id: 'governance',
    labelKey: 'area.governance.label',
    descriptionKey: 'area.governance.description',
    defaultPath: '/governance/review',
    shortcut: 'mod+4',
    ring: 'primary',
  },
  {
    id: 'memory',
    labelKey: 'area.memory.label',
    descriptionKey: 'area.memory.description',
    defaultPath: '/memory/learning',
    shortcut: 'mod+5',
    ring: 'primary',
    legacyInV3: true,
  },
  {
    id: 'admin',
    labelKey: 'area.admin.label',
    descriptionKey: 'area.admin.description',
    defaultPath: '/admin/models',
    shortcut: 'mod+,',
    ring: 'admin',
  },
] as const;

export const ADMIN_SECTION_DESCRIPTORS: readonly AdminSectionDescriptor[] = [
  { id: 'models', labelKey: 'area.admin.models', defaultPath: '/admin/models' },
  { id: 'connectors', labelKey: 'area.admin.connectors', defaultPath: '/admin/connectors' },
  { id: 'policies', labelKey: 'area.admin.policies', defaultPath: '/admin/policies' },
  { id: 'notifications', labelKey: 'area.admin.notifications', defaultPath: '/admin/notifications' },
  { id: 'settings', labelKey: 'area.admin.settings', defaultPath: '/admin/settings' },
] as const;

export function isAreaId(value: string): value is AreaId {
  return AREA_DESCRIPTORS.some((descriptor) => descriptor.id === value);
}

export function isAdminSectionId(value: string): value is AdminSectionId {
  return ADMIN_SECTION_DESCRIPTORS.some((descriptor) => descriptor.id === value);
}

export function getAreaDescriptor(areaId: AreaId): AreaDescriptor {
  return (
    AREA_DESCRIPTORS.find((descriptor) => descriptor.id === areaId) ?? AREA_DESCRIPTORS[0]
  );
}

export function getAdminSectionDescriptor(sectionId: AdminSectionId): AdminSectionDescriptor {
  return (
    ADMIN_SECTION_DESCRIPTORS.find((descriptor) => descriptor.id === sectionId) ??
    ADMIN_SECTION_DESCRIPTORS[0]
  );
}

/**
 * Areas shown in the v3 sidebar primary group, in display order.
 * Excludes `mission` and `memory` (replaced by MissionContextBar + FloatingChat
 * and folded into Admin respectively).
 */
export const PRIMARY_AREAS_V3: readonly AreaDescriptor[] = AREA_DESCRIPTORS.filter(
  (d) => d.ring === 'primary' && !d.legacyInV3,
);

/** Returns true when an area id exists but should be hidden/redirected in v3. */
export function isLegacyV3AreaId(value: string): boolean {
  return AREA_DESCRIPTORS.find((d) => d.id === value)?.legacyInV3 === true;
}
