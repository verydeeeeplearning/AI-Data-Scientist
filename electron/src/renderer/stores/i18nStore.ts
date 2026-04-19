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

import { useEffect, useSyncExternalStore } from 'react';

import i18next, {
  I18N_LANGUAGE_KEY,
  I18N_NAMESPACES,
  SUPPORTED_LNGS,
  type SupportedLng,
} from '../i18n';

export type Locale = SupportedLng;

export interface LocaleOption {
  code: Locale;
  nativeLabel: string;
  englishLabel: string;
  bcp47: string;
}

type Interpolations = Record<string, string | number | undefined | null>;

export const LOCALE_STORAGE_KEY = I18N_LANGUAGE_KEY;

export const LOCALE_OPTIONS: readonly LocaleOption[] = [
  { code: 'ko', nativeLabel: '한국어', englishLabel: 'Korean', bcp47: 'ko-KR' },
  { code: 'en', nativeLabel: 'English', englishLabel: 'English', bcp47: 'en-US' },
  { code: 'ja', nativeLabel: '日本語', englishLabel: 'Japanese', bcp47: 'ja-JP' },
] as const;

const SUPPORTED_LOCALES = new Set<Locale>(LOCALE_OPTIONS.map((option) => option.code));
const NAMESPACE_SET = new Set<string>(I18N_NAMESPACES);

export function isSupportedLocale(value: unknown): value is Locale {
  return typeof value === 'string' && SUPPORTED_LOCALES.has(value as Locale);
}

export function normalizeLocale(value: string | null | undefined): Locale | null {
  if (!value) return null;
  const normalized = value.toLowerCase();
  const base = normalized.split(/[-_]/, 1)[0];
  return isSupportedLocale(base) ? base : null;
}

export function getLocaleOption(locale: Locale): LocaleOption {
  return LOCALE_OPTIONS.find((option) => option.code === locale) ?? LOCALE_OPTIONS[1];
}

function resolveNamespaceAndKey(rawKey: string): { ns: string; key: string } {
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

function translate(key: string, vars?: Interpolations): string {
  const { ns, key: lookup } = resolveNamespaceAndKey(key);
  const result = i18next.t(lookup, {
    ns,
    defaultValue: key,
    replace: vars ?? undefined,
  });
  return typeof result === 'string' ? result : key;
}

function currentLocale(): Locale {
  const lng = i18next.resolvedLanguage ?? i18next.language ?? 'en';
  return (isSupportedLocale(lng) ? lng : 'en') as Locale;
}

const listeners = new Set<() => void>();

function emitChange(): void {
  for (const listener of listeners) {
    listener();
  }
}

i18next.on('languageChanged', emitChange);
i18next.on('initialized', emitChange);

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): Locale {
  return currentLocale();
}

export interface UseI18nResult {
  locale: Locale;
  locales: readonly LocaleOption[];
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Interpolations) => string;
}

function buildResult(locale: Locale): UseI18nResult {
  return {
    locale,
    locales: LOCALE_OPTIONS,
    setLocale,
    t: translate,
  };
}

export function useI18n(): UseI18nResult;
export function useI18n<T>(selector: (state: UseI18nResult) => T): T;
export function useI18n<T>(selector?: (state: UseI18nResult) => T): UseI18nResult | T {
  const locale = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = getLocaleOption(locale).bcp47;
      document.documentElement.dataset.locale = locale;
    }
  }, [locale]);

  const state = buildResult(locale);
  return selector ? selector(state) : state;
}

export function setLocale(locale: Locale): void {
  if (!isSupportedLocale(locale)) return;
  if (i18next.language === locale && i18next.resolvedLanguage === locale) {
    emitChange();
    return;
  }
  void i18next.changeLanguage(locale);
}

export function getCurrentLocale(): Locale {
  return currentLocale();
}

export function translateKey(key: string, vars?: Interpolations): string {
  return translate(key, vars);
}

export const __test = {
  resolveNamespaceAndKey,
  translate,
  currentLocale,
  SUPPORTED_LNGS,
};
