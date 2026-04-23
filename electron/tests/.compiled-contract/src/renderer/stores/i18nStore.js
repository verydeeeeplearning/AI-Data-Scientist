"use strict";
/**
 * i18n store — Wave 1-A Phase D shim that delegates to i18next.
 *
 * Existing call sites use `useI18n().t('namespace.key', vars)` plus
 * `setLocale(locale)` and `useI18n().locale`. This module preserves that
 * API while translation lookups, missing-key fallbacks, and resource
 * loading flow through i18next (see `../i18n.ts`).
 *
 * Namespace inference rule: if the first dot-segment of `key` matches a
 * registered namespace, that namespace is used; otherwise `common` is used.
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = exports.LOCALE_OPTIONS = exports.LOCALE_STORAGE_KEY = void 0;
exports.isSupportedLocale = isSupportedLocale;
exports.normalizeLocale = normalizeLocale;
exports.getLocaleOption = getLocaleOption;
exports.useI18n = useI18n;
exports.setLocale = setLocale;
exports.getCurrentLocale = getCurrentLocale;
exports.translateKey = translateKey;
const react_1 = require("react");
const i18n_1 = __importStar(require("../i18n"));
exports.LOCALE_STORAGE_KEY = i18n_1.I18N_LANGUAGE_KEY;
exports.LOCALE_OPTIONS = [
    { code: 'ko', nativeLabel: '한국어', englishLabel: 'Korean', bcp47: 'ko-KR' },
    { code: 'en', nativeLabel: 'English', englishLabel: 'English', bcp47: 'en-US' },
    { code: 'ja', nativeLabel: '日本語', englishLabel: 'Japanese', bcp47: 'ja-JP' },
];
const SUPPORTED_LOCALES = new Set(exports.LOCALE_OPTIONS.map((option) => option.code));
const NAMESPACE_SET = new Set(i18n_1.I18N_NAMESPACES);
function isSupportedLocale(value) {
    return typeof value === 'string' && SUPPORTED_LOCALES.has(value);
}
function normalizeLocale(value) {
    if (!value)
        return null;
    const normalized = value.toLowerCase();
    const base = normalized.split(/[-_]/, 1)[0];
    return isSupportedLocale(base) ? base : null;
}
function getLocaleOption(locale) {
    return exports.LOCALE_OPTIONS.find((option) => option.code === locale) ?? exports.LOCALE_OPTIONS[1];
}
function resolveNamespaceAndKey(rawKey) {
    const colonIdx = rawKey.indexOf(':');
    if (colonIdx > 0) {
        const ns = rawKey.slice(0, colonIdx);
        const key = rawKey.slice(colonIdx + 1);
        return { ns, key };
    }
    const dotIdx = rawKey.indexOf('.');
    if (dotIdx > 0) {
        const candidate = rawKey.slice(0, dotIdx);
        if (NAMESPACE_SET.has(candidate)) {
            return { ns: candidate, key: rawKey.slice(dotIdx + 1) };
        }
    }
    return { ns: 'common', key: rawKey };
}
function translate(key, vars) {
    const { ns, key: lookup } = resolveNamespaceAndKey(key);
    const result = i18n_1.default.t(lookup, {
        ns,
        defaultValue: key,
        replace: vars ?? undefined,
    });
    return typeof result === 'string' ? result : key;
}
function currentLocale() {
    const lng = i18n_1.default.resolvedLanguage ?? i18n_1.default.language ?? 'en';
    return (isSupportedLocale(lng) ? lng : 'en');
}
const listeners = new Set();
function emitChange() {
    for (const listener of listeners) {
        listener();
    }
}
i18n_1.default.on('languageChanged', emitChange);
i18n_1.default.on('initialized', emitChange);
function subscribe(listener) {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}
function getSnapshot() {
    return currentLocale();
}
function buildResult(locale) {
    return {
        locale,
        locales: exports.LOCALE_OPTIONS,
        setLocale,
        t: translate,
    };
}
function useI18n(selector) {
    const locale = (0, react_1.useSyncExternalStore)(subscribe, getSnapshot, getSnapshot);
    (0, react_1.useEffect)(() => {
        if (typeof document !== 'undefined') {
            document.documentElement.lang = getLocaleOption(locale).bcp47;
            document.documentElement.dataset.locale = locale;
        }
    }, [locale]);
    const state = buildResult(locale);
    return selector ? selector(state) : state;
}
function setLocale(locale) {
    if (!isSupportedLocale(locale))
        return;
    if (i18n_1.default.language === locale && i18n_1.default.resolvedLanguage === locale) {
        emitChange();
        return;
    }
    void i18n_1.default.changeLanguage(locale);
}
function getCurrentLocale() {
    return currentLocale();
}
function translateKey(key, vars) {
    return translate(key, vars);
}
exports.__test = {
    resolveNamespaceAndKey,
    translate,
    currentLocale,
    SUPPORTED_LNGS: i18n_1.SUPPORTED_LNGS,
};
