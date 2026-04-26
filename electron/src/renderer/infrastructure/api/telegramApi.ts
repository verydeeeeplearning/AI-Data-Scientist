import type { RpcFn } from '../../components/settings/types';

export type TelegramRuntimeStatus =
  | 'disabled'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'error'
  | 'unknown';

export type TelegramPairingStatus =
  | 'pending'
  | 'paired'
  | 'expired'
  | 'cancelled'
  | 'unknown';

export type TelegramTestFailureReason =
  | 'invalid_format'
  | 'unauthorized'
  | 'network_error'
  | 'bot_disabled'
  | 'api_error'
  | 'unknown';

export interface TelegramBotIdentity {
  username: string | null;
  botId: number | null;
  firstName: string | null;
}

export interface TelegramPairedChat {
  chatId: string;
  firstActiveAtMs: number | null;
  lastActiveAtMs: number | null;
}

export interface TelegramStatusSnapshot {
  enabled: boolean;
  status: TelegramRuntimeStatus;
  botIdentity: TelegramBotIdentity | null;
  pairedChats: TelegramPairedChat[];
  lastError: string | null;
}

export type TelegramTestResult =
  | {
      ok: true;
      botIdentity: TelegramBotIdentity;
    }
  | {
      ok: false;
      reason: TelegramTestFailureReason;
    };

export interface TelegramPairingHandle {
  handleId: string;
  code: string;
  state: TelegramPairingStatus;
  expiresAtMs: number | null;
  botIdentity: TelegramBotIdentity | null;
}

export interface TelegramPairingStatusSnapshot {
  state: TelegramPairingStatus;
}

const TELEGRAM_RPC_TIMEOUT_MS = 15_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function pickString(...values: readonly unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== 'string') {
      continue;
    }
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      return trimmed;
    }
  }
  return null;
}

function pickNumber(...values: readonly unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value.trim());
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function coerceBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value !== 0;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (['1', 'true', 'yes', 'on'].includes(normalized)) {
      return true;
    }
    if (['0', 'false', 'no', 'off'].includes(normalized)) {
      return false;
    }
  }
  return fallback;
}

function normalizeEpochMs(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 0 && value < 1_000_000_000_000 ? Math.round(value * 1000) : Math.round(value);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsedNumber = Number(trimmed);
    if (Number.isFinite(parsedNumber)) {
      return normalizeEpochMs(parsedNumber);
    }
    const parsedDate = Date.parse(trimmed);
    return Number.isFinite(parsedDate) ? parsedDate : null;
  }
  return null;
}

export function normalizeTelegramRuntimeStatus(value: unknown): TelegramRuntimeStatus {
  if (
    value === 'disabled'
    || value === 'starting'
    || value === 'running'
    || value === 'stopping'
    || value === 'error'
  ) {
    return value;
  }
  return 'unknown';
}

export function normalizeTelegramPairingStatus(value: unknown): TelegramPairingStatus {
  if (
    value === 'pending'
    || value === 'paired'
    || value === 'expired'
    || value === 'cancelled'
  ) {
    return value;
  }
  return 'unknown';
}

function normalizeTelegramTestFailureReason(value: unknown): TelegramTestFailureReason {
  if (
    value === 'invalid_format'
    || value === 'unauthorized'
    || value === 'network_error'
    || value === 'bot_disabled'
    || value === 'api_error'
  ) {
    return value;
  }
  return 'unknown';
}

function normalizeBotIdentity(payload: unknown): TelegramBotIdentity | null {
  if (!isRecord(payload)) {
    return null;
  }

  const username = pickString(
    payload.botUsername,
    payload.bot_username,
    payload.username,
  );
  const botId = pickNumber(payload.botId, payload.bot_id, payload.id);
  const firstName = pickString(
    payload.firstName,
    payload.first_name,
    payload.name,
  );

  if (username === null && botId === null && firstName === null) {
    return null;
  }

  return {
    username,
    botId,
    firstName,
  };
}

function normalizePairedChat(payload: unknown): TelegramPairedChat | null {
  if (typeof payload === 'string' && payload.trim().length > 0) {
    return {
      chatId: payload.trim(),
      firstActiveAtMs: null,
      lastActiveAtMs: null,
    };
  }
  if (!isRecord(payload)) {
    return null;
  }

  const chatId = pickString(payload.chatId, payload.chat_id, payload.id);
  if (!chatId) {
    return null;
  }

  return {
    chatId,
    firstActiveAtMs: normalizeEpochMs(payload.firstActiveAt ?? payload.first_active_at),
    lastActiveAtMs: normalizeEpochMs(payload.lastActiveAt ?? payload.last_active_at),
  };
}

