import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button, Checkbox, Input, Select } from '../../design-system/primitives';
import {
  type TelegramDigestCadence,
  type TelegramNotificationSettings,
  useConfigStore,
} from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';
import type { RpcFn } from './types';

interface PreviewTextPayload {
  kind?: string;
  content?: unknown;
}

interface WorkspaceOperatorPreference {
  chatId: string;
  digestEnabled: boolean;
  digestCadence: TelegramDigestCadence;
  digestIntervalMinutes: number;
  timezone: string;
  updatedAt: number | null;
}

interface WorkspaceDeliveryPolicy {
  digestEnabled: boolean;
  digestIntervalMinutes: number;
  quietHoursStart: string;
  quietHoursEnd: string;
  quietHoursTimezone: string;
}

interface WorkspaceTelegramSnapshot {
  chatPreferences: WorkspaceOperatorPreference[];
  deliveryPolicy: WorkspaceDeliveryPolicy | null;
}

const DIGEST_CADENCE_OPTIONS: ReadonlyArray<{
  value: TelegramDigestCadence;
  labelKey: string;
}> = [
  { value: 'interval', labelKey: 'settings.telegram.digestCadence.interval' },
  { value: 'hourly', labelKey: 'settings.telegram.digestCadence.hourly' },
  { value: 'morning', labelKey: 'settings.telegram.digestCadence.morning' },
  { value: 'end_of_day', labelKey: 'settings.telegram.digestCadence.endOfDay' },
];

const DEFAULT_FALLBACK_TIMEZONE = 'UTC';

