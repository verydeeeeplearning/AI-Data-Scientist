import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import i18next from 'i18next';
import {
  DESKTOP_I18N_NAMESPACES,
  SHARED_I18N_LOCALES,
} from '../../src/shared/i18n/meta';

function findElectronRoot(start: string): string {
  let dir = start;
  for (let i = 0; i < 8; i += 1) {
    if (dir.endsWith('electron') || dir.endsWith('electron\\') || dir.endsWith('electron/')) {
      return dir;
    }
    const parent = resolve(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  return resolve(start, '..', '..', '..', '..');
}

const ELECTRON_ROOT = findElectronRoot(__dirname);
const LOCALES_DIR = join(ELECTRON_ROOT, 'public', 'locales');

const NAMESPACES = DESKTOP_I18N_NAMESPACES;
const LOCALES = SHARED_I18N_LOCALES;

function loadResources(): Record<string, Record<string, unknown>> {
  const out: Record<string, Record<string, unknown>> = {};
  for (const lng of LOCALES) {
    out[lng] = {};
    for (const ns of NAMESPACES) {
      const filePath = join(LOCALES_DIR, lng, `${ns}.json`);
      out[lng][ns] = JSON.parse(readFileSync(filePath, 'utf8').replace(/^\uFEFF/, ''));
    }
  }
  return out;
}

const NAMESPACE_SET = new Set<string>(NAMESPACES);

function resolveNamespaceAndKey(rawKey: string): { ns: string; key: string } {
  const colonIdx = rawKey.indexOf(':');
  if (colonIdx > 0) return { ns: rawKey.slice(0, colonIdx), key: rawKey.slice(colonIdx + 1) };
  const dotIdx = rawKey.indexOf('.');
  if (dotIdx > 0) {
    const candidate = rawKey.slice(0, dotIdx);
    if (NAMESPACE_SET.has(candidate)) return { ns: candidate, key: rawKey.slice(dotIdx + 1) };
  }
  return { ns: 'common', key: rawKey };
}

function shimT(key: string, vars?: Record<string, unknown>): string {
  const { ns, key: lookup } = resolveNamespaceAndKey(key);
  const result = i18next.t(lookup, {
    ns,
    defaultValue: key,
    replace: vars ?? undefined,
  });
  return typeof result === 'string' ? result : key;
}

interface TestCase {
  name: string;
  fn: () => void | Promise<void>;
}
const tests: TestCase[] = [];
function test(name: string, fn: () => void | Promise<void>): void {
  tests.push({ name, fn });
}

test('namespace inference: prefix matches a registered namespace and is stripped', () => {
  assert.deepEqual(resolveNamespaceAndKey('mission.header.title'), {
    ns: 'mission',
    key: 'header.title',
  });
  assert.deepEqual(resolveNamespaceAndKey('execution.stage.eda'), {
    ns: 'execution',
    key: 'stage.eda',
  });
  assert.deepEqual(resolveNamespaceAndKey('area.mission.label'), {
    ns: 'area',
    key: 'mission.label',
  });
  assert.deepEqual(resolveNamespaceAndKey('cmd.palette.title'), {
    ns: 'cmd',
    key: 'palette.title',
  });
});

test('namespace inference: unknown prefix falls back to common, key kept whole', () => {
  assert.deepEqual(resolveNamespaceAndKey('alert.leakage'), {
    ns: 'common',
    key: 'alert.leakage',
  });
  assert.deepEqual(resolveNamespaceAndKey('quality.grade.A'), {
    ns: 'common',
    key: 'quality.grade.A',
  });
});

test('namespace inference: explicit ns:key syntax wins over dot prefix', () => {
  assert.deepEqual(resolveNamespaceAndKey('common:mission.header.title'), {
    ns: 'common',
    key: 'mission.header.title',
  });
});

test('namespace inference: bare key without dot uses common', () => {
  assert.deepEqual(resolveNamespaceAndKey('save'), { ns: 'common', key: 'save' });
});

test('i18next init: 3 locales x shared desktop namespaces resources load', async () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await i18next.init({
    resources: loadResources() as any,
    lng: 'en',
    fallbackLng: 'en',
    supportedLngs: LOCALES as readonly string[],
    defaultNS: 'common',
    ns: NAMESPACES as readonly string[],
    nsSeparator: ':',
    keySeparator: '.',
    interpolation: { escapeValue: false, prefix: '{', suffix: '}' },
    initImmediate: false,
  });
  assert.ok(i18next.isInitialized);
});

test('shim t(): mission.header.title returns en value', () => {
  const value = shimT('mission.header.title');
  assert.equal(value, 'Mission Header');
});

test('shim t(): namespace inference + interpolation works', () => {
  const value = shimT('mission.header.elapsed', { value: '3m' });
  assert.equal(value, '3m elapsed');
});

test('shim t(): common namespace lookup', () => {
  const value = shimT('common.save');
  assert.equal(value, 'Save');
});

test('shim t(): unknown key returns the key as fallback', () => {
  const value = shimT('mission.nonexistent.key');
  assert.equal(value, 'mission.nonexistent.key');
});

test('shim t(): execution stage label', () => {
  const value = shimT('execution.stage.data_loading');
  assert.equal(value, 'Data loading');
});

test('shim t(): locale switch to ko surfaces Korean copy', async () => {
  await i18next.changeLanguage('ko');
  assert.equal(shimT('mission.header.title'), '미션 헤더');
  assert.equal(shimT('common.save'), '저장');
});

test('shim t(): locale switch to ja surfaces Japanese copy', async () => {
  await i18next.changeLanguage('ja');
  assert.equal(shimT('mission.header.title'), 'ミッションヘッダー');
});

test('shim t(): ko interpolation preserves vars', async () => {
  await i18next.changeLanguage('ko');
  const value = shimT('mission.header.sourceCount', { count: 3 });
  assert.equal(value, '소스 3개');
});

let passed = 0;
let failed = 0;

(async () => {
  for (const t of tests) {
    try {
      await t.fn();
      console.log(`  ok  ${t.name}`);
      passed += 1;
    } catch (err) {
      console.error(`  FAIL ${t.name}`);
      console.error(`    ${(err as Error).message}`);
      failed += 1;
    }
  }
  console.log(
    `\ni18nStoreShim.spec — ${passed}/${passed + failed} passed${failed ? ' (' + failed + ' failed)' : ''}`,
  );
  if (failed > 0) process.exit(1);
})();
