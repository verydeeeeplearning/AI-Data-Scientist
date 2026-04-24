"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = require("node:fs");
const node_path_1 = require("node:path");
const i18next_1 = __importDefault(require("i18next"));
const meta_1 = require("../../src/shared/i18n/meta");
function findElectronRoot(start) {
    let dir = start;
    for (let i = 0; i < 8; i += 1) {
        if (dir.endsWith('electron') || dir.endsWith('electron\\') || dir.endsWith('electron/')) {
            return dir;
        }
        const parent = (0, node_path_1.resolve)(dir, '..');
        if (parent === dir)
            break;
        dir = parent;
    }
    return (0, node_path_1.resolve)(start, '..', '..', '..', '..');
}
const ELECTRON_ROOT = findElectronRoot(__dirname);
const LOCALES_DIR = (0, node_path_1.join)(ELECTRON_ROOT, 'public', 'locales');
const NAMESPACES = meta_1.DESKTOP_I18N_NAMESPACES;
const LOCALES = meta_1.SHARED_I18N_LOCALES;
function loadResources() {
    const out = {};
    for (const lng of LOCALES) {
        out[lng] = {};
        for (const ns of NAMESPACES) {
            const filePath = (0, node_path_1.join)(LOCALES_DIR, lng, `${ns}.json`);
            out[lng][ns] = JSON.parse((0, node_fs_1.readFileSync)(filePath, 'utf8').replace(/^\uFEFF/, ''));
        }
    }
    return out;
}
const NAMESPACE_SET = new Set(NAMESPACES);
function resolveNamespaceAndKey(rawKey) {
    const colonIdx = rawKey.indexOf(':');
    if (colonIdx > 0)
        return { ns: rawKey.slice(0, colonIdx), key: rawKey.slice(colonIdx + 1) };
    const dotIdx = rawKey.indexOf('.');
    if (dotIdx > 0) {
        const candidate = rawKey.slice(0, dotIdx);
        if (NAMESPACE_SET.has(candidate))
            return { ns: candidate, key: rawKey.slice(dotIdx + 1) };
    }
    return { ns: 'common', key: rawKey };
}
function shimT(key, vars) {
    const { ns, key: lookup } = resolveNamespaceAndKey(key);
    const result = i18next_1.default.t(lookup, {
        ns,
        defaultValue: key,
        replace: vars ?? undefined,
    });
    return typeof result === 'string' ? result : key;
}
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
test('namespace inference: prefix matches a registered namespace and is stripped', () => {
    strict_1.default.deepEqual(resolveNamespaceAndKey('mission.header.title'), {
        ns: 'mission',
        key: 'header.title',
    });
    strict_1.default.deepEqual(resolveNamespaceAndKey('execution.stage.eda'), {
        ns: 'execution',
        key: 'stage.eda',
    });
    strict_1.default.deepEqual(resolveNamespaceAndKey('area.mission.label'), {
        ns: 'area',
        key: 'mission.label',
    });
    strict_1.default.deepEqual(resolveNamespaceAndKey('cmd.palette.title'), {
        ns: 'cmd',
        key: 'palette.title',
    });
});
test('namespace inference: unknown prefix falls back to common, key kept whole', () => {
    strict_1.default.deepEqual(resolveNamespaceAndKey('alert.leakage'), {
        ns: 'common',
        key: 'alert.leakage',
    });
    strict_1.default.deepEqual(resolveNamespaceAndKey('quality.grade.A'), {
        ns: 'common',
        key: 'quality.grade.A',
    });
});
test('namespace inference: explicit ns:key syntax wins over dot prefix', () => {
    strict_1.default.deepEqual(resolveNamespaceAndKey('common:mission.header.title'), {
        ns: 'common',
        key: 'mission.header.title',
    });
});
test('namespace inference: bare key without dot uses common', () => {
    strict_1.default.deepEqual(resolveNamespaceAndKey('save'), { ns: 'common', key: 'save' });
});
test('i18next init: 3 locales x shared desktop namespaces resources load', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await i18next_1.default.init({
        resources: loadResources(),
        lng: 'en',
        fallbackLng: 'en',
        supportedLngs: LOCALES,
        defaultNS: 'common',
        ns: NAMESPACES,
        nsSeparator: ':',
        keySeparator: '.',
        interpolation: { escapeValue: false, prefix: '{', suffix: '}' },
        initImmediate: false,
    });
    strict_1.default.ok(i18next_1.default.isInitialized);
});
test('shim t(): mission.header.title returns en value', () => {
    const value = shimT('mission.header.title');
    strict_1.default.equal(value, 'Mission Header');
});
test('shim t(): namespace inference + interpolation works', () => {
    const value = shimT('mission.header.elapsed', { value: '3m' });
    strict_1.default.equal(value, '3m elapsed');
});
test('shim t(): common namespace lookup', () => {
    const value = shimT('common.save');
    strict_1.default.equal(value, 'Save');
});
test('shim t(): unknown key returns the key as fallback', () => {
    const value = shimT('mission.nonexistent.key');
    strict_1.default.equal(value, 'mission.nonexistent.key');
});
test('shim t(): execution stage label', () => {
    const value = shimT('execution.stage.data_loading');
    strict_1.default.equal(value, 'Data loading');
});
test('shim t(): locale switch to ko surfaces Korean copy', async () => {
    await i18next_1.default.changeLanguage('ko');
    strict_1.default.equal(shimT('mission.header.title'), '미션 헤더');
    strict_1.default.equal(shimT('common.save'), '저장');
});
test('shim t(): locale switch to ja surfaces Japanese copy', async () => {
    await i18next_1.default.changeLanguage('ja');
    strict_1.default.equal(shimT('mission.header.title'), 'ミッションヘッダー');
});
test('shim t(): ko interpolation preserves vars', async () => {
    await i18next_1.default.changeLanguage('ko');
    const value = shimT('mission.header.sourceCount', { count: 3 });
    strict_1.default.equal(value, '소스 3개');
});
let passed = 0;
let failed = 0;
(async () => {
    for (const t of tests) {
        try {
            await t.fn();
            console.log(`  ok  ${t.name}`);
            passed += 1;
        }
        catch (err) {
            console.error(`  FAIL ${t.name}`);
            console.error(`    ${err.message}`);
            failed += 1;
        }
    }
    console.log(`\ni18nStoreShim.spec — ${passed}/${passed + failed} passed${failed ? ' (' + failed + ' failed)' : ''}`);
    if (failed > 0)
        process.exit(1);
})();
