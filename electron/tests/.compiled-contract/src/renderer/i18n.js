"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.I18N_RESOURCES = exports.LEGACY_LOCALE_KEY = exports.I18N_LANGUAGE_KEY = exports.I18N_NAMESPACES = exports.SUPPORTED_LNGS = void 0;
const i18next_1 = __importDefault(require("i18next"));
const react_i18next_1 = require("react-i18next");
const common_json_1 = __importDefault(require("../../public/locales/ko/common.json"));
const area_json_1 = __importDefault(require("../../public/locales/ko/area.json"));
const mission_json_1 = __importDefault(require("../../public/locales/ko/mission.json"));
const workspace_json_1 = __importDefault(require("../../public/locales/ko/workspace.json"));
const execution_json_1 = __importDefault(require("../../public/locales/ko/execution.json"));
const llm_json_1 = __importDefault(require("../../public/locales/ko/llm.json"));
const sidebar_json_1 = __importDefault(require("../../public/locales/ko/sidebar.json"));
const onboarding_json_1 = __importDefault(require("../../public/locales/ko/onboarding.json"));
const settings_json_1 = __importDefault(require("../../public/locales/ko/settings.json"));
const approval_json_1 = __importDefault(require("../../public/locales/ko/approval.json"));
const trust_json_1 = __importDefault(require("../../public/locales/ko/trust.json"));
const run_json_1 = __importDefault(require("../../public/locales/ko/run.json"));
const cards_json_1 = __importDefault(require("../../public/locales/ko/cards.json"));
const chat_json_1 = __importDefault(require("../../public/locales/ko/chat.json"));
const cmd_json_1 = __importDefault(require("../../public/locales/ko/cmd.json"));
const share_json_1 = __importDefault(require("../../public/locales/ko/share.json"));
const common_json_2 = __importDefault(require("../../public/locales/en/common.json"));
const area_json_2 = __importDefault(require("../../public/locales/en/area.json"));
const mission_json_2 = __importDefault(require("../../public/locales/en/mission.json"));
const workspace_json_2 = __importDefault(require("../../public/locales/en/workspace.json"));
const execution_json_2 = __importDefault(require("../../public/locales/en/execution.json"));
const llm_json_2 = __importDefault(require("../../public/locales/en/llm.json"));
const sidebar_json_2 = __importDefault(require("../../public/locales/en/sidebar.json"));
const onboarding_json_2 = __importDefault(require("../../public/locales/en/onboarding.json"));
const settings_json_2 = __importDefault(require("../../public/locales/en/settings.json"));
const approval_json_2 = __importDefault(require("../../public/locales/en/approval.json"));
const trust_json_2 = __importDefault(require("../../public/locales/en/trust.json"));
const run_json_2 = __importDefault(require("../../public/locales/en/run.json"));
const cards_json_2 = __importDefault(require("../../public/locales/en/cards.json"));
const chat_json_2 = __importDefault(require("../../public/locales/en/chat.json"));
const cmd_json_2 = __importDefault(require("../../public/locales/en/cmd.json"));
const share_json_2 = __importDefault(require("../../public/locales/en/share.json"));
const common_json_3 = __importDefault(require("../../public/locales/ja/common.json"));
const area_json_3 = __importDefault(require("../../public/locales/ja/area.json"));
const mission_json_3 = __importDefault(require("../../public/locales/ja/mission.json"));
const workspace_json_3 = __importDefault(require("../../public/locales/ja/workspace.json"));
const execution_json_3 = __importDefault(require("../../public/locales/ja/execution.json"));
const llm_json_3 = __importDefault(require("../../public/locales/ja/llm.json"));
const sidebar_json_3 = __importDefault(require("../../public/locales/ja/sidebar.json"));
const onboarding_json_3 = __importDefault(require("../../public/locales/ja/onboarding.json"));
const settings_json_3 = __importDefault(require("../../public/locales/ja/settings.json"));
const approval_json_3 = __importDefault(require("../../public/locales/ja/approval.json"));
const trust_json_3 = __importDefault(require("../../public/locales/ja/trust.json"));
const run_json_3 = __importDefault(require("../../public/locales/ja/run.json"));
const cards_json_3 = __importDefault(require("../../public/locales/ja/cards.json"));
const chat_json_3 = __importDefault(require("../../public/locales/ja/chat.json"));
const cmd_json_3 = __importDefault(require("../../public/locales/ja/cmd.json"));
const share_json_3 = __importDefault(require("../../public/locales/ja/share.json"));
exports.SUPPORTED_LNGS = ['ko', 'en', 'ja'];
exports.I18N_NAMESPACES = [
    'common',
    'area',
    'mission',
    'workspace',
    'execution',
    'llm',
    'sidebar',
    'onboarding',
    'settings',
    'approval',
    'trust',
    'run',
    'cards',
    'chat',
    'cmd',
    'share',
];
exports.I18N_LANGUAGE_KEY = 'i18nextLng';
exports.LEGACY_LOCALE_KEY = 'ds-agent-locale';
exports.I18N_RESOURCES = {
    ko: {
        common: common_json_1.default,
        area: area_json_1.default,
        mission: mission_json_1.default,
        workspace: workspace_json_1.default,
        execution: execution_json_1.default,
        llm: llm_json_1.default,
        sidebar: sidebar_json_1.default,
        onboarding: onboarding_json_1.default,
        settings: settings_json_1.default,
        approval: approval_json_1.default,
        trust: trust_json_1.default,
        run: run_json_1.default,
        cards: cards_json_1.default,
        chat: chat_json_1.default,
        cmd: cmd_json_1.default,
        share: share_json_1.default,
    },
    en: {
        common: common_json_2.default,
        area: area_json_2.default,
        mission: mission_json_2.default,
        workspace: workspace_json_2.default,
        execution: execution_json_2.default,
        llm: llm_json_2.default,
        sidebar: sidebar_json_2.default,
        onboarding: onboarding_json_2.default,
        settings: settings_json_2.default,
        approval: approval_json_2.default,
        trust: trust_json_2.default,
        run: run_json_2.default,
        cards: cards_json_2.default,
        chat: chat_json_2.default,
        cmd: cmd_json_2.default,
        share: share_json_2.default,
    },
    ja: {
        common: common_json_3.default,
        area: area_json_3.default,
        mission: mission_json_3.default,
        workspace: workspace_json_3.default,
        execution: execution_json_3.default,
        llm: llm_json_3.default,
        sidebar: sidebar_json_3.default,
        onboarding: onboarding_json_3.default,
        settings: settings_json_3.default,
        approval: approval_json_3.default,
        trust: trust_json_3.default,
        run: run_json_3.default,
        cards: cards_json_3.default,
        chat: chat_json_3.default,
        cmd: cmd_json_3.default,
        share: share_json_3.default,
    },
};
const LOCALE_BCP47 = {
    ko: 'ko-KR',
    en: 'en-US',
    ja: 'ja-JP',
};
function detectInitialLocale() {
    try {
        const saved = window.localStorage.getItem(exports.I18N_LANGUAGE_KEY);
        if (saved && exports.SUPPORTED_LNGS.includes(saved)) {
            return saved;
        }
        const legacy = window.localStorage.getItem(exports.LEGACY_LOCALE_KEY);
        if (legacy && exports.SUPPORTED_LNGS.includes(legacy)) {
            window.localStorage.setItem(exports.I18N_LANGUAGE_KEY, legacy);
            return legacy;
        }
    }
    catch {
        // ignore storage failures
    }
    try {
        const base = (navigator.language ?? 'en').toLowerCase().split(/[-_]/, 1)[0];
        if (exports.SUPPORTED_LNGS.includes(base)) {
            return base;
        }
    }
    catch {
        // ignore detection failures
    }
    return 'en';
}
function applyDocumentLocale(lng) {
    if (typeof document === 'undefined')
        return;
    document.documentElement.lang = LOCALE_BCP47[lng];
    document.documentElement.dataset.locale = lng;
}
const initialLng = detectInitialLocale();
void i18next_1.default.use(react_i18next_1.initReactI18next).init({
    resources: exports.I18N_RESOURCES,
    lng: initialLng,
    fallbackLng: 'en',
    supportedLngs: exports.SUPPORTED_LNGS,
    defaultNS: 'common',
    ns: exports.I18N_NAMESPACES,
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
applyDocumentLocale(initialLng);
i18next_1.default.on('languageChanged', (lng) => {
    if (exports.SUPPORTED_LNGS.includes(lng)) {
        applyDocumentLocale(lng);
        try {
            window.localStorage.setItem(exports.I18N_LANGUAGE_KEY, lng);
        }
        catch {
            // ignore storage failures
        }
    }
});
exports.default = i18next_1.default;
