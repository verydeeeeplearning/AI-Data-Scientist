"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TELEGRAM_BOT_OWNERSHIP_CHOICES = exports.TELEGRAM_QUICK_POLICY_CHOICES = void 0;
exports.createTelegramConnectFlowState = createTelegramConnectFlowState;
exports.normalizeTelegramBotToken = normalizeTelegramBotToken;
exports.validateTelegramBotToken = validateTelegramBotToken;
exports.chooseTelegramBotOwnership = chooseTelegramBotOwnership;
exports.updateTelegramTokenEntry = updateTelegramTokenEntry;
exports.touchTelegramTokenEntry = touchTelegramTokenEntry;
exports.canStartTelegramPairing = canStartTelegramPairing;
exports.resolveTelegramTokenFailureKey = resolveTelegramTokenFailureKey;
exports.markTelegramPairingStarted = markTelegramPairingStarted;
exports.applyTelegramPairingStatus = applyTelegramPairingStatus;
exports.applyTelegramPairedEvent = applyTelegramPairedEvent;
exports.markTelegramTokenPersisted = markTelegramTokenPersisted;
exports.chooseTelegramQuickPolicy = chooseTelegramQuickPolicy;
exports.finishTelegramConnectFlow = finishTelegramConnectFlow;
exports.cancelTelegramConnectFlow = cancelTelegramConnectFlow;
exports.resetTelegramConnectFlow = resetTelegramConnectFlow;
exports.getTelegramPairingSecondsRemaining = getTelegramPairingSecondsRemaining;
exports.buildTelegramStartCommand = buildTelegramStartCommand;
exports.buildTelegramBotDeepLink = buildTelegramBotDeepLink;
exports.TELEGRAM_QUICK_POLICY_CHOICES = [
    'critical',
    'digest',
    'all',
];
exports.TELEGRAM_BOT_OWNERSHIP_CHOICES = [
    'create',
    'existing',
];
const TELEGRAM_TOKEN_PATTERN = /^\d{6,}:[A-Za-z0-9_-]{20,}$/;
function nowMs() {
    return Date.now();
}
function createTelegramConnectFlowState(timestampMs = nowMs()) {
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
function normalizeTelegramBotToken(token) {
    return token.trim();
}
function validateTelegramBotToken(token) {
    const normalized = normalizeTelegramBotToken(token);
    if (!normalized) {
        return 'required';
    }
    return TELEGRAM_TOKEN_PATTERN.test(normalized) ? null : 'format';
}
function chooseTelegramBotOwnership(state, ownershipChoice, timestampMs = nowMs()) {
    return {
        ...state,
        ownershipChoice,
        substep: 'token',
        cancelled: false,
        updatedAtMs: timestampMs,
    };
}
function updateTelegramTokenEntry(state, token, timestampMs = nowMs()) {
    const tokenError = state.tokenTouched ? validateTelegramBotToken(token) : null;
    return {
        ...state,
        token,
        tokenError,
        updatedAtMs: timestampMs,
    };
}
function touchTelegramTokenEntry(state, timestampMs = nowMs()) {
    return {
        ...state,
        tokenTouched: true,
        tokenError: validateTelegramBotToken(state.token),
        updatedAtMs: timestampMs,
    };
}
function canStartTelegramPairing(state) {
    return validateTelegramBotToken(state.token) === null;
}
function resolveTelegramTokenFailureKey(reason) {
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
function markTelegramPairingStarted(state, handle, timestampMs = nowMs()) {
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
function applyTelegramPairingStatus(state, pairingStatus, timestampMs = nowMs()) {
    const normalizedStatus = pairingStatus === 'unknown' ? 'pending' : pairingStatus;
    return {
        ...state,
        substep: normalizedStatus === 'paired'
            ? 'policy'
            : normalizedStatus === 'cancelled'
                ? 'cancelled'
                : state.substep,
        pairingStatus: normalizedStatus,
        persistTokenRequested: normalizedStatus === 'paired' ? true : state.persistTokenRequested,
        cancelled: normalizedStatus === 'cancelled' ? true : state.cancelled,
        updatedAtMs: timestampMs,
    };
}
function applyTelegramPairedEvent(state, event, timestampMs = nowMs()) {
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
function markTelegramTokenPersisted(state, timestampMs = nowMs()) {
    return {
        ...state,
        tokenPersisted: true,
        persistTokenRequested: false,
        updatedAtMs: timestampMs,
    };
}
function chooseTelegramQuickPolicy(state, quickPolicy, timestampMs = nowMs()) {
    return {
        ...state,
        quickPolicy,
        updatedAtMs: timestampMs,
    };
}
function finishTelegramConnectFlow(state, timestampMs = nowMs()) {
    return {
        ...state,
        substep: 'complete',
        updatedAtMs: timestampMs,
    };
}
function cancelTelegramConnectFlow(state, timestampMs = nowMs()) {
    return {
        ...state,
        substep: 'cancelled',
        pairingStatus: state.pairingStatus === 'paired' ? 'paired' : 'cancelled',
        cancelled: true,
        updatedAtMs: timestampMs,
    };
}
function resetTelegramConnectFlow(timestampMs = nowMs()) {
    return createTelegramConnectFlowState(timestampMs);
}
function getTelegramPairingSecondsRemaining(state, timestampMs = nowMs()) {
    if (!state.pairingExpiresAtMs) {
        return null;
    }
    return Math.max(0, Math.ceil((state.pairingExpiresAtMs - timestampMs) / 1000));
}
function buildTelegramStartCommand(code) {
    const normalizedCode = code?.trim() ?? '';
    return normalizedCode ? `/pair ${normalizedCode}` : '/pair';
}
function buildTelegramBotDeepLink(username, code) {
    const normalizedUsername = username?.trim().replace(/^@/, '') ?? '';
    const normalizedCode = code?.trim() ?? '';
    if (!normalizedUsername || !normalizedCode) {
        return null;
    }
    return `https://t.me/${encodeURIComponent(normalizedUsername)}`;
}
