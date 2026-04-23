/**
 * Backend adapter for the workspace export wizard.
 *
 * Wraps `POST /api/export/file` with the same backend port discovery used by
 * the trust/mission/cards adapters.
 */

import type { AudienceView } from '../../domain/workspace/audienceView';

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

export async function exportWorkspaceFile(input: {
  path: string;
  format: string;
  audience: AudienceView;
}): Promise<Record<string, unknown>> {
  const response = await fetch(`${getBackendBaseUrl()}/api/export/file`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path: input.path,
      format: input.format,
      audience: input.audience,
    }),
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON bodies.
    }
    throw new Error(
      extractErrorMessage(payload, `Export request failed with status ${response.status}`),
    );
  }
  const payload = await response.json();
  return typeof payload === 'object' && payload !== null
    ? (payload as Record<string, unknown>)
    : {};
}
