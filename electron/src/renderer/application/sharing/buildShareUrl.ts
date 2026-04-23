export type ShareableResourceType = 'run' | 'artifact' | 'session' | 'mission';

const RESOURCE_PATH_SEGMENT: Record<ShareableResourceType, string> = {
  run: 'runs',
  artifact: 'artifacts',
  session: 'sessions',
  mission: 'missions',
};

export interface BuildShareUrlInput {
  readonly resourceType: ShareableResourceType;
  readonly resourceId: string;
  readonly baseUrl?: string;
}

export interface ShareUrlResult {
  readonly resourceType: ShareableResourceType;
  readonly resourceId: string;
  readonly url: string;
}

export function buildShareUrl(input: BuildShareUrlInput): ShareUrlResult {
  const trimmed = input.resourceId.trim();
  if (trimmed.length === 0) {
    throw new Error('buildShareUrl: resourceId is required');
  }
  const segment = RESOURCE_PATH_SEGMENT[input.resourceType];
  const path = `/${segment}/${encodeURIComponent(trimmed)}`;
  const url = input.baseUrl ? `${input.baseUrl.replace(/\/+$/, '')}${path}` : path;
  return {
    resourceType: input.resourceType,
    resourceId: trimmed,
    url,
  };
}
