"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeTelegramRuntimeStatus = normalizeTelegramRuntimeStatus;
exports.normalizeTelegramPairingStatus = normalizeTelegramPairingStatus;
exports.normalizeTelegramStatus = normalizeTelegramStatus;
exports.normalizeTelegramTestResult = normalizeTelegramTestResult;
exports.normalizeTelegramPairingHandle = normalizeTelegramPairingHandle;
exports.normalizeTelegramPairingStatusSnapshot = normalizeTelegramPairingStatusSnapshot;
exports.testTelegramBot = testTelegramBot;
exports.startTelegramPairing = startTelegramPairing;
exports.getTelegramPairingStatus = getTelegramPairingStatus;
exports.cancelTelegramPairing = cancelTelegramPairing;
exports.getTelegramStatus = getTelegramStatus;
exports.sendTelegramTestMessage = sendTelegramTestMessage;
exports.disconnectTelegram = disconnectTelegram;
exports.reconnectTelegram = reconnectTelegram;
const TELEGRAM_RPC_TIMEOUT_MS = 15000;
function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function pickString(...values) {
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
function pickNumber(...values) {
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
function coerceBoolean(value, fallback = false) {
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
function normalizeEpochMs(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value > 0 && value < 1000000000000 ? Math.round(value * 1000) : Math.round(value);
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
function normalizeTelegramRuntimeStatus(value) {
    if (value === 'disabled'
        || value === 'starting'
        || value === 'running'
        || value === 'stopping'
        || value === 'error') {
        return value;
    }
    return 'unknown';
}
function normalizeTelegramPairingStatus(value) {
    if (value === 'pending'
        || value === 'paired'
        || value === 'expired'
        || value === 'cancelled') {
        return value;
    }
    return 'unknown';
}
function normalizeTelegramTestFailureReason(value) {
    if (value === 'invalid_format'
        || value === 'unauthorized'
        || value === 'network_error'
        || value === 'bot_disabled'
        || value === 'api_error') {
        return value;
    }
    return 'unknown';
}
function normalizeBotIdentity(payload) {
    if (!isRecord(payload)) {
        return null;
    }
    const username = pickString(payload.botUsername, payload.bot_username, payload.username);
    const botId = pickNumber(payload.botId, payload.bot_id, payload.id);
    const firstName = pickString(payload.firstName, payload.first_name, payload.name);
    if (username === null && botId === null && firstName === null) {
        return null;
    }
    return {
        username,
        botId,
        firstName,
    };
}
function normalizePairedChat(payload) {
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
function normalizeTelegramStatus(payload) {
    const raw = isRecord(payload) ? payload : {};
    const rawPaired = raw.paired ?? raw.pairedChats ?? raw.paired_chats ?? raw.chats;
    const pairedChats = Array.isArray(rawPaired)
        ? rawPaired
            .map((entry) => normalizePairedChat(entry))
            .filter((entry) => entry !== null)
        : [];
    const enabled = coerceBoolean(raw.enabled, pairedChats.length > 0 || normalizeTelegramRuntimeStatus(raw.status) === 'running');
    return {
        enabled,
        status: normalizeTelegramRuntimeStatus(raw.status),
        botIdentity: normalizeBotIdentity(raw),
        pairedChats,
        lastError: pickString(raw.lastError, raw.last_error, raw.error, raw.reason),
    };
}
function normalizeTelegramTestResult(payload) {
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
function normalizeTelegramPairingHandle(payload) {
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
function normalizeTelegramPairingStatusSnapshot(payload) {
    const raw = isRecord(payload) ? payload : {};
    return {
        state: normalizeTelegramPairingStatus(raw.state ?? raw.status),
    };
}
function ensureOk(payload, fallback) {
    const raw = isRecord(payload) ? payload : {};
    if (coerceBoolean(raw.ok ?? raw.success, false)) {
        return;
    }
    throw new Error(pickString(raw.message, raw.error, raw.reason) ?? fallback);
}
async function testTelegramBot(rpc, token) {
    const payload = await rpc('telegram.test', { token }, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    return normalizeTelegramTestResult(payload);
}
async function startTelegramPairing(rpc, token) {
    const payload = await rpc('telegram.startPairing', { token }, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    return normalizeTelegramPairingHandle(payload);
}
async function getTelegramPairingStatus(rpc, handleId) {
    const payload = await rpc('telegram.pairingStatus', { handleId }, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    return normalizeTelegramPairingStatusSnapshot(payload);
}
async function cancelTelegramPairing(rpc, handleId) {
    const payload = await rpc('telegram.cancelPairing', { handleId }, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    ensureOk(payload, 'Telegram pairing cancellation failed');
}
async function getTelegramStatus(rpc) {
    const payload = await rpc('telegram.status', undefined, {
        timeoutMs: TELEGRAM_RPC_TIMEOUT_MS,
    });
    return normalizeTelegramStatus(payload);
}
async function sendTelegramTestMessage(rpc, chatId) {
    const payload = await rpc('telegram.sendTestMessage', { chatId }, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    ensureOk(payload, 'Telegram test message failed');
}
async function disconnectTelegram(rpc, chatId) {
    const normalizedChatId = typeof chatId === 'string' ? chatId.trim() : '';
    const payload = await rpc('telegram.disconnect', normalizedChatId ? { chatId: normalizedChatId } : {}, { timeoutMs: TELEGRAM_RPC_TIMEOUT_MS });
    ensureOk(payload, 'Telegram disconnect failed');
}
async function reconnectTelegram(rpc) {
    const payload = await rpc('telegram.reconnect', undefined, {
        timeoutMs: TELEGRAM_RPC_TIMEOUT_MS,
    });
    ensureOk(payload, 'Telegram reconnect failed');
}
