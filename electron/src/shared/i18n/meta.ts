export const SHARED_I18N_LOCALES = ['ko', 'en', 'ja'] as const;
export type SharedI18nLocale = (typeof SHARED_I18N_LOCALES)[number];

export const DESKTOP_I18N_NAMESPACES = [
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
  'session',
] as const;
export type DesktopI18nNamespace = (typeof DESKTOP_I18N_NAMESPACES)[number];

export const MOBILE_I18N_NAMESPACES = ['mobile'] as const;
export type MobileI18nNamespace = (typeof MOBILE_I18N_NAMESPACES)[number];

export const ALL_I18N_NAMESPACES = [
  ...DESKTOP_I18N_NAMESPACES,
  ...MOBILE_I18N_NAMESPACES,
] as const;
export type AnyI18nNamespace = (typeof ALL_I18N_NAMESPACES)[number];
