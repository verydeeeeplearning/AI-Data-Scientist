export type ViewerRole = 'owner' | 'viewer';

interface UseAccessRoleOptions {
  readonly forceRole?: ViewerRole;
}

export interface AccessRoleResult {
  readonly role: ViewerRole;
  readonly isOwner: boolean;
  readonly isViewer: boolean;
}

const SOLE_USER_MODE = true;

export function resolveAccessRole(
  forceRole: ViewerRole | undefined,
  soleUserMode: boolean,
): ViewerRole {
  if (forceRole !== undefined) {
    return forceRole;
  }
  if (soleUserMode) {
    return 'owner';
  }
  return 'owner';
}

export function useAccessRole(options: UseAccessRoleOptions = {}): AccessRoleResult {
  const role = resolveAccessRole(options.forceRole, SOLE_USER_MODE);
  return {
    role,
    isOwner: role === 'owner',
    isViewer: role === 'viewer',
  };
}