export function normalizeTelegramStatus(payload: unknown): TelegramStatusSnapshot {
  const raw = isRecord(payload) ? payload : {};
  const rawPaired = raw.paired ?? raw.pairedChats ?? raw.paired_chats ?? raw.chats;
  const pairedChats = Array.isArray(rawPaired)
    ? rawPaired
        .map((entry) => normalizePairedChat(entry))
        .filter((entry): entry is TelegramPairedChat => entry !== null)
    : [];
  const enabled = coerceBoolean(
    raw.enabled,
    pairedChats.length > 0 || normalizeTelegramRuntimeStatus(raw.status) === 'running',
  );

  return {
    enabled,
    status: normalizeTelegramRuntimeStatus(raw.status),
    botIdentity: normalizeBotIdentity(raw),
    pairedChats,
    lastError: pickString(raw.lastError, raw.last_error, raw.error, raw.reason),
  };
}

export function normalizeTelegramTestResult(payload: unknown): TelegramTestResult {
  const raw = isRecord(payload) ? payload : {};
  const ok = coerceBoolean(raw.ok ?? raw.success, false);
  const botIdentity = normalizeBotIdentity(raw);

  if (ok || botIdentity !== null) {
    return {
      ok: true,
      botIdentity: botIdentity ?? {
        username: null,
        botId: null,
        firstName: null,
      },
    };
  }

  return {
    ok: false,
    reason: normalizeTelegramTestFailureReason(raw.reason ?? raw.error),
  };
}

export function normalizeTelegramPairingHandle(payload: unknown): TelegramPairingHandle {
  if (!isRecord(payload)) {
    throw new Error('Telegram pairing response was not an object');
  }

  const handleId = pickString(payload.handleId, payload.handle_id, payload.id);
  const code = pickString(payload.code, payload.otp, payload.pairingCode, payload.pairing_code);
  if (!handleId || !code) {
    throw new Error('Telegram pairing response was missing handle or code');
  }

  return {
    handleId,
    code,
    state: normalizeTelegramPairingStatus(payload.state ?? 'pending'),
    expiresAtMs: normalizeEpochMs(payload.expiresAt ?? payload.expires_at ?? payload.expiresAtMs),
    botIdentity: normalizeBotIdentity(payload),
  };
}

export function normalizeTelegramPairingStatusSnapshot(
  payload: unknown,
): TelegramPairingStatusSnapshot {
  const raw = isRecord(payload) ? payload : {};
  return {
    state: normalizeTelegramPairingStatus(raw.state ?? raw.status),
  };
}

function ensureOk(payload: unknown, fallback: string): void {
  const raw = isRecord(payload) ? payload : {};
  if (coerceBoolean(raw.ok ?? raw.success, false)) {
    return;
  }
  throw new Error(pickString(raw.message, raw.error, raw.reason) ?? fallback);
}

export async function testTelegramBot(
  rpc: RpcFn,
  token: string,
): Promise<TelegramTestResult> {
  const payload = await rpc(
    'telegram.test',
    { token },
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  return normalizeTelegramTestResult(payload);
}

export async function startTelegramPairing(
  rpc: RpcFn,
  token: string,
): Promise<TelegramPairingHandle> {
  const payload = await rpc(
    'telegram.startPairing',
    { token },
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  return normalizeTelegramPairingHandle(payload);
}

export async function getTelegramPairingStatus(
  rpc: RpcFn,
  handleId: string,
): Promise<TelegramPairingStatusSnapshot> {
  const payload = await rpc(
    'telegram.pairingStatus',
    { handleId },
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  return normalizeTelegramPairingStatusSnapshot(payload);
}

export async function cancelTelegramPairing(
  rpc: RpcFn,
  handleId: string,
): Promise<void> {
  const payload = await rpc(
    'telegram.cancelPairing',
    { handleId },
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  ensureOk(payload, 'Telegram pairing cancellation failed');
}

export async function getTelegramStatus(rpc: RpcFn): Promise<TelegramStatusSnapshot> {
  const payload = await rpc('telegram.status', undefined, {
    timeoutMs: TELEGRAM_RPC_TIMEOUT_MS,
  });
  return normalizeTelegramStatus(payload);
}

export async function sendTelegramTestMessage(
  rpc: RpcFn,
  chatId: string,
): Promise<void> {
  const payload = await rpc(
    'telegram.sendTestMessage',
    { chatId },
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  ensureOk(payload, 'Telegram test message failed');
}

export async function disconnectTelegram(
  rpc: RpcFn,
  chatId?: string | null,
): Promise<void> {
  const normalizedChatId = typeof chatId === 'string' ? chatId.trim() : '';
  const payload = await rpc(
    'telegram.disconnect',
    normalizedChatId ? { chatId: normalizedChatId } : {},
    { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS },
  );
  ensureOk(payload, 'Telegram disconnect failed');
}

export async function reconnectTelegram(rpc: RpcFn): Promise<void> {
  const payload = await rpc('telegram.reconnect', undefined, {
    timeoutMs: TELEGRAM_RPC_TIMEOUT_MS,
  });
  ensureOk(payload, 'Telegram reconnect failed');
}
