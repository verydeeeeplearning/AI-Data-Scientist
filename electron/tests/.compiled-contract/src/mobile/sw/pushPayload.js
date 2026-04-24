"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizePushNotification = normalizePushNotification;
exports.resolveNotificationClickTarget = resolveNotificationClickTarget;
const mobile_json_1 = __importDefault(require("../../../public/locales/en/mobile.json"));
const mobile_json_2 = __importDefault(require("../../../public/locales/ja/mobile.json"));
const mobile_json_3 = __importDefault(require("../../../public/locales/ko/mobile.json"));
const MOBILE_NOTIFICATION_MESSAGES = {
    en: mobile_json_1.default,
    ja: mobile_json_2.default,
    ko: mobile_json_3.default,
};
function pickString(record, key) {
    const value = record[key];
    return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}
function resolveNotificationLocale() {
    if (typeof navigator === 'undefined') {
        return 'en';
    }
    const language = (navigator.language ?? navigator.languages?.[0] ?? 'en').toLowerCase();
    if (language.startsWith('ko')) {
        return 'ko';
    }
    if (language.startsWith('ja')) {
        return 'ja';
    }
    return 'en';
}
function readNotificationCopy(key, locale, fallbackKey) {
    return (MOBILE_NOTIFICATION_MESSAGES[locale][key]
        ?? MOBILE_NOTIFICATION_MESSAGES.en[key]
        ?? MOBILE_NOTIFICATION_MESSAGES[locale][fallbackKey]
        ?? MOBILE_NOTIFICATION_MESSAGES.en[fallbackKey]
        ?? '');
}
function notificationFallbackKeys(category) {
    if (category === 'approval') {
        return {
            title: 'mobile.push.notification.approval.title',
            body: 'mobile.push.notification.approval.body',
        };
    }
    if (category === 'error') {
        return {
            title: 'mobile.push.notification.error.title',
            body: 'mobile.push.notification.error.body',
        };
    }
    return {
        title: 'mobile.push.notification.default.title',
        body: 'mobile.push.notification.default.body',
    };
}
function normalizePushNotification(raw) {
    const locale = resolveNotificationLocale();
    const defaultKeys = notificationFallbackKeys('notification');
    if (!raw || typeof raw !== 'object') {
        return {
            title: readNotificationCopy(defaultKeys.title, locale, defaultKeys.title),
            body: readNotificationCopy(defaultKeys.body, locale, defaultKeys.body),
            deepLink: null,
            tag: 'ds-agent-notification',
        };
    }
    const record = raw;
    const hasStructuredData = Boolean(record.data && typeof record.data === 'object');
    const data = hasStructuredData
        ? record.data
        : {};
    const category = pickString(data, 'category') ?? 'notification';
    const fallbackKeys = notificationFallbackKeys(category);
    const titleKey = pickString(data, 'titleKey');
    const bodyKey = pickString(data, 'bodyKey');
    const rawTitle = hasStructuredData && category !== 'error' ? pickString(record, 'title') : null;
    const rawBody = hasStructuredData && category !== 'error' ? pickString(record, 'body') : null;
    return {
        title: titleKey
            ? readNotificationCopy(titleKey, locale, fallbackKeys.title)
            : rawTitle ?? readNotificationCopy(fallbackKeys.title, locale, fallbackKeys.title),
        body: bodyKey
            ? readNotificationCopy(bodyKey, locale, fallbackKeys.body)
            : rawBody ?? readNotificationCopy(fallbackKeys.body, locale, fallbackKeys.body),
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
