"use strict";
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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MOBILE_I18N_RESOURCES = exports.MOBILE_I18N_LANGUAGE_KEY = exports.MOBILE_I18N_NAMESPACES = exports.MOBILE_SUPPORTED_LNGS = void 0;
exports.resolveInitialMobileLocale = resolveInitialMobileLocale;
exports.applyMobileDocumentLocale = applyMobileDocumentLocale;
exports.initializeMobileI18n = initializeMobileI18n;
exports.createMobileI18nInstance = createMobileI18nInstance;
const i18next_1 = __importStar(require("i18next"));
const react_i18next_1 = require("react-i18next");
const meta_1 = require("../shared/i18n/meta");
const mobile_json_1 = __importDefault(require("../../public/locales/ko/mobile.json"));
const mobile_json_2 = __importDefault(require("../../public/locales/en/mobile.json"));
const mobile_json_3 = __importDefault(require("../../public/locales/ja/mobile.json"));
exports.MOBILE_SUPPORTED_LNGS = meta_1.SHARED_I18N_LOCALES;
exports.MOBILE_I18N_NAMESPACES = meta_1.MOBILE_I18N_NAMESPACES;
exports.MOBILE_I18N_LANGUAGE_KEY = 'i18nextLng';
exports.MOBILE_I18N_RESOURCES = {
    ko: {
        mobile: mobile_json_1.default,
    },
    en: {
        mobile: mobile_json_2.default,
    },
    ja: {
        mobile: mobile_json_3.default,
    },
};
const LOCALE_BCP47 = {
    ko: 'ko-KR',
    en: 'en-US',
    ja: 'ja-JP',
};
function normalizeMobileLocale(value) {
    if (typeof value !== 'string' || value.length === 0) {
        return null;
    }
    const normalized = value.toLowerCase().split(/[-_]/, 1)[0];
    return isMobileLocale(normalized) ? normalized : null;
}
function isMobileLocale(value) {
    return (typeof value === 'string' &&
        exports.MOBILE_SUPPORTED_LNGS.includes(value));
}
function getBrowserStorage() {
    if (typeof window === 'undefined') {
        return null;
    }
    try {
        return window.localStorage;
    }
    catch {
        return null;
    }
}
function getNavigatorLanguage() {
    if (typeof navigator === 'undefined') {
        return null;
    }
    return navigator.language ?? navigator.languages?.[0] ?? null;
}
function getDocumentTarget() {
    if (typeof document === 'undefined') {
        return null;
    }
    return document;
}
function resolveInitialMobileLocale(options = {}) {
    const saved = normalizeMobileLocale(options.storage?.getItem(exports.MOBILE_I18N_LANGUAGE_KEY) ?? null);
    if (saved) {
        return saved;
    }
    const browserLocale = normalizeMobileLocale(options.navigatorLanguage ?? getNavigatorLanguage());
    if (browserLocale) {
        return browserLocale;
    }
    return 'en';
}
function applyMobileDocumentLocale(locale, documentTarget = getDocumentTarget()) {
    if (!documentTarget) {
        return;
    }
    documentTarget.documentElement.lang = LOCALE_BCP47[locale];
    documentTarget.documentElement.dataset.locale = locale;
}
async function initializeMobileI18n(instance, options = {}) {
    const storage = options.storage ?? getBrowserStorage();
    const documentTarget = options.document ?? getDocumentTarget();
    const locale = resolveInitialMobileLocale({
        storage,
        navigatorLanguage: options.navigatorLanguage,
    });
    await instance.use(react_i18next_1.initReactI18next).init({
        resources: exports.MOBILE_I18N_RESOURCES,
        lng: locale,
        fallbackLng: 'en',
        supportedLngs: exports.MOBILE_SUPPORTED_LNGS,
        defaultNS: 'mobile',
        ns: exports.MOBILE_I18N_NAMESPACES,
        nsSeparator: ':',
        keySeparator: '.',
        interpolation: {
            escapeValue: false,
            prefix: '{',
            suffix: '}',
        },
        returnNull: false,
        initImmediate: false,
    });
    applyMobileDocumentLocale(locale, documentTarget);
    instance.on('languageChanged', (nextLanguage) => {
        if (!isMobileLocale(nextLanguage)) {
            return;
        }
        applyMobileDocumentLocale(nextLanguage, documentTarget);
        try {
            storage?.setItem(exports.MOBILE_I18N_LANGUAGE_KEY, nextLanguage);
        }
        catch {
            // Ignore storage failures in constrained webviews.
        }
    });
    return instance;
}
async function createMobileI18nInstance(options = {}) {
    const instance = (0, i18next_1.createInstance)();
    return initializeMobileI18n(instance, options);
}
void initializeMobileI18n(i18next_1.default);
exports.default = i18next_1.default;
