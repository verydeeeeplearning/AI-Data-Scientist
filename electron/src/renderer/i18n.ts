import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import {
  DESKTOP_I18N_NAMESPACES,
  SHARED_I18N_LOCALES,
} from '../shared/i18n/meta';

import koCommon from '../../public/locales/ko/common.json';
import koArea from '../../public/locales/ko/area.json';
import koMission from '../../public/locales/ko/mission.json';
import koWorkspace from '../../public/locales/ko/workspace.json';
import koExecution from '../../public/locales/ko/execution.json';
import koLlm from '../../public/locales/ko/llm.json';
import koSidebar from '../../public/locales/ko/sidebar.json';
import koOnboarding from '../../public/locales/ko/onboarding.json';
import koSettings from '../../public/locales/ko/settings.json';
import koApproval from '../../public/locales/ko/approval.json';
import koTrust from '../../public/locales/ko/trust.json';
import koRun from '../../public/locales/ko/run.json';
import koCards from '../../public/locales/ko/cards.json';
import koChat from '../../public/locales/ko/chat.json';
import koCmd from '../../public/locales/ko/cmd.json';
import koShare from '../../public/locales/ko/share.json';

import enCommon from '../../public/locales/en/common.json';
import enArea from '../../public/locales/en/area.json';
import enMission from '../../public/locales/en/mission.json';
import enWorkspace from '../../public/locales/en/workspace.json';
import enExecution from '../../public/locales/en/execution.json';
import enLlm from '../../public/locales/en/llm.json';
import enSidebar from '../../public/locales/en/sidebar.json';
import enOnboarding from '../../public/locales/en/onboarding.json';
import enSettings from '../../public/locales/en/settings.json';
import enApproval from '../../public/locales/en/approval.json';
import enTrust from '../../public/locales/en/trust.json';
import enRun from '../../public/locales/en/run.json';
import enCards from '../../public/locales/en/cards.json';
import enChat from '../../public/locales/en/chat.json';
import enCmd from '../../public/locales/en/cmd.json';
import enShare from '../../public/locales/en/share.json';

import jaCommon from '../../public/locales/ja/common.json';
import jaArea from '../../public/locales/ja/area.json';
import jaMission from '../../public/locales/ja/mission.json';
import jaWorkspace from '../../public/locales/ja/workspace.json';
import jaExecution from '../../public/locales/ja/execution.json';
import jaLlm from '../../public/locales/ja/llm.json';
import jaSidebar from '../../public/locales/ja/sidebar.json';
import jaOnboarding from '../../public/locales/ja/onboarding.json';
import jaSettings from '../../public/locales/ja/settings.json';
import jaApproval from '../../public/locales/ja/approval.json';
import jaTrust from '../../public/locales/ja/trust.json';
import jaRun from '../../public/locales/ja/run.json';
import jaCards from '../../public/locales/ja/cards.json';
import jaChat from '../../public/locales/ja/chat.json';
import jaCmd from '../../public/locales/ja/cmd.json';
import jaShare from '../../public/locales/ja/share.json';

export const SUPPORTED_LNGS = SHARED_I18N_LOCALES;
export type SupportedLng = (typeof SUPPORTED_LNGS)[number];

export const I18N_NAMESPACES = DESKTOP_I18N_NAMESPACES;
export type I18nNamespace = (typeof I18N_NAMESPACES)[number];

export const I18N_LANGUAGE_KEY = 'i18nextLng';
export const LEGACY_LOCALE_KEY = 'ds-agent-locale';

export const I18N_RESOURCES = {
  ko: {
    common: koCommon,
    area: koArea,
    mission: koMission,
    workspace: koWorkspace,
    execution: koExecution,
    llm: koLlm,
    sidebar: koSidebar,
    onboarding: koOnboarding,
    settings: koSettings,
    approval: koApproval,
    trust: koTrust,
    run: koRun,
    cards: koCards,
    chat: koChat,
    cmd: koCmd,
    share: koShare,
  },
  en: {
    common: enCommon,
    area: enArea,
    mission: enMission,
    workspace: enWorkspace,
    execution: enExecution,
    llm: enLlm,
    sidebar: enSidebar,
    onboarding: enOnboarding,
    settings: enSettings,
    approval: enApproval,
    trust: enTrust,
    run: enRun,
    cards: enCards,
    chat: enChat,
    cmd: enCmd,
    share: enShare,
  },
  ja: {
    common: jaCommon,
    area: jaArea,
    mission: jaMission,
    workspace: jaWorkspace,
    execution: jaExecution,
    llm: jaLlm,
    sidebar: jaSidebar,
    onboarding: jaOnboarding,
    settings: jaSettings,
    approval: jaApproval,
    trust: jaTrust,
    run: jaRun,
    cards: jaCards,
    chat: jaChat,
    cmd: jaCmd,
    share: jaShare,
  },
} as const;

const LOCALE_BCP47: Record<SupportedLng, string> = {
  ko: 'ko-KR',
  en: 'en-US',
  ja: 'ja-JP',
};

function detectInitialLocale(): SupportedLng {
  try {
    const saved = window.localStorage.getItem(I18N_LANGUAGE_KEY);
    if (saved && (SUPPORTED_LNGS as readonly string[]).includes(saved)) {
      return saved as SupportedLng;
    }
    const legacy = window.localStorage.getItem(LEGACY_LOCALE_KEY);
    if (legacy && (SUPPORTED_LNGS as readonly string[]).includes(legacy)) {
      window.localStorage.setItem(I18N_LANGUAGE_KEY, legacy);
      return legacy as SupportedLng;
    }
  } catch {
    // ignore storage failures
  }
  try {
    const base = (navigator.language ?? 'en').toLowerCase().split(/[-_]/, 1)[0];
    if ((SUPPORTED_LNGS as readonly string[]).includes(base)) {
      return base as SupportedLng;
    }
  } catch {
    // ignore detection failures
  }
  return 'en';
}

function applyDocumentLocale(lng: SupportedLng): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = LOCALE_BCP47[lng];
  document.documentElement.dataset.locale = lng;
}

const initialLng = detectInitialLocale();

void i18next.use(initReactI18next).init({
  resources: I18N_RESOURCES,
  lng: initialLng,
  fallbackLng: 'en',
  supportedLngs: SUPPORTED_LNGS as readonly string[],
  defaultNS: 'common',
  ns: I18N_NAMESPACES as readonly string[],
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

i18next.on('languageChanged', (lng) => {
  if ((SUPPORTED_LNGS as readonly string[]).includes(lng)) {
    applyDocumentLocale(lng as SupportedLng);
    try {
      window.localStorage.setItem(I18N_LANGUAGE_KEY, lng);
    } catch {
      // ignore storage failures
    }
  }
});

export default i18next;
