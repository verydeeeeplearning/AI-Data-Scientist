import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  NotificationsPanel,
  statusBadgeClass,
} from '../../src/renderer/components/admin/NotificationsPanel';
import type { RpcFn } from '../../src/renderer/components/settings/types';

const RPC: RpcFn = async (method) => {
  throw new Error(`unexpected NotificationsPanel RPC during static render: ${method}`);
};

function renderPanel(): string {
  return renderToStaticMarkup(createElement(NotificationsPanel, { rpc: RPC }));
}

function readNotificationsPanelSource(): string {
  return readFileSync(
    resolve(
      __dirname,
      '..',
      '..',
      '..',
      '..',
      'src',
      'renderer',
      'components',
      'admin',
      'NotificationsPanel.tsx',
    ),
    'utf8',
  );
}

function run(): void {
  // === Panel shell renders the Telegram pairing flow and delivery-policy editor ===
  {
    const html = renderPanel();

    assert.match(html, /lucide-message-circle/);
    assert.match(html, /aria-label="[^"]*Telegram[^"]*"/);
    assert.match(html, /id="telegram-digest-cadence"/);
    assert.match(html, /<option value="interval"/);
    assert.match(html, /<option value="hourly"/);
    assert.match(html, /<option value="morning"/);
    assert.match(html, /<option value="end_of_day"/);
    assert.match(html, /id="telegram-digest-interval"/);
    assert.match(html, /id="telegram-digest-interval" type="number"/);
    assert.match(html, /id="telegram-digest-timezone"/);
    assert.match(html, /id="telegram-quiet-hours-start"/);
    assert.match(html, /id="telegram-quiet-hours-start" type="time"/);
    assert.match(html, /id="telegram-quiet-hours-end"/);
    assert.match(html, /id="telegram-quiet-hours-end" type="time"/);
    assert.match(html, /id="telegram-quiet-hours-timezone"/);
    assert.match(html, /lucide-hash/);
    assert.match(html, /lucide-mail/);
    assert.match(html, /aria-disabled="true"/);
  }

  // === Runtime status variants use stable badge semantics without jsdom ===
  {
    assert.equal(statusBadgeClass('running', true), 'bg-ds-success/15 text-ds-success');
    assert.equal(statusBadgeClass('error', false), 'bg-ds-error/15 text-ds-error');
    assert.equal(statusBadgeClass('starting', false), 'bg-ds-warning/15 text-ds-warning');
    assert.equal(statusBadgeClass('stopping', false), 'bg-ds-warning/15 text-ds-warning');
    assert.equal(statusBadgeClass('running', false), 'bg-ds-warning/15 text-ds-warning');
    assert.equal(statusBadgeClass('disabled', false), 'bg-ds-bg text-ds-muted');
    assert.equal(statusBadgeClass('unknown', false), 'bg-ds-bg text-ds-muted');
  }

  // === The panel delegates Telegram RPC/state contracts to the dedicated children ===
  {
    const source = readNotificationsPanelSource();

    assert.match(
      source,
      /<TelegramConnectFlow\s+rpc=\{rpc\}\s+embedded\s*\/>/,
      'NotificationsPanel must forward rpc to the pairing flow',
    );
    assert.match(
      source,
      /<TelegramNotificationSettings\s+rpc=\{rpc\}\s*\/>/,
      'NotificationsPanel must forward rpc to the settings editor',
    );
    assert.doesNotMatch(
      source,
      /rpc\(['"]telegram\.(?:ack|mute|digest|quiet|quietHours)/,
      'Alert lifecycle mutations remain owned by Telegram/runtime contracts, not the panel shell',
    );
  }

  console.log('[contract] PASS notifications-panel (24 cases)');
}

run();