export function TelegramNotificationSettings({ rpc }: { rpc: RpcFn }) {
  const { t, locale } = useI18n();
  const settings = useConfigStore((state) => state.telegramNotificationSettings);
  const source = useConfigStore((state) => state.telegramNotificationSettingsSource);
  const updateSettings = useConfigStore((state) => state.updateTelegramNotificationSettings);
  const hydrateFromWorkspace = useConfigStore(
    (state) => state.hydrateTelegramNotificationSettingsFromWorkspace,
  );
  const replaceSettings = useConfigStore((state) => state.replaceTelegramNotificationSettings);
  const resetSettings = useConfigStore((state) => state.resetTelegramNotificationSettings);

  const [snapshot, setSnapshot] = useState<WorkspaceTelegramSnapshot | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const selectedPreference = useMemo(() => {
    if (!snapshot?.chatPreferences.length) {
      return null;
    }
    return (
      snapshot.chatPreferences.find((entry) => entry.chatId === selectedChatId)
      ?? snapshot.chatPreferences[0]
    );
  }, [selectedChatId, snapshot?.chatPreferences]);

  const snapshotDraft = useMemo(
    () => buildDraftFromWorkspace(selectedPreference, snapshot?.deliveryPolicy ?? null),
    [selectedPreference, snapshot?.deliveryPolicy],
  );

  const timezoneError = useMemo(
    () => validateTimeZone(settings.timezone, t('settings.telegram.timezone.invalid')),
    [settings.timezone, t],
  );
  const quietHoursTimezoneError = useMemo(
    () =>
      validateTimeZone(
        settings.quietHoursTimezone,
        t('settings.telegram.timezone.invalid'),
      ),
    [settings.quietHoursTimezone, t],
  );

  const refreshSnapshot = useCallback(async () => {
    setLoading(true);
    setLoadError(null);

    const [preferencesResult, policyResult] = await Promise.all([
      loadWorkspaceJsonSnapshot(rpc, '.ds_agent/operator_preferences.json'),
      loadWorkspaceJsonSnapshot(rpc, '.ds_agent/delivery_policy.json'),
    ]);

    const nextSnapshot: WorkspaceTelegramSnapshot = {
      chatPreferences: parseOperatorPreferences(preferencesResult.data),
      deliveryPolicy: parseDeliveryPolicy(policyResult.data),
    };

    const errors = [preferencesResult.error, policyResult.error].filter(
      (value): value is string => Boolean(value),
    );

    setSnapshot(nextSnapshot);
    setSelectedChatId((current) => {
      if (
        current
        && nextSnapshot.chatPreferences.some((entry) => entry.chatId === current)
      ) {
        return current;
      }
      return nextSnapshot.chatPreferences[0]?.chatId ?? '';
    });
    setLoadError(errors[0] ?? null);
    setLoading(false);
  }, [rpc]);

  useEffect(() => {
    void refreshSnapshot();
  }, [refreshSnapshot]);

  useEffect(() => {
    if (!snapshotDraft) {
      return;
    }
    hydrateFromWorkspace(snapshotDraft);
  }, [hydrateFromWorkspace, snapshotDraft]);

  const sourceLabelKey =
    source === 'local'
      ? 'settings.telegram.editor.source.local'
      : source === 'workspace'
        ? 'settings.telegram.editor.source.workspace'
        : 'settings.telegram.editor.source.default';

  const copySnapshotToEditor = () => {
    if (!snapshotDraft) {
      return;
    }
    replaceSettings(snapshotDraft, 'workspace');
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="text-xs font-medium text-ds-text">
              {t('settings.telegram.title')}
            </div>
            <p className="text-[11px] leading-5 text-ds-muted">
              {t('settings.telegram.description')}
            </p>
          </div>
          <span className="rounded-full bg-ds-surface px-2 py-1 text-[10px] font-medium text-ds-muted">
            {t(sourceLabelKey)}
          </span>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-ds-muted">
          {t('settings.telegram.localOnly')}
        </p>
      </div>

      <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-medium text-ds-text">
              {t('settings.telegram.snapshot.title')}
            </div>
            <p className="mt-1 text-[11px] leading-5 text-ds-muted">
              {t('settings.telegram.snapshot.description')}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void refreshSnapshot()} loading={loading}>
            {t('settings.telegram.snapshot.refresh')}
          </Button>
        </div>

        {loadError ? (
          <div className="mt-3 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error">
            {loadError}
          </div>
        ) : null}

        {snapshot?.chatPreferences.length ? (
          <div className="mt-3 space-y-3">
            <Select
              id="telegram-snapshot-chat"
              label={t('settings.telegram.snapshot.chat')}
              description={t('settings.telegram.snapshot.chatDescription')}
              value={selectedPreference?.chatId ?? ''}
              onChange={(event) => setSelectedChatId(event.target.value)}
              options={snapshot.chatPreferences.map((entry) => ({
                value: entry.chatId,
                label: entry.chatId,
              }))}
            />
            <SnapshotRow
              label={t('settings.telegram.snapshot.digest')}
              value={formatDigestSummary(selectedPreference, t)}
            />
            <SnapshotRow
              label={t('settings.telegram.snapshot.quietHours')}
              value={formatQuietHoursSummary(snapshot.deliveryPolicy, t)}
            />
            <SnapshotRow
              label={t('settings.telegram.snapshot.policy')}
              value={formatPolicySummary(snapshot.deliveryPolicy, t)}
            />
            {selectedPreference?.updatedAt ? (
              <SnapshotRow
                label={t('settings.telegram.snapshot.updated')}
                value={new Date(selectedPreference.updatedAt * 1000).toLocaleString(locale)}
              />
            ) : null}
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                variant="secondary"
                size="sm"
                onClick={copySnapshotToEditor}
                disabled={!snapshotDraft}
              >
                {t('settings.telegram.snapshot.copy')}
              </Button>
              <Button variant="ghost" size="sm" onClick={resetSettings}>
                {t('settings.telegram.editor.reset')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-3 rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px] leading-5 text-ds-muted">
            {snapshot?.deliveryPolicy
              ? t('settings.telegram.snapshot.policyOnly')
              : t('settings.telegram.snapshot.empty')}
          </div>
        )}
      </div>

      <div className="space-y-4 rounded-lg border border-ds-border bg-ds-bg p-3">
        <div>
          <div className="text-xs font-medium text-ds-text">
            {t('settings.telegram.editor.title')}
          </div>
          <p className="mt-1 text-[11px] leading-5 text-ds-muted">
            {t('settings.telegram.editor.description')}
          </p>
        </div>

        <Checkbox
          checked={settings.digestEnabled}
          onChange={(event) =>
            updateSettings({
              digestEnabled: event.target.checked,
            })
          }
          label={t('settings.telegram.editor.digestEnabled')}
          description={t('settings.telegram.editor.digestEnabledDescription')}
        />

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
          <Select
            id="telegram-digest-cadence"
            label={t('settings.telegram.editor.digestCadence')}
            description={t('settings.telegram.editor.digestCadenceDescription')}
            value={settings.digestCadence}
            onChange={(event) =>
              updateSettings({
                digestCadence: event.target.value as TelegramDigestCadence,
              })
            }
            options={DIGEST_CADENCE_OPTIONS.map((option) => ({
              value: option.value,
              label: t(option.labelKey),
            }))}
          />

          <Input
            id="telegram-digest-interval"
            type="number"
            min={1}
            step={1}
            label={t('settings.telegram.editor.digestInterval')}
            description={t('settings.telegram.editor.digestIntervalDescription')}
            value={String(settings.digestIntervalMinutes)}
            onChange={(event) =>
              updateSettings({
                digestIntervalMinutes: normalizeIntervalMinutes(event.target.value),
              })
            }
            disabled={settings.digestCadence !== 'interval'}
          />
        </div>

        <Input
          id="telegram-digest-timezone"
          label={t('settings.telegram.editor.timezone')}
          description={t('settings.telegram.editor.timezoneDescription')}
          value={settings.timezone}
          onChange={(event) =>
            updateSettings({
              timezone: event.target.value,
            })
          }
          errorMessage={timezoneError}
          placeholder={t('settings.telegram.timezone.placeholder')}
        />

        <Checkbox
          checked={settings.quietHoursEnabled}
          onChange={(event) =>
            updateSettings({
              quietHoursEnabled: event.target.checked,
            })
          }
          label={t('settings.telegram.editor.quietHoursEnabled')}
          description={t('settings.telegram.editor.quietHoursEnabledDescription')}
        />

        <div className="grid gap-3 md:grid-cols-3">
          <Input
            id="telegram-quiet-hours-start"
            type="time"
            label={t('settings.telegram.editor.quietHoursStart')}
            value={settings.quietHoursStart}
            onChange={(event) =>
              updateSettings({
                quietHoursStart: normalizeTimeValue(event.target.value, settings.quietHoursStart),
              })
            }
            disabled={!settings.quietHoursEnabled}
          />
          <Input
            id="telegram-quiet-hours-end"
            type="time"
            label={t('settings.telegram.editor.quietHoursEnd')}
            value={settings.quietHoursEnd}
            onChange={(event) =>
              updateSettings({
                quietHoursEnd: normalizeTimeValue(event.target.value, settings.quietHoursEnd),
              })
            }
            disabled={!settings.quietHoursEnabled}
          />
          <Input
            id="telegram-quiet-hours-timezone"
            label={t('settings.telegram.editor.quietHoursTimezone')}
            value={settings.quietHoursTimezone}
            onChange={(event) =>
              updateSettings({
                quietHoursTimezone: event.target.value,
              })
            }
            errorMessage={settings.quietHoursEnabled ? quietHoursTimezoneError : undefined}
            placeholder={t('settings.telegram.timezone.placeholder')}
            disabled={!settings.quietHoursEnabled}
          />
        </div>

        <div className="rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">
            {t('settings.telegram.editor.summary')}
          </div>
          <div className="mt-1 text-[11px] text-ds-text">
            {formatEditorSummary(settings, t)}
          </div>
        </div>
      </div>
    </div>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px]">
      <span className="text-ds-muted">{label}</span>
      <span className="font-medium text-ds-text">{value}</span>
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeCadence(value: unknown): TelegramDigestCadence {
  if (typeof value !== 'string') {
    return 'interval';
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === 'hourly') {
    return 'hourly';
  }
  if (normalized === 'morning') {
    return 'morning';
  }
  if (normalized === 'eod' || normalized === 'end-of-day' || normalized === 'end_of_day') {
    return 'end_of_day';
  }
  return 'interval';
}

