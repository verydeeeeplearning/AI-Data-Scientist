/**
 * `prefers-reduced-motion` utility (WCAG 2.3.3 Animation from Interactions).
 *
 * Pure DOM API — no React or 3rd-party lib (ADR-0008). Components in
 * higher layers wrap these in hooks (e.g. `useReducedMotion`).
 */

const QUERY = '(prefers-reduced-motion: reduce)';

export interface MediaQueryProvider {
  matchMedia?: ((query: string) => MediaQueryList) | undefined;
}

interface ResolveOptions {
  provider?: MediaQueryProvider;
  emitInitial?: boolean;
}

function resolveProvider(options: ResolveOptions): MediaQueryProvider {
  if (options.provider) return options.provider;
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    return { matchMedia: window.matchMedia.bind(window) };
  }
  return { matchMedia: undefined };
}

export function prefersReducedMotion(options: ResolveOptions = {}): boolean {
  const provider = resolveProvider(options);
  if (!provider.matchMedia) return false;
  try {
    return provider.matchMedia(QUERY).matches;
  } catch {
    return false;
  }
}

export type ReducedMotionListener = (reduced: boolean) => void;

export function subscribeReducedMotion(
  listener: ReducedMotionListener,
  options: ResolveOptions = {},
): () => void {
  const provider = resolveProvider(options);
  if (!provider.matchMedia) {
    return () => {
      // no-op
    };
  }
  let mql: MediaQueryList;
  try {
    mql = provider.matchMedia(QUERY);
  } catch {
    return () => {
      // no-op
    };
  }
  if (options.emitInitial) {
    listener(mql.matches);
  }
  const handler = (event: { matches: boolean }) => listener(event.matches);
  mql.addEventListener('change', handler as (e: MediaQueryListEvent) => void);
  return () => {
    mql.removeEventListener('change', handler as (e: MediaQueryListEvent) => void);
  };
}
