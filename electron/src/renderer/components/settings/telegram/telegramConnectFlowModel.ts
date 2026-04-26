export type TelegramConnectSubstep =
  | 'ownership'
  | 'token'
  | 'pairing'
  | 'policy'
  | 'complete'
  | 'cancelled';

export type TelegramBotOwnershipChoice = 'create' | 'existing';

export type TelegramQuickPolicyChoice = 'critical' | 'digest' | 'all';

export type TelegramPairingStatus =
  | 'pending'
  | 'paired'
  | 'expired'
  | 'cancelled'
  | 'unknown';

export interface TelegramPairingHandleLike {
  readonly handleId: string;
  readonly code: string;
  readonly state: TelegramPairingStatus;
  readonly expiresAtMs: number | null;
  readonly botIdentity?: {
    readonly username: string | null;
  } | null;
}

export interface TelegramPairedEventLike {
  readonly handleId?: string | null;
  readonly chatId?: string | null;
  readonly persistToken?: boolean;
}

export interface TelegramConnectFlowState {
  readonly substep: TelegramConnectSubstep;
  readonly ownershipChoice: TelegramBotOwnershipChoice | null;
  readonly token: string;
  readonly tokenTouched: boolean;
  readonly tokenError: 'required' | 'format' | null;
  readonly handleId: string | null;
  readonly pairingCode: string | null;
  readonly pairingStatus: TelegramPairingStatus | null;
  readonly pairingExpiresAtMs: number | null;
  readonly botUsername: string | null;
  readonly pairedChatId: string | null;
  readonly persistTokenRequested: boolean;
  readonly tokenPersisted: boolean;
  readonly quickPolicy: TelegramQuickPolicyChoice;
  readonly cancelled: boolean;
  readonly updatedAtMs: number;
}

export const TELEGRAM_QUICK_POLICY_CHOICES: readonly TelegramQuickPolicyChoice[] = [
  'critical',
  'digest',
  'all',
] as const;

export const TELEGRAM_BOT_OWNERSHIP_CHOICES: readonly TelegramBotOwnershipChoice[] = [
  'create',
  'existing',
] as const;

const TELEGRAM_TOKEN_PATTERN = /^\d{6,}:[A-Za-z0-9_-]{20,}$/;

function nowMs(): number {
  return Date.now();
}

export function createTelegramConnectFlowState(
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    substep: 'ownership',
    ownershipChoice: null,
    token: '',
    tokenTouched: false,
    tokenError: null,
    handleId: null,
    pairingCode: null,
    pairingStatus: null,
    pairingExpiresAtMs: null,
    botUsername: null,
    pairedChatId: null,
    persistTokenRequested: false,
    tokenPersisted: false,
    quickPolicy: 'critical',
    cancelled: false,
    updatedAtMs: timestampMs,
  };
}

export function normalizeTelegramBotToken(token: string): string {
  return token.trim();
}

export function validateTelegramBotToken(
  token: string,
): TelegramConnectFlowState['tokenError'] {
  const normalized = normalizeTelegramBotToken(token);
  if (!normalized) {
    return 'required';
  }
  return TELEGRAM_TOKEN_PATTERN.test(normalized) ? null : 'format';
}

export function chooseTelegramBotOwnership(
  state: TelegramConnectFlowState,
  ownershipChoice: TelegramBotOwnershipChoice,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    ownershipChoice,
    substep: 'token',
    cancelled: false,
    updatedAtMs: timestampMs,
  };
}

export function updateTelegramTokenEntry(
  state: TelegramConnectFlowState,
  token: string,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  const tokenError = state.tokenTouched ? validateTelegramBotToken(token) : null;
  return {
    ...state,
    token,
    tokenError,
    updatedAtMs: timestampMs,
  };
}

export function touchTelegramTokenEntry(
  state: TelegramConnectFlowState,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    tokenTouched: true,
    tokenError: validateTelegramBotToken(state.token),
    updatedAtMs: timestampMs,
  };
}

export function canStartTelegramPairing(state: TelegramConnectFlowState): boolean {
  return validateTelegramBotToken(state.token) === null;
}

