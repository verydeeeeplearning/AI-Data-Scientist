import assert from 'node:assert/strict';

import { __test } from '../../src/renderer/components/settings/TelegramNotificationSettings';

function run(): void {
  const preferences = __test.parseOperatorPreferences({
    alpha: {
      digest_mode: true,
      digest_cadence: 'morning',
      digest_interval_seconds: 900,
      timezone: 'Asia/Seoul',
      updated_at: 50,
    },
    beta: {
      digest_mode: false,
      digest_cadence: 'end-of-day',
      digest_interval_seconds: 3600,
      timezone: 'UTC',
      updated_at: 100,
    },
  });

  assert.equal(preferences.length, 2);
  assert.equal(preferences[0]?.chatId, 'beta');
  assert.equal(preferences[0]?.digestCadence, 'end_of_day');
  assert.equal(preferences[1]?.chatId, 'alpha');
  assert.equal(preferences[1]?.digestCadence, 'morning');
  assert.equal(preferences[1]?.digestIntervalMinutes, 15);

  const policy = __test.parseDeliveryPolicy({
    default_policy: {
      digest_enabled: true,
      digest_interval_seconds: 1800,
      quiet_hours_start: '22:00',
      quiet_hours_end: '07:00',
      quiet_hours_timezone: 'America/New_York',
    },
  });

  assert.deepEqual(policy, {
    digestEnabled: true,
    digestIntervalMinutes: 30,
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00',
    quietHoursTimezone: 'America/New_York',
  });

  const draft = __test.buildDraftFromWorkspace(preferences[1] ?? null, policy);

  assert.deepEqual(draft, {
    digestEnabled: true,
    digestCadence: 'morning',
    digestIntervalMinutes: 15,
    timezone: 'Asia/Seoul',
    quietHoursEnabled: true,
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00',
    quietHoursTimezone: 'America/New_York',
  });

  assert.equal(__test.validateTimeZone('Asia/Seoul', 'invalid'), undefined);
  assert.equal(__test.validateTimeZone('Mars/Base', 'invalid'), 'invalid');

  console.log('[contract] PASS telegram-notification-settings (10 cases)');
}

run();
