export type MobileErrorCode =
  | 'approval_invalid_decision'
  | 'approval_missing_id'
  | 'approval_queue_unavailable'
  | 'approval_submit_failed'
  | 'approval_transport_unavailable'
  | 'outbox_id_required'
  | 'outbox_request_failed'
  | 'outbox_transaction_aborted'
  | 'outbox_transaction_failed'
  | 'outbox_unavailable'
  | 'push_backend_offline'
  | 'push_bridge_missing'
  | 'push_invalid_public_key'
  | 'push_metrics_invalid_request'
  | 'push_metrics_load_failed'
  | 'push_register_failed'
  | 'push_register_payload_invalid'
  | 'push_service_worker_missing'
  | 'push_subscription_invalid'
  | 'push_subject_invalid'
  | 'push_subject_load_failed'
  | 'push_subject_required'
  | 'push_subject_save_failed'
  | 'push_unregister_failed'
  | 'push_unregister_payload_invalid'
  | 'push_vapid_private_key_missing'
  | 'push_vapid_public_key_empty'
  | 'push_vapid_public_key_missing'
  | 'push_vapid_keys_missing'
  | 'unknown';

export interface MobileError extends Error {
  readonly code: MobileErrorCode;
  readonly debugDetail?: string;
}

const KNOWN_CODES: ReadonlySet<MobileErrorCode> = new Set([
  'approval_invalid_decision',
  'approval_missing_id',
  'approval_queue_unavailable',
  'approval_submit_failed',
  'approval_transport_unavailable',
  'outbox_id_required',
  'outbox_request_failed',
  'outbox_transaction_aborted',
  'outbox_transaction_failed',
  'outbox_unavailable',
  'push_backend_offline',
  'push_bridge_missing',
  'push_invalid_public_key',
  'push_metrics_invalid_request',
  'push_metrics_load_failed',
  'push_register_failed',
  'push_register_payload_invalid',
  'push_service_worker_missing',
  'push_subscription_invalid',
  'push_subject_invalid',
  'push_subject_load_failed',
  'push_subject_required',
  'push_subject_save_failed',
  'push_unregister_failed',
  'push_unregister_payload_invalid',
  'push_vapid_private_key_missing',
  'push_vapid_public_key_empty',
  'push_vapid_public_key_missing',
  'push_vapid_keys_missing',
  'unknown',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function normalizeText(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

export function createMobileError(
  code: MobileErrorCode,
  message: string,
  debugDetail?: string,
): MobileError {
  const error = new Error(message) as MobileError;
  error.name = 'MobileError';
  Object.defineProperty(error, 'code', {
    value: code,
    enumerable: true,
    configurable: true,
    writable: false,
  });
  if (debugDetail && debugDetail.trim().length > 0) {
    Object.defineProperty(error, 'debugDetail', {
      value: debugDetail,
      enumerable: true,
      configurable: true,
      writable: false,
    });
  }
  return error;
}

export function getMobileErrorCode(value: unknown): MobileErrorCode | null {
  if (isRecord(value)) {
    const code = normalizeText(value.code);
    if (code && KNOWN_CODES.has(code as MobileErrorCode)) {
      return code as MobileErrorCode;
    }
  }
  return null;
}

export function getMobileErrorDebugDetail(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return normalizeText(value);
  }
  if (value instanceof Error) {
    const mobileError = value as MobileError;
    return normalizeText(mobileError.debugDetail) ?? normalizeText(value.message);
  }
  if (isRecord(value)) {
    return (
      normalizeText(value.debugDetail)
      ?? normalizeText(value.error)
      ?? normalizeText(value.reason)
      ?? normalizeText(value.message)
    );
  }
  return undefined;
}

function lowerDetail(value: unknown): string {
  return (getMobileErrorDebugDetail(value) ?? '').toLowerCase();
}

export function resolvePushErrorCode(value: unknown): MobileErrorCode {
  const explicitCode = getMobileErrorCode(value);
  if (explicitCode) {
    return explicitCode;
  }

  const detail = lowerDetail(value);
  if (!detail) {
    return 'unknown';
  }

  if (
    detail.includes('backend_offline')
    || detail.includes('backend is not connected')
    || detail.includes('connect econnrefused')
    || detail.includes('failed to fetch')
    || detail.includes('public-key fetch failed')
    || detail.includes('subject fetch failed')
    || detail.includes('backend returned an empty response')
  ) {
    return 'push_backend_offline';
  }
  if (detail.includes('vapid_private_key_missing')) {
    return 'push_vapid_private_key_missing';
  }
  if (detail.includes('vapid_public_key_missing')) {
    return 'push_vapid_public_key_missing';
  }
  if (detail.includes('vapid_keys_missing')) {
    return 'push_vapid_keys_missing';
  }
  if (detail.includes('subject is required')) {
    return 'push_subject_required';
  }
  if (
    detail.includes('subject must start with mailto:')
    || detail.includes('subject must be a non-empty mailto:')
  ) {
    return 'push_subject_invalid';
  }
  if (
    detail.includes('endpoint, p256dhkey, and authkey are required')
    || detail.includes('endpoint, p256dh, and auth are required')
  ) {
    return 'push_register_payload_invalid';
  }
  if (detail.includes('endpoint is required')) {
    return 'push_unregister_payload_invalid';
  }
  if (detail.includes('failed to save subject')) {
    return 'push_subject_save_failed';
  }
  if (detail.includes('failed to register subscription')) {
    return 'push_register_failed';
  }
  if (detail.includes('failed to unregister subscription')) {
    return 'push_unregister_failed';
  }
  if (detail.includes('pushsubscription is missing p256dh or auth key')) {
    return 'push_subscription_invalid';
  }
  if (detail.includes('vapid public key is empty')) {
    return 'push_vapid_public_key_empty';
  }
  if (
    detail.includes('invalid character')
    || detail.includes("failed to execute 'atob'")
  ) {
    return 'push_invalid_public_key';
  }
  return 'unknown';
}

export function resolveApprovalErrorCode(value: unknown): MobileErrorCode {
  const explicitCode = getMobileErrorCode(value);
  if (explicitCode) {
    if (explicitCode.startsWith('outbox_')) {
      return 'approval_queue_unavailable';
    }
    return explicitCode;
  }

  const detail = lowerDetail(value);
  if (!detail) {
    return 'approval_submit_failed';
  }

  if (detail.includes('missing approvalid')) {
    return 'approval_missing_id';
  }
  if (detail.includes('invalid decision')) {
    return 'approval_invalid_decision';
  }
  if (
    detail.includes('indexeddb')
    || detail.includes('outbox')
    || detail.includes('transaction failed')
    || detail.includes('transaction aborted')
    || detail.includes('request failed')
    || detail.includes('id is required')
  ) {
    return 'approval_queue_unavailable';
  }
  if (
    detail.includes('offline')
    || detail.includes('network')
    || detail.includes('socket')
    || detail.includes('websocket')
    || detail.includes('disconnected')
    || detail.includes('failed to fetch')
    || detail.includes('backend is not connected')
    || detail.includes('rpc timeout')
  ) {
    return 'approval_transport_unavailable';
  }
  return 'approval_submit_failed';
}

export function getApprovalErrorKey(code: MobileErrorCode): string {
  switch (code) {
    case 'approval_missing_id':
      return 'mobile.approvals.error.reason.missingApprovalId';
    case 'approval_invalid_decision':
      return 'mobile.approvals.error.reason.invalidDecision';
    case 'approval_transport_unavailable':
      return 'mobile.approvals.error.reason.transportUnavailable';
    case 'approval_queue_unavailable':
      return 'mobile.approvals.error.reason.queueUnavailable';
    default:
      return 'mobile.approvals.error.reason.submitFailed';
  }
}

export function getPushErrorKey(code: MobileErrorCode): string {
  switch (code) {
    case 'push_bridge_missing':
      return 'mobile.push.error.bridgeMissing';
    case 'push_backend_offline':
      return 'mobile.push.error.backendOffline';
    case 'push_vapid_public_key_missing':
      return 'mobile.push.error.keyMissing';
    case 'push_vapid_private_key_missing':
    case 'push_vapid_keys_missing':
      return 'mobile.push.error.serverConfig';
    case 'push_vapid_public_key_empty':
    case 'push_invalid_public_key':
      return 'mobile.push.error.invalidKey';
    case 'push_service_worker_missing':
      return 'mobile.push.error.swMissing';
    case 'push_subscription_invalid':
      return 'mobile.push.error.subscriptionInvalid';
    case 'push_register_payload_invalid':
      return 'mobile.push.error.registerInvalid';
    case 'push_unregister_payload_invalid':
      return 'mobile.push.error.unregisterInvalid';
    case 'push_unregister_failed':
      return 'mobile.push.error.unregister';
    case 'push_register_failed':
      return 'mobile.push.error.register';
    default:
      return 'mobile.push.error.generic';
  }
}

export function getPushSubjectErrorKey(
  code: MobileErrorCode,
  phase: 'load' | 'save',
): string {
  switch (code) {
    case 'push_bridge_missing':
      return 'mobile.push.error.bridgeMissing';
    case 'push_backend_offline':
      return 'mobile.push.subject.error.backendOffline';
    case 'push_subject_required':
      return 'mobile.push.subject.error.required';
    case 'push_subject_invalid':
      return 'mobile.push.subject.error.format';
    default:
      return phase === 'load'
        ? 'mobile.push.subject.error.load'
        : 'mobile.push.subject.error.save';
  }
}

export function getPushMetricsErrorKey(code: MobileErrorCode): string {
  switch (code) {
    case 'push_backend_offline':
      return 'mobile.push.metrics.error.backendOffline';
    case 'push_metrics_invalid_request':
      return 'mobile.push.metrics.error.invalidRequest';
    default:
      return 'mobile.push.metrics.error';
  }
}
