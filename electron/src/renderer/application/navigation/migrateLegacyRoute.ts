export interface MigrationResult {
  newPath: string;
  migratedFrom?: string;
  showMigrationToast: boolean;
}

const LEGACY_ROUTE_MAP: Record<string, string> = {
  '/files': '/artifacts/files',
  '/workflow': '/mission',
  '/workflow/runs': '/runs',
  '/review': '/governance/review',
  '/runtime': '/runs',
  '/experiments': '/artifacts/experiments',
  '/portfolio': '/artifacts/portfolio',
  '/learning': '/memory/learning',
  '/settings': '/admin/settings',
};

export function migrateLegacyRoute(path: string): MigrationResult {
  const mapped = LEGACY_ROUTE_MAP[path];
  if (!mapped) {
    return { newPath: path, showMigrationToast: false };
  }
  return {
    newPath: mapped,
    migratedFrom: path,
    showMigrationToast: true,
  };
}
