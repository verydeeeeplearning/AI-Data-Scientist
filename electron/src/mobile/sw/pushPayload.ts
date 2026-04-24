import enMobile from '../../../public/locales/en/mobile.json';
import jaMobile from '../../../public/locales/ja/mobile.json';
import koMobile from '../../../public/locales/ko/mobile.json';

export interface NormalizedPushNotification {
  readonly title: string;
  readonly body: string;
  readonly deepLink: string | null;
  readonly tag: string;
}

type NotificationLocale = 'en' | 'ja' | 'ko';

const MOBILE_NOTIFICATION_MESSAGES: Readonly<Record<NotificationLocale, Record<string, string>>> = {
  en: enMobile as Record<string, string>,
  ja: jaMobile as Record<string, string>,
  ko: koMobile as Record<string, string>,
};

function pickString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}

function resolveNotificationLocale(): NotificationLocale {
  if (typeof navigator === 'undefined') {
    return 'en';
  }
  const language = (navigator.language ?? navigator.languages?.[0] ?? 'en').toLowerCase();
  if (language.startsWith('ko')) {
    return 'ko';
  }
  if (language.startsWith('ja')) {
    return 'ja';
  }
  return 'en';
}

function readNotificationCopy(
  key: string,
  locale: NotificationLocale,
  fallbackKey: string,
): string {
  return (
    MOBILE_NOTIFICATION_MESSAGES[locale][key]
    ?? MOBILE_NOTIFICATION_MESSAGES.en[key]
    ?? MOBILE_NOTIFICATION_MESSAGES[locale][fallbackKey]
    ?? MOBILE_NOTIFICATION_MESSAGES.en[fallbackKey]
    ?? ''
  );
}

function notificationFallbackKeys(category: string): { title: string; body: string } {
  if (category === 'approval') {
    return {
      title: 'mobile.push.notification.approval.title',
      body: 'mobile.push.notification.approval.body',
    };
  }
  if (category === 'error') {
    return {
      title: 'mobile.push.notification.error.title',
      body: 'mobile.push.notification.error.body',
    };
  }
  return {
    title: 'mobile.push.notification.default.title',
    body: 'mobile.push.notification.default.body',
  };
}

export function normalizePushNotification(raw: unknown): NormalizedPushNotification {
  const locale = resolveNotificationLocale();
  const defaultKeys = notificationFallbackKeys('notification');

  if (!raw || typeof raw !== 'object') {
    return {
      title: readNotificationCopy(defaultKeys.title, locale, defaultKeys.title),
      body: readNotificationCopy(defaultKeys.body, locale, defaultKeys.body),
      deepLink: null,
      tag: 'ds-agent-notification',
    };
  }

  const record = raw as Record<string, unknown>;
  const hasStructuredData = Boolean(record.data && typeof record.data === 'object');
  const data = hasStructuredData
    ? (record.data as Record<string, unknown>)
    : {};
  const category = pickString(data, 'category') ?? 'notification';
  const fallbackKeys = notificationFallbackKeys(category);
  const titleKey = pickString(data, 'titleKey');
  const bodyKey = pickString(data, 'bodyKey');
  const rawTitle = hasStructuredData && category !== 'error' ? pickString(record, 'title') : null;
  const rawBody = hasStructuredData && category !== 'error' ? pickString(record, 'body') : null;

  return {
    title: titleKey
      ? readNotificationCopy(titleKey, locale, fallbackKeys.title)
      : rawTitle ?? readNotificationCopy(fallbackKeys.title, locale, fallbackKeys.title),
    body: bodyKey
      ? readNotificationCopy(bodyKey, locale, fallbackKeys.body)
      : rawBody ?? readNotificationCopy(fallbackKeys.body, locale, fallbackKeys.body),
    deepLink: pickString(data, 'deepLink'),
    tag: `ds-agent-${category}`,
  };
}

export function resolveNotificationClickTarget(data: unknown, fallback: string = './'): string {
  if (data && typeof data === 'object') {
    const deepLink = pickString(data as Record<string, unknown>, 'deepLink');
    if (deepLink) {
      return deepLink;
    }
  }
  return fallback;
}
