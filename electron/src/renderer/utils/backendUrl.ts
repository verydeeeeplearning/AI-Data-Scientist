/**
 * Backend URL utilities — single source of truth for backend base URL.
 *
 * 4.14 fix: Eliminates hardcoded 'http://127.0.0.1:18790' in renderer components.
 * The actual port is passed from the main process as a URL query parameter.
 * Falls back to 18790 only when running in browser dev mode without a port param.
 */

function readBackendQueryParam(name: string): string | null {
  if (typeof window === 'undefined') return null;
  const searchValue = new URLSearchParams(window.location.search).get(name);
  if (searchValue) return searchValue;

  const hashQueryStart = window.location.hash.indexOf('?');
  if (hashQueryStart < 0) return null;
  return new URLSearchParams(window.location.hash.slice(hashQueryStart + 1)).get(name);
}

const INITIAL_BACKEND_QUERY_PARAMS: Record<string, string> = (() => {
  if (typeof window === 'undefined') return {};
  const params: Record<string, string> = {};
  for (const key of ['port', 'token']) {
    const value = readBackendQueryParam(key);
    if (value) {
      params[key] = value;
    }
  }
  return params;
})();

export function getBackendQueryParam(name: string): string | null {
  return readBackendQueryParam(name) ?? INITIAL_BACKEND_QUERY_PARAMS[name] ?? null;
}

export function getBackendPort(): number {
  if (typeof window === 'undefined') return 18790;
  const port = getBackendQueryParam('port');
  const parsed = port ? parseInt(port, 10) : 18790;
  return Number.isFinite(parsed) ? parsed : 18790;
}

/**
 * Returns the backend base URL including scheme, host, and port.
 * Example: 'http://127.0.0.1:18790'
 */
export function getBackendBase(): string {
  return `http://127.0.0.1:${getBackendPort()}`;
}
