"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const TelegramNotificationSettings_1 = require("../../src/renderer/components/settings/TelegramNotificationSettings");
function run() {
    const preferences = TelegramNotificationSettings_1.__test.parseOperatorPreferences({
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
    strict_1.default.equal(preferences.length, 2);
    strict_1.default.equal(preferences[0]?.chatId, 'beta');
    strict_1.default.equal(preferences[0]?.digestCadence, 'end_of_day');
    strict_1.default.equal(preferences[1]?.chatId, 'alpha');
    strict_1.default.equal(preferences[1]?.digestCadence, 'morning');
    strict_1.default.equal(preferences[1]?.digestIntervalMinutes, 15);
    const policy = TelegramNotificationSettings_1.__test.parseDeliveryPolicy({
        default_policy: {
            digest_enabled: true,
            digest_interval_seconds: 1800,
            quiet_hours_start: '22:00',
            quiet_hours_end: '07:00',
            quiet_hours_timezone: 'America/New_York',
        },
    });
    strict_1.default.deepEqual(policy, {
        digestEnabled: true,
        digestIntervalMinutes: 30,
        quietHoursStart: '22:00',
        quietHoursEnd: '07:00',
        quietHoursTimezone: 'America/New_York',
    });
    const draft = TelegramNotificationSettings_1.__test.buildDraftFromWorkspace(preferences[1] ?? null, policy);
    strict_1.default.deepEqual(draft, {
        digestEnabled: true,
        digestCadence: 'morning',
        digestIntervalMinutes: 15,
        timezone: 'Asia/Seoul',
        quietHoursEnabled: true,
        quietHoursStart: '22:00',
        quietHoursEnd: '07:00',
        quietHoursTimezone: 'America/New_York',
    });
    strict_1.default.equal(TelegramNotificationSettings_1.__test.validateTimeZone('Asia/Seoul', 'invalid'), undefined);
    strict_1.default.equal(TelegramNotificationSettings_1.__test.validateTimeZone('Mars/Base', 'invalid'), 'invalid');
    console.log('[contract] PASS telegram-notification-settings (10 cases)');
}
run();
