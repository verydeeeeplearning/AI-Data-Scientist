import { translateKey } from '../stores/i18nStore';

type Interpolations = Record<string, string | number | undefined | null>;

const DEFAULT_ERROR_KEY_BY_CODE: Record<string, string> = {
  backend_offline: 'common.mainIpc.backendOffline',
  backend_restart_failed: 'common.mainIpc.backendRestartFailed',
};

function extractErrorCode(value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.errorCode === 'string' && record.errorCode.trim()) {
    return record.errorCode.trim();
  }
  if (typeof record.reason === 'string' && record.reason.trim()) {
    return record.reason.trim();
  }
  return null;
}

export function resolveMainIpcErrorMessage(
  payload: unknown,
  fallbackKey: string,
  vars?: Interpolations,
  errorKeyByCode?: Record<string, string>,
): string {
  const errorCode = extractErrorCode(payload);
  const key = errorCode
    ? errorKeyByCode?.[errorCode] ?? DEFAULT_ERROR_KEY_BY_CODE[errorCode] ?? fallbackKey
    : fallbackKey;
  return translateKey(key, vars);
}