function normalizeIntervalMinutes(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(1, Math.round(value));
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return Math.max(1, parsed);
    }
  }
  return 15;
}

function normalizeIntervalSeconds(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 15;
  }
  return Math.max(1, Math.round(value / 60));
}

function normalizeTimeValue(value: unknown, fallback: string): string {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  return /^\d{2}:\d{2}$/.test(trimmed) ? trimmed : fallback;
}

function validateTimeZone(value: string, message: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return message;
  }
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: trimmed });
    return undefined;
  } catch {
    return message;
  }
}

function parseOperatorPreferences(raw: unknown): WorkspaceOperatorPreference[] {
  if (!isRecord(raw)) {
    return [];
  }

  return Object.entries(raw)
    .map(([chatId, value]) => {
      if (!isRecord(value)) {
        return null;
      }
      return {
        chatId: String(value.chat_id ?? chatId),
        digestEnabled: Boolean(value.digest_mode),
        digestCadence: normalizeCadence(value.digest_cadence),
        digestIntervalMinutes: normalizeIntervalSeconds(value.digest_interval_seconds),
        timezone:
          typeof value.timezone === 'string' && value.timezone.trim()
            ? value.timezone.trim()
            : DEFAULT_FALLBACK_TIMEZONE,
        updatedAt:
          typeof value.updated_at === 'number' && Number.isFinite(value.updated_at)
            ? value.updated_at
            : null,
      };
    })
    .filter((entry): entry is WorkspaceOperatorPreference => Boolean(entry))
    .sort((left, right) => {
      const leftUpdated = left.updatedAt ?? 0;
      const rightUpdated = right.updatedAt ?? 0;
      if (leftUpdated !== rightUpdated) {
        return rightUpdated - leftUpdated;
      }
      return left.chatId.localeCompare(right.chatId);
    });
}

