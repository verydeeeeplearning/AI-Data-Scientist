"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const mobile_json_1 = __importDefault(require("../../public/locales/en/mobile.json"));
const mobile_json_2 = __importDefault(require("../../public/locales/ko/mobile.json"));
const mobile_json_3 = __importDefault(require("../../public/locales/ja/mobile.json"));
const meta_1 = require("../../src/shared/i18n/meta");
const i18n_1 = require("../../src/mobile/i18n");
function createStorage(initialLocale = null) {
    const values = new Map();
    if (initialLocale) {
        values.set(i18n_1.MOBILE_I18N_LANGUAGE_KEY, initialLocale);
    }
    return {
        getItem(key) {
            return values.get(key) ?? null;
        },
        setItem(key, value) {
            values.set(key, value);
        },
    };
}
function createDocumentLike() {
    return {
        documentElement: {
            lang: '',
            dataset: {},
        },
    };
}
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
test('mobile locale registry stays bounded to the 3 shared locales', () => {
    strict_1.default.deepEqual([...i18n_1.MOBILE_SUPPORTED_LNGS], [...meta_1.SHARED_I18N_LOCALES]);
    strict_1.default.deepEqual([...i18n_1.MOBILE_I18N_NAMESPACES], [...meta_1.MOBILE_I18N_NAMESPACES]);
});
test('resolveInitialMobileLocale prefers saved locale over browser language', () => {
    const storage = createStorage('ja');
    const locale = (0, i18n_1.resolveInitialMobileLocale)({
        storage,
        navigatorLanguage: 'ko-KR',
    });
    strict_1.default.equal(locale, 'ja');
});
test('resolveInitialMobileLocale falls back to browser language and then en', () => {
    strict_1.default.equal((0, i18n_1.resolveInitialMobileLocale)({
        storage: createStorage('en-US'),
        navigatorLanguage: 'ko-KR',
    }), 'en');
    strict_1.default.equal((0, i18n_1.resolveInitialMobileLocale)({ navigatorLanguage: 'ko-KR' }), 'ko');
    strict_1.default.equal((0, i18n_1.resolveInitialMobileLocale)({ navigatorLanguage: 'fr-FR' }), 'en');
});
test('createMobileI18nInstance loads the saved locale and syncs document metadata', async () => {
    const storage = createStorage('ja');
    const documentLike = createDocumentLike();
    const instance = await (0, i18n_1.createMobileI18nInstance)({
        storage,
        document: documentLike,
        navigatorLanguage: 'en-US',
    });
    strict_1.default.equal(instance.t('nav.mission'), mobile_json_3.default['nav.mission']);
    strict_1.default.equal(documentLike.documentElement.lang, 'ja-JP');
    strict_1.default.equal(documentLike.documentElement.dataset.locale, 'ja');
});
test('createMobileI18nInstance persists language changes and serves locale copy', async () => {
    const storage = createStorage('en');
    const documentLike = createDocumentLike();
    const instance = await (0, i18n_1.createMobileI18nInstance)({
        storage,
        document: documentLike,
        navigatorLanguage: 'en-US',
    });
    strict_1.default.equal(instance.t('status.readOnly'), mobile_json_1.default['status.readOnly']);
    await instance.changeLanguage('ko');
    strict_1.default.equal(instance.t('status.readOnly'), mobile_json_2.default['status.readOnly']);
    strict_1.default.equal(storage.getItem(i18n_1.MOBILE_I18N_LANGUAGE_KEY), 'ko');
    strict_1.default.equal(documentLike.documentElement.lang, 'ko-KR');
    strict_1.default.equal(documentLike.documentElement.dataset.locale, 'ko');
});
let passed = 0;
let failed = 0;
(async () => {
    for (const current of tests) {
        try {
            await current.fn();
            console.log(`  ok  ${current.name}`);
            passed += 1;
        }
        catch (error) {
            console.error(`  FAIL ${current.name}`);
            console.error(`    ${error.message}`);
            failed += 1;
        }
    }
    console.log(`\nmobileI18n.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
    if (failed > 0) {
        process.exit(1);
    }
})();
