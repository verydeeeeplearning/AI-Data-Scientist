import {
  DEFAULT_AREA_PATH,
  getAreaDescriptor,
  getAdminSectionDescriptor,
  isAdminSectionId,
  isAreaId,
  type AreaSelection,
} from '../../domain/navigation/area';
import { migrateLegacyRoute, type MigrationResult } from './migrateLegacyRoute';

export interface ResolvedNavigationState {
  path: string;
  selection: AreaSelection;
  migration: MigrationResult;
}

function stripHashPrefix(hash: string): string {
  const value = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!value) {
    return DEFAULT_AREA_PATH;
  }
  return value.startsWith('/') ? value : `/${value}`;
}

export function normalizeNavigationPath(path: string): string {
  const raw = stripHashPrefix(path).replace(/\/{2,}/g, '/');
  const cleaned = raw.replace(/\/+$/, '');
  return cleaned || DEFAULT_AREA_PATH;
}

export function buildNavigationHash(path: string): string {
  return `#${normalizeNavigationPath(path)}`;
}

export function parseAreaSelection(path: string): AreaSelection {
  const normalized = normalizeNavigationPath(path);
  const [areaCandidate = 'mission', ...rest] = normalized.slice(1).split('/');
  const areaId = isAreaId(areaCandidate) ? areaCandidate : 'mission';
  const descriptor = getAreaDescriptor(areaId);
  if (areaId === 'admin') {
    const sectionCandidate = rest[0] ?? '';
    const adminSectionId = isAdminSectionId(sectionCandidate)
      ? sectionCandidate
      : getAdminSectionDescriptor('models').id;
    return {
      areaId,
      path: normalized === '/admin' ? descriptor.defaultPath : normalized,
      adminSectionId,
      subPath: rest.slice(1).join('/'),
    };
  }
  return {
    areaId,
    path: normalized === `/${areaId}` ? descriptor.defaultPath : normalized,
    subPath: rest.join('/'),
  };
}

export function resolveNavigationState(rawHash: string): ResolvedNavigationState {
  const normalized = normalizeNavigationPath(rawHash);
  const migrated = migrateLegacyRoute(normalized);
  const selection = parseAreaSelection(migrated.newPath);
  return {
    path: selection.path,
    selection,
    migration: migrated,
  };
}