function parseDeliveryPolicy(raw: unknown): WorkspaceDeliveryPolicy | null {
  if (!isRecord(raw)) {
    return null;
  }
  const payload = isRecord(raw.default_policy) ? raw.default_policy : raw;
  return {
    digestEnabled: Boolean(payload.digest_enabled),
    digestIntervalMinutes: normalizeIntervalSeconds(payload.digest_interval_seconds),
    quietHoursStart: normalizeTimeValue(payload.quiet_hours_start, ''),
    quietHoursEnd: normalizeTimeValue(payload.quiet_hours_end, ''),
    quietHoursTimezone:
      typeof payload.quiet_hours_timezone === 'string' && payload.quiet_hours_timezone.trim()
        ? payload.quiet_hours_timezone.trim()
        : DEFAULT_FALLBACK_TIMEZONE,
  };
}

function buildDraftFromWorkspace(
  preference: WorkspaceOperatorPreference | null,
  policy: WorkspaceDeliveryPolicy | null,
): TelegramNotificationSettings | null {
  if (!preference && !policy) {
    return null;
  }

  const digestTimeZone =
    preference?.timezone
    ?? policy?.quietHoursTimezone
    ?? DEFAULT_FALLBACK_TIMEZONE;
  const quietHoursEnabled = Boolean(policy?.quietHoursStart && policy?.quietHoursEnd);

  return {
    digestEnabled: preference?.digestEnabled ?? false,
    digestCadence: preference?.digestCadence ?? 'interval',
    digestIntervalMinutes:
      preference?.digestIntervalMinutes ?? policy?.digestIntervalMinutes ?? 15,
    timezone: digestTimeZone,
    quietHoursEnabled,
    quietHoursStart: policy?.quietHoursStart || '22:00',
    quietHoursEnd: policy?.quietHoursEnd || '07:00',
    quietHoursTimezone: policy?.quietHoursTimezone || digestTimeZone,
  };
}

