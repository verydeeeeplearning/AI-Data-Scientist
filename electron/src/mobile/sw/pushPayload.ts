export interface NormalizedPushNotification {
  readonly title: string;
  readonly body: string;
  readonly deepLink: string | null;
  readonly tag: string;
}

function pickString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}

export function normalizePushNotification(raw: unknown): NormalizedPushNotification {
  if (!raw || typeof raw !== 'object') {
    return {
      title: 'DS Agent',
      body: '',
      deepLink: null,
      tag: 'ds-agent-notification',
    };
  }

  const record = raw as Record<string, unknown>;
  const data = record.data && typeof record.data === 'object'
    ? (record.data as Record<string, unknown>)
    : {};
  const category = pickString(data, 'category') ?? 'notification';

  return {
    title: pickString(record, 'title') ?? 'DS Agent',
    body: pickString(record, 'body') ?? '',
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