export function resolveTelegramTokenFailureKey(reason: string): string {
  switch (reason) {
    case 'invalid_format':
      return 'settings.telegramConnect.token.errorFormat';
    case 'unauthorized':
      return 'settings.telegramConnect.token.rejected';
    case 'bot_disabled':
      return 'settings.telegramConnect.token.botDisabled';
    case 'network_error':
    case 'timeout':
      return 'settings.telegramConnect.token.networkError';
    case 'api_error':
    case 'unknown':
    default:
      return 'settings.telegramConnect.token.unknownError';
  }
}

export function markTelegramPairingStarted(
  state: TelegramConnectFlowState,
  handle: TelegramPairingHandleLike,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    substep: handle.state === 'paired' ? 'policy' : 'pairing',
    token: normalizeTelegramBotToken(state.token),
    tokenTouched: true,
    tokenError: null,
    handleId: handle.handleId,
    pairingCode: handle.code,
    pairingStatus: handle.state === 'unknown' ? 'pending' : handle.state,
    pairingExpiresAtMs: handle.expiresAtMs,
    botUsername: handle.botIdentity?.username ?? state.botUsername,
    persistTokenRequested: handle.state === 'paired' ? true : state.persistTokenRequested,
    cancelled: false,
    updatedAtMs: timestampMs,
  };
}

export function applyTelegramPairingStatus(
  state: TelegramConnectFlowState,
  pairingStatus: TelegramPairingStatus,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  const normalizedStatus = pairingStatus === 'unknown' ? 'pending' : pairingStatus;
  return {
    ...state,
    substep:
      normalizedStatus === 'paired'
        ? 'policy'
        : normalizedStatus === 'cancelled'
          ? 'cancelled'
          : state.substep,
    pairingStatus: normalizedStatus,
    persistTokenRequested:
      normalizedStatus === 'paired' ? true : state.persistTokenRequested,
    cancelled: normalizedStatus === 'cancelled' ? true : state.cancelled,
    updatedAtMs: timestampMs,
  };
}

export function applyTelegramPairedEvent(
  state: TelegramConnectFlowState,
  event: TelegramPairedEventLike,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  const eventHandleId = event.handleId?.trim() || null;
  if (eventHandleId && state.handleId && eventHandleId !== state.handleId) {
    return state;
  }

  return {
    ...state,
    substep: 'policy',
    pairingStatus: 'paired',
    pairedChatId: event.chatId?.trim() || state.pairedChatId,
    persistTokenRequested: event.persistToken ?? true,
    cancelled: false,
    updatedAtMs: timestampMs,
  };
}

export function markTelegramTokenPersisted(
  state: TelegramConnectFlowState,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    tokenPersisted: true,
    persistTokenRequested: false,
    updatedAtMs: timestampMs,
  };
}

export function chooseTelegramQuickPolicy(
  state: TelegramConnectFlowState,
  quickPolicy: TelegramQuickPolicyChoice,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    quickPolicy,
    updatedAtMs: timestampMs,
  };
}

export function finishTelegramConnectFlow(
  state: TelegramConnectFlowState,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    substep: 'complete',
    updatedAtMs: timestampMs,
  };
}

export function cancelTelegramConnectFlow(
  state: TelegramConnectFlowState,
  timestampMs = nowMs(),
): TelegramConnectFlowState {
  return {
    ...state,
    substep: 'cancelled',
    pairingStatus: state.pairingStatus === 'paired' ? 'paired' : 'cancelled',
    cancelled: true,
    updatedAtMs: timestampMs,
  };
}

export function resetTelegramConnectFlow(timestampMs = nowMs()): TelegramConnectFlowState {
  return createTelegramConnectFlowState(timestampMs);
}

export function getTelegramPairingSecondsRemaining(
  state: Pick<TelegramConnectFlowState, 'pairingExpiresAtMs'>,
  timestampMs = nowMs(),
): number | null {
  if (!state.pairingExpiresAtMs) {
    return null;
  }
  return Math.max(0, Math.ceil((state.pairingExpiresAtMs - timestampMs) / 1000));
}

export function buildTelegramStartCommand(code: string | null): string {
  const normalizedCode = code?.trim() ?? '';
  return normalizedCode ? `/pair ${normalizedCode}` : '/pair';
}

export function buildTelegramBotDeepLink(
  username: string | null,
  code: string | null,
): string | null {
  const normalizedUsername = username?.trim().replace(/^@/, '') ?? '';
  const normalizedCode = code?.trim() ?? '';
  if (!normalizedUsername || !normalizedCode) {
    return null;
  }
  return `https://t.me/${encodeURIComponent(normalizedUsername)}`;
}
