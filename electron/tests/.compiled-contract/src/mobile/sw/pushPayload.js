"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizePushNotification = normalizePushNotification;
exports.resolveNotificationClickTarget = resolveNotificationClickTarget;
function pickString(record, key) {
    const value = record[key];
    return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}
function normalizePushNotification(raw) {
    if (!raw || typeof raw !== 'object') {
        return {
            title: 'DS Agent',
            body: '',
            deepLink: null,
            tag: 'ds-agent-notification',
        };
    }
    const record = raw;
    const data = record.data && typeof record.data === 'object'
        ? record.data
        : {};
    const category = pickString(data, 'category') ?? 'notification';
    return {
        title: pickString(record, 'title') ?? 'DS Agent',
        body: pickString(record, 'body') ?? '',
        deepLink: pickString(data, 'deepLink'),
        tag: `ds-agent-${category}`,
    };
}
function resolveNotificationClickTarget(data, fallback = './') {
    if (data && typeof data === 'object') {
        const deepLink = pickString(data, 'deepLink');
        if (deepLink) {
            return deepLink;
        }
    }
    return fallback;
}
