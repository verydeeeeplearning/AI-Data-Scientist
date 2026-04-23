import i18next, { createInstance, type i18n as I18nInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';

import koMobile from '../../public/locales/ko/mobile.json';
import enMobile from '../../public/locales/en/mobile.json';
import jaMobile from '../../public/locales/ja/mobile.json';

export const MOBILE_SUPPORTED_LNGS = ['ko', 'en', 'ja'] as const;
export type MobileLocale = (typeof MOBILE_SUPPORTED_LNGS)[number];

export const MOBILE_I18N_NAMESPACES = ['mobile'] as const;
export const MOBILE_I18N_LANGUAGE_KEY = 'i18nextLng';

export const MOBILE_I18N_RESOURCES = {
  ko: {
    mobile: koMobile,
  },
  en: {
    mobile: enMobile,
  },
  ja: {
    mobile: jaMobile,
  },
} as const;

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

interface DocumentLike {
  documentElement: {
    lang: string;
    dataset: Record<string, string | undefined>;
  };
}

interface MobileI18nInitOptions {
  readonly document?: DocumentLike | null;
  readonly navigatorLanguage?: string | null;
  readonly storage?: StorageLike | null;
}

const LOCALE_BCP47: Record<MobileLocale, string> = {
  ko: 'ko-KR',
  en: 'en-US',
  ja: 'ja-JP',
};

function normalizeMobileLocale(value: string | null | undefined): MobileLocale | null {
  if (typeof value !== 'string' || value.length === 0) {
    return null;
  }
  const normalized = value.toLowerCase().split(/[-_]/, 1)[0];
  return isMobileLocale(normalized) ? normalized : null;
}

function isMobileLocale(value: string | null | undefined): value is MobileLocale {
  return (
    typeof value === 'string' &&
    (MOBILE_SUPPORTED_LNGS as readonly string[]).includes(value)
  );
}

function getBrowserStorage(): StorageLike | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function getNavigatorLanguage(): string | null {
  if (typeof navigator === 'undefined') {
    return null;
  }
  return navigator.language ?? navigator.languages?.[0] ?? null;
}

function getDocumentTarget(): DocumentLike | null {
  if (typeof document === 'undefined') {
    return null;
  }
  return document as unknown as DocumentLike;
}

export function resolveInitialMobileLocale(
  options: Pick<MobileI18nInitOptions, 'navigatorLanguage' | 'storage'> = {},
): MobileLocale {
  const saved = normalizeMobileLocale(options.storage?.getItem(MOBILE_I18N_LANGUAGE_KEY) ?? null);
  if (saved) {
    return saved;
  }

  const browserLocale = normalizeMobileLocale(options.navigatorLanguage ?? getNavigatorLanguage());
  if (browserLocale) {
    return browserLocale;
  }

  return 'en';
}

export function applyMobileDocumentLocale(
  locale: MobileLocale,
  documentTarget: DocumentLike | null = getDocumentTarget(),
): void {
  if (!documentTarget) {
    return;
  }
  documentTarget.documentElement.lang = LOCALE_BCP47[locale];
  documentTarget.documentElement.dataset.locale = locale;
}

export async function initializeMobileI18n(
  instance: I18nInstance,
  options: MobileI18nInitOptions = {},
): Promise<I18nInstance> {
  const storage = options.storage ?? getBrowserStorage();
  const documentTarget = options.document ?? getDocumentTarget();
  const locale = resolveInitialMobileLocale({
    storage,
    navigatorLanguage: options.navigatorLanguage,
  });

  await instance.use(initReactI18next).init({
    resources: MOBILE_I18N_RESOURCES,
    lng: locale,
    fallbackLng: 'en',
    supportedLngs: MOBILE_SUPPORTED_LNGS as readonly string[],
    defaultNS: 'mobile',
    ns: MOBILE_I18N_NAMESPACES as readonly string[],
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
      storage?.setItem(MOBILE_I18N_LANGUAGE_KEY, nextLanguage);
    } catch {
      // Ignore storage failures in constrained webviews.
    }
  });

  return instance;
}

export async function createMobileI18nInstance(
  options: MobileI18nInitOptions = {},
): Promise<I18nInstance> {
  const instance = createInstance();
  return initializeMobileI18n(instance, options);
}

void initializeMobileI18n(i18next);

export default i18next;
