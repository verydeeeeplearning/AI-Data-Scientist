import {
  parseDeepLink,
  type DeepLink,
  type DeepLinkParseError,
  type DeepLinkParseResult,
} from '../../domain/deepLink/deepLink';

export type DeepLinkReauthPolicy = 'none' | 'once-per-session' | 'always';

export interface DeepLinkHandlerDeps {
  readonly parseUri: (rawUri: string) => DeepLinkParseResult;
  readonly navigate: (path: string) => void;
  readonly warnInvalid: (error: DeepLinkParseError, uri: string) => void;
  readonly getReauthPolicy: () => DeepLinkReauthPolicy;
  readonly requestReauth: () => Promise<boolean>;
  readonly hasReauthedThisSession: () => boolean;
  readonly markSessionReauthed: () => void;
}

export function buildDeepLinkRoute(link: DeepLink): string {
  const base = `/workspace/${link.workspaceId}/${link.resourceType}/${link.resourceId}`;
  return link.action ? `${base}?action=${link.action}` : base;
}

export async function handleDeepLink(
  rawUri: string,
  deps: DeepLinkHandlerDeps,
): Promise<void> {
  const result = deps.parseUri(rawUri);
  if (!result.ok) {
    deps.warnInvalid(result.error, rawUri);
    return;
  }

  const policy = deps.getReauthPolicy();
  if (policy === 'always' || (policy === 'once-per-session' && !deps.hasReauthedThisSession())) {
    const granted = await deps.requestReauth();
    if (!granted) {
      return;
    }
    if (policy === 'once-per-session') {
      deps.markSessionReauthed();
    }
  }

  deps.navigate(buildDeepLinkRoute(result.value));
}

export const __test__ = { parseDeepLink };
