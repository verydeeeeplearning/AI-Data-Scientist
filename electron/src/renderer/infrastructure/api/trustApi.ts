import { mapTrustPayload } from '../../application/trust/trustMapper';
import type { TrustMetadata } from '../../application/trust/trustTypes';

function getBackendBaseUrl(): string {
  const params = new URLSearchParams(window.location.search);
  const rawPort = params.get('port');
  const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
  return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

export async function fetchTrustByResultId(resultId: string): Promise<TrustMetadata> {
  const encodedResultId = encodeURIComponent(resultId);
  const response = await fetch(`${getBackendBaseUrl()}/api/trust/${encodedResultId}`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }

    throw new Error(
      extractErrorMessage(payload, `Trust request failed with status ${response.status}`),
    );
  }

  const payload = await response.json();
  return mapTrustPayload(resultId, payload);
}
