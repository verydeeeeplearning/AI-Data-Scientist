"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveMainIpcErrorMessage = resolveMainIpcErrorMessage;
const i18nStore_1 = require("../stores/i18nStore");
const DEFAULT_ERROR_KEY_BY_CODE = {
    backend_offline: 'common.mainIpc.backendOffline',
    backend_restart_failed: 'common.mainIpc.backendRestartFailed',
};
function extractErrorCode(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return null;
    }
    const record = value;
    if (typeof record.errorCode === 'string' && record.errorCode.trim()) {
        return record.errorCode.trim();
    }
    if (typeof record.reason === 'string' && record.reason.trim()) {
        return record.reason.trim();
    }
    return null;
}
function resolveMainIpcErrorMessage(payload, fallbackKey, vars, errorKeyByCode) {
    const errorCode = extractErrorCode(payload);
    const key = errorCode
        ? errorKeyByCode?.[errorCode] ?? DEFAULT_ERROR_KEY_BY_CODE[errorCode] ?? fallbackKey
        : fallbackKey;
    return (0, i18nStore_1.translateKey)(key, vars);
}
