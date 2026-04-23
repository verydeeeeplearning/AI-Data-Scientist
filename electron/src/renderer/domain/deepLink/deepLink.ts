// Cross-surface deep link contract (W4-C / PLAN_03).
//
// Wire format: ds-agent://workspace/<workspaceId>/<resourceType>/<resourceId>(?action=<action>)
//
// Parsing is pure, runs in renderer / Electron main / CLI / Telegram identically.
// External input MUST flow through `parseDeepLink` so traversal / scheme spoofing
// / oversized URIs are rejected before any side effect.

export const DEEP_LINK_SCHEME = 'ds-agent:';
export const DEEP_LINK_HOST = 'workspace';
export const DEEP_LINK_MAX_LENGTH = 2048;

export const DEEP_LINK_RESOURCE_TYPES = [
  'run',
  'artifact',
  'checkpoint',
  'verifier_result',
] as const;
export type DeepLinkResourceType = (typeof DEEP_LINK_RESOURCE_TYPES)[number];

export interface DeepLink {
  readonly workspaceId: string;
  readonly resourceType: DeepLinkResourceType;
  readonly resourceId: string;
  readonly action: string | null;
}

export type DeepLinkParseError =
  | 'too_long'
  | 'invalid_scheme'
  | 'invalid_host'
  | 'missing_workspace'
  | 'invalid_workspace'
  | 'unknown_resource_type'
  | 'missing_resource_id'
  | 'invalid_resource_id'
  | 'path_traversal'
  | 'invalid_action';

export interface DeepLinkParseFailure {
  readonly ok: false;
  readonly error: DeepLinkParseError;
}

export interface DeepLinkParseSuccess {
  readonly ok: true;
  readonly value: DeepLink;
}

export type DeepLinkParseResult = DeepLinkParseSuccess | DeepLinkParseFailure;

const ID_PATTERN = /^[A-Za-z0-9_:.-]{1,128}$/;
const ACTION_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

function isResourceType(value: string): value is DeepLinkResourceType {
  return (DEEP_LINK_RESOURCE_TYPES as readonly string[]).includes(value);
}

function containsTraversal(segment: string): boolean {
  return segment.includes('..') || segment.includes('//') || segment.includes('\\');
}

export function parseDeepLink(rawInput: string): DeepLinkParseResult {
  if (typeof rawInput !== 'string' || rawInput.length === 0) {
    return { ok: false, error: 'invalid_scheme' };
  }
  if (rawInput.length > DEEP_LINK_MAX_LENGTH) {
    return { ok: false, error: 'too_long' };
  }

  let url: URL;
  try {
    url = new URL(rawInput);
  } catch {
    return { ok: false, error: 'invalid_scheme' };
  }

  if (url.protocol !== DEEP_LINK_SCHEME) {
    return { ok: false, error: 'invalid_scheme' };
  }

  // For ds-agent://workspace/<id>/...  the host parses as 'workspace'.
  if (url.hostname !== DEEP_LINK_HOST) {
    return { ok: false, error: 'invalid_host' };
  }

  const segments = url.pathname.split('/').filter((segment) => segment.length > 0);
  if (segments.length === 0) {
    return { ok: false, error: 'missing_workspace' };
  }

  const workspaceId = decodeSegment(segments[0]);
  if (workspaceId === null || !ID_PATTERN.test(workspaceId)) {
    return { ok: false, error: 'invalid_workspace' };
  }

  if (segments.length < 2) {
    return { ok: false, error: 'unknown_resource_type' };
  }

  const resourceType = segments[1];
  if (!isResourceType(resourceType)) {
    return { ok: false, error: 'unknown_resource_type' };
  }

  if (segments.length < 3) {
    return { ok: false, error: 'missing_resource_id' };
  }
  // Reject extra path segments — they make path-traversal disguise easier.
  if (segments.length > 3) {
    return { ok: false, error: 'path_traversal' };
  }

  const rawResourceId = segments[2];
  if (containsTraversal(rawResourceId)) {
    return { ok: false, error: 'path_traversal' };
  }
  const resourceId = decodeSegment(rawResourceId);
  if (resourceId === null || !ID_PATTERN.test(resourceId)) {
    return { ok: false, error: 'invalid_resource_id' };
  }

  let action: string | null = null;
  const rawAction = url.searchParams.get('action');
  if (rawAction !== null) {
    if (!ACTION_PATTERN.test(rawAction)) {
      return { ok: false, error: 'invalid_action' };
    }
    action = rawAction;
  }

  return {
    ok: true,
    value: { workspaceId, resourceType, resourceId, action },
  };
}

function decodeSegment(segment: string): string | null {
  try {
    const decoded = decodeURIComponent(segment);
    return decoded.length > 0 ? decoded : null;
  } catch {
    return null;
  }
}

export function buildDeepLinkUri(link: DeepLink): string {
  const base = `${DEEP_LINK_SCHEME}//${DEEP_LINK_HOST}`
    + `/${encodeURIComponent(link.workspaceId)}`
    + `/${link.resourceType}`
    + `/${encodeURIComponent(link.resourceId)}`;
  if (link.action) {
    const params = new URLSearchParams({ action: link.action });
    return `${base}?${params.toString()}`;
  }
  return base;
}
