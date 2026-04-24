import assert from 'node:assert/strict';

import enMobile from '../../public/locales/en/mobile.json';
import koMobile from '../../public/locales/ko/mobile.json';
import jaMobile from '../../public/locales/ja/mobile.json';
import {
  MOBILE_I18N_NAMESPACES as SHARED_MOBILE_I18N_NAMESPACES,
  SHARED_I18N_LOCALES,
} from '../../src/shared/i18n/meta';
import {
  MOBILE_I18N_LANGUAGE_KEY,
  MOBILE_I18N_NAMESPACES,
  MOBILE_SUPPORTED_LNGS,
  createMobileI18nInstance,
  resolveInitialMobileLocale,
} from '../../src/mobile/i18n';

interface StorageLike {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
}

interface DocumentLike {
  documentElement: {
    lang: string;
    dataset: Record<string, string | undefined>;
  };
}

function createStorage(initialLocale: string | null = null): StorageLike {
  const values = new Map<string, string>();
  if (initialLocale) {
    values.set(MOBILE_I18N_LANGUAGE_KEY, initialLocale);
  }
  return {
    getItem(key: string): string | null {
      return values.get(key) ?? null;
    },
    setItem(key: string, value: string): void {
      values.set(key, value);
    },
  };
}

function createDocumentLike(): DocumentLike {
  return {
    documentElement: {
      lang: '',
      dataset: {},
    },
  };
}

interface TestCase {
  name: string;
  fn: () => void | Promise<void>;
}

const tests: TestCase[] = [];

function test(name: string, fn: () => void | Promise<void>): void {
  tests.push({ name, fn });
}

test('mobile locale registry stays bounded to the 3 shared locales', () => {
  assert.deepEqual([...MOBILE_SUPPORTED_LNGS], [...SHARED_I18N_LOCALES]);
  assert.deepEqual([...MOBILE_I18N_NAMESPACES], [...SHARED_MOBILE_I18N_NAMESPACES]);
});

test('resolveInitialMobileLocale prefers saved locale over browser language', () => {
  const storage = createStorage('ja');
  const locale = resolveInitialMobileLocale({
    storage,
    navigatorLanguage: 'ko-KR',
  });
  assert.equal(locale, 'ja');
});

test('resolveInitialMobileLocale falls back to browser language and then en', () => {
  assert.equal(
    resolveInitialMobileLocale({
      storage: createStorage('en-US'),
      navigatorLanguage: 'ko-KR',
    }),
    'en',
  );
  assert.equal(resolveInitialMobileLocale({ navigatorLanguage: 'ko-KR' }), 'ko');
  assert.equal(resolveInitialMobileLocale({ navigatorLanguage: 'fr-FR' }), 'en');
});

test('createMobileI18nInstance loads the saved locale and syncs document metadata', async () => {
  const storage = createStorage('ja');
  const documentLike = createDocumentLike();
  const instance = await createMobileI18nInstance({
    storage,
    document: documentLike,
    navigatorLanguage: 'en-US',
  });

  assert.equal(instance.t('nav.mission'), jaMobile['nav.mission']);
  assert.equal(documentLike.documentElement.lang, 'ja-JP');
  assert.equal(documentLike.documentElement.dataset.locale, 'ja');
});

test('createMobileI18nInstance persists language changes and serves locale copy', async () => {
  const storage = createStorage('en');
  const documentLike = createDocumentLike();
  const instance = await createMobileI18nInstance({
    storage,
    document: documentLike,
    navigatorLanguage: 'en-US',
  });

  assert.equal(instance.t('status.readOnly'), enMobile['status.readOnly']);

  await instance.changeLanguage('ko');
  assert.equal(instance.t('status.readOnly'), koMobile['status.readOnly']);
  assert.equal(storage.getItem(MOBILE_I18N_LANGUAGE_KEY), 'ko');
  assert.equal(documentLike.documentElement.lang, 'ko-KR');
  assert.equal(documentLike.documentElement.dataset.locale, 'ko');
});

let passed = 0;
let failed = 0;

(async () => {
  for (const current of tests) {
    try {
      await current.fn();
      console.log(`  ok  ${current.name}`);
      passed += 1;
    } catch (error) {
      console.error(`  FAIL ${current.name}`);
      console.error(`    ${(error as Error).message}`);
      failed += 1;
    }
  }

  console.log(
    `\nmobileI18n.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
  );

  if (failed > 0) {
    process.exit(1);
  }
})();
