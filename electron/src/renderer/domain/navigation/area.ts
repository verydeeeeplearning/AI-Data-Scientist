export type AreaId =
  | 'mission'
  | 'runs'
  | 'artifacts'
  | 'governance'
  | 'memory'
  | 'admin';

export type AdminSectionId = 'models' | 'connectors' | 'policies' | 'settings';

export interface AreaDescriptor {
  id: AreaId;
  labelKey: string;
  descriptionKey: string;
  defaultPath: string;
  shortcut: string;
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

export const AREA_DESCRIPTORS: readonly AreaDescriptor[] = [
  {
    id: 'mission',
    labelKey: 'area.mission.label',
    descriptionKey: 'area.mission.description',
    defaultPath: '/mission',
    shortcut: 'mod+1',
  },
  {
    id: 'runs',
    labelKey: 'area.runs.label',
    descriptionKey: 'area.runs.description',
    defaultPath: '/runs',
    shortcut: 'mod+2',
  },
  {
    id: 'artifacts',
    labelKey: 'area.artifacts.label',
    descriptionKey: 'area.artifacts.description',
    defaultPath: '/artifacts/files',
    shortcut: 'mod+3',
  },
  {
    id: 'governance',
    labelKey: 'area.governance.label',
    descriptionKey: 'area.governance.description',
    defaultPath: '/governance/review',
    shortcut: 'mod+4',
  },
  {
    id: 'memory',
    labelKey: 'area.memory.label',
    descriptionKey: 'area.memory.description',
    defaultPath: '/memory/learning',
    shortcut: 'mod+5',
  },
  {
    id: 'admin',
    labelKey: 'area.admin.label',
    descriptionKey: 'area.admin.description',
    defaultPath: '/admin/models',
    shortcut: 'mod+,',
  },
] as const;

export const ADMIN_SECTION_DESCRIPTORS: readonly AdminSectionDescriptor[] = [
  { id: 'models', labelKey: 'area.admin.models', defaultPath: '/admin/models' },
  { id: 'connectors', labelKey: 'area.admin.connectors', defaultPath: '/admin/connectors' },
  { id: 'policies', labelKey: 'area.admin.policies', defaultPath: '/admin/policies' },
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