async function loadWorkspaceJsonSnapshot(
  rpc: RpcFn,
  path: string,
): Promise<{ data: unknown; error: string | null }> {
  try {
    const preview = (await rpc('files.preview', { path })) as PreviewTextPayload;
    if (preview.kind !== 'text' || typeof preview.content !== 'string') {
      return {
        data: null,
        error: `Unsupported preview payload for ${path}.`,
      };
    }
    return {
      data: JSON.parse(preview.content),
      error: null,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes('No such file')) {
      return { data: null, error: null };
    }
    return {
      data: null,
      error: message,
    };
  }
}

function formatCadenceLabel(
  cadence: TelegramDigestCadence,
  intervalMinutes: number,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (cadence === 'interval') {
    return t('settings.telegram.digestCadence.intervalSummary', {
      minutes: intervalMinutes,
    });
  }
  return t(
    `settings.telegram.digestCadence.${cadence === 'end_of_day' ? 'endOfDay' : cadence}`,
  );
}

function formatDigestSummary(
  preference: WorkspaceOperatorPreference | null,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (!preference) {
    return t('settings.telegram.snapshot.unavailable');
  }
  if (!preference.digestEnabled) {
    return t('settings.telegram.snapshot.digestDisabled', {
      timezone: preference.timezone,
    });
  }
  return t('settings.telegram.snapshot.digestEnabled', {
    cadence: formatCadenceLabel(
      preference.digestCadence,
      preference.digestIntervalMinutes,
      t,
    ),
    timezone: preference.timezone,
  });
}

function formatPolicySummary(
  policy: WorkspaceDeliveryPolicy | null,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (!policy) {
    return t('settings.telegram.snapshot.unavailable');
  }
  if (!policy.digestEnabled) {
    return t('settings.telegram.snapshot.policyDigestDisabled');
  }
  return t('settings.telegram.snapshot.policyDigestEnabled', {
    cadence: formatCadenceLabel('interval', policy.digestIntervalMinutes, t),
  });
}

function formatQuietHoursSummary(
  policy: WorkspaceDeliveryPolicy | null,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (!policy) {
    return t('settings.telegram.snapshot.unavailable');
  }
  if (!policy.quietHoursStart || !policy.quietHoursEnd) {
    return t('settings.telegram.snapshot.quietHoursDisabled');
  }
  return t('settings.telegram.snapshot.quietHoursEnabled', {
    start: policy.quietHoursStart,
    end: policy.quietHoursEnd,
    timezone: policy.quietHoursTimezone,
  });
}

function formatEditorSummary(
  settings: TelegramNotificationSettings,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  const digestSummary = settings.digestEnabled
    ? t('settings.telegram.editor.digestSummaryEnabled', {
        cadence: formatCadenceLabel(
          settings.digestCadence,
          settings.digestIntervalMinutes,
          t,
        ),
        timezone: settings.timezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
      })
    : t('settings.telegram.editor.digestSummaryDisabled', {
        timezone: settings.timezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
      });

  const quietHoursSummary = settings.quietHoursEnabled
    ? t('settings.telegram.editor.quietHoursSummaryEnabled', {
        start: settings.quietHoursStart,
        end: settings.quietHoursEnd,
        timezone: settings.quietHoursTimezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
      })
    : t('settings.telegram.editor.quietHoursSummaryDisabled');

  return `${digestSummary} | ${quietHoursSummary}`;
}

export const __test = {
  buildDraftFromWorkspace,
  parseDeliveryPolicy,
  parseOperatorPreferences,
  validateTimeZone,
};
