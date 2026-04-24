export type RuntimeTranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

export function formatRuntimeRelativeAge(t: RuntimeTranslateFn, ts: number): string {
  const diffSeconds = Math.max(0, Math.round((Date.now() - ts * 1000) / 1000));
  if (diffSeconds < 60) {
    return t('run.runtime.relativeAge.seconds', { count: diffSeconds });
  }
  if (diffSeconds < 3600) {
    return t('run.runtime.relativeAge.minutes', { count: Math.round(diffSeconds / 60) });
  }
  if (diffSeconds < 86_400) {
    return t('run.runtime.relativeAge.hours', { count: Math.round(diffSeconds / 3600) });
  }
  return t('run.runtime.relativeAge.days', { count: Math.round(diffSeconds / 86_400) });
}

export function formatRuntimeIntervalShort(
  t: RuntimeTranslateFn,
  intervalSeconds: number,
): string {
  if (intervalSeconds < 60) {
    return t('run.runtime.policy.recurringGoals.interval.seconds', {
      count: Math.round(intervalSeconds),
    });
  }
  if (intervalSeconds < 3600) {
    return t('run.runtime.policy.recurringGoals.interval.minutes', {
      count: Math.round(intervalSeconds / 60),
    });
  }
  if (intervalSeconds < 86_400) {
    return t('run.runtime.policy.recurringGoals.interval.hours', {
      count: Math.round(intervalSeconds / 3600),
    });
  }
  return t('run.runtime.policy.recurringGoals.interval.days', {
    count: Math.round(intervalSeconds / 86_400),
  });
}

export function translateRuntimeConnectionStatus(
  value: string,
  t: RuntimeTranslateFn,
): string {
  const keyByValue: Record<string, string> = {
    connected: 'run.runtime.connection.connected',
    connecting: 'run.runtime.connection.connecting',
    disconnected: 'run.runtime.connection.disconnected',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}

export function translateRuntimeProfile(value: string, t: RuntimeTranslateFn): string {
  const keyByValue: Record<string, string> = {
    manual: 'run.runtime.profile.manual',
    balanced: 'run.runtime.profile.balanced',
    aggressive: 'run.runtime.profile.aggressive',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}

export function translateRuntimeOverlay(
  value: string | null | undefined,
  t: RuntimeTranslateFn,
): string {
  const normalized = value ?? 'none';
  const keyByValue: Record<string, string> = {
    none: 'run.runtime.overlay.none',
    incident: 'run.runtime.overlay.incident',
    freeze: 'run.runtime.overlay.freeze',
  };
  const key = keyByValue[normalized];
  return key ? t(key) : normalized;
}

export function translateRuntimeMode(value: string, t: RuntimeTranslateFn): string {
  const keyByValue: Record<string, string> = {
    auto: 'run.runtime.mode.auto',
    supervised: 'run.runtime.mode.supervised',
    'step-by-step': 'run.runtime.mode.stepByStep',
    incident: 'run.runtime.overlay.incident',
    freeze: 'run.runtime.overlay.freeze',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}

export function translateRuntimeSeverity(value: string, t: RuntimeTranslateFn): string {
  const keyByValue: Record<string, string> = {
    info: 'run.runtime.severity.info',
    success: 'run.runtime.severity.success',
    warning: 'run.runtime.severity.warning',
    error: 'run.runtime.severity.error',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}

export function translateRuntimeRunStatus(value: string, t: RuntimeTranslateFn): string {
  const keyByValue: Record<string, string> = {
    running: 'run.runtime.status.running',
    succeeded: 'run.runtime.status.succeeded',
    failed: 'run.runtime.status.failed',
    cancelled: 'run.runtime.status.cancelled',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}

export function translateRuntimeEventCategory(
  value: string,
  t: RuntimeTranslateFn,
): string {
  const keyByValue: Record<string, string> = {
    recovery: 'run.runtime.alerts.category.recovery',
    approval: 'run.runtime.alerts.category.approval',
    pressure: 'run.runtime.alerts.category.pressure',
    health: 'run.runtime.alerts.category.health',
  };
  const key = keyByValue[value];
  return key ? t(key) : value;
}
