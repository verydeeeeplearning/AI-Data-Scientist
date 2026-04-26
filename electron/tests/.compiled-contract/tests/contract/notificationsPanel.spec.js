"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = require("node:fs");
const node_path_1 = require("node:path");
const react_1 = require("react");
const server_1 = require("react-dom/server");
const NotificationsPanel_1 = require("../../src/renderer/components/admin/NotificationsPanel");
const RPC = async (method) => {
    throw new Error(`unexpected NotificationsPanel RPC during static render: ${method}`);
};
function renderPanel() {
    return (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(NotificationsPanel_1.NotificationsPanel, { rpc: RPC }));
}
function readNotificationsPanelSource() {
    return (0, node_fs_1.readFileSync)((0, node_path_1.resolve)(__dirname, '..', '..', '..', '..', 'src', 'renderer', 'components', 'admin', 'NotificationsPanel.tsx'), 'utf8');
}
function run() {
    // === Panel shell renders the Telegram pairing flow and delivery-policy editor ===
    {
        const html = renderPanel();
        strict_1.default.match(html, /lucide-message-circle/);
        strict_1.default.match(html, /aria-label="[^"]*Telegram[^"]*"/);
        strict_1.default.match(html, /id="telegram-digest-cadence"/);
        strict_1.default.match(html, /<option value="interval"/);
        strict_1.default.match(html, /<option value="hourly"/);
        strict_1.default.match(html, /<option value="morning"/);
        strict_1.default.match(html, /<option value="end_of_day"/);
        strict_1.default.match(html, /id="telegram-digest-interval"/);
        strict_1.default.match(html, /id="telegram-digest-interval" type="number"/);
        strict_1.default.match(html, /id="telegram-digest-timezone"/);
        strict_1.default.match(html, /id="telegram-quiet-hours-start"/);
        strict_1.default.match(html, /id="telegram-quiet-hours-start" type="time"/);
        strict_1.default.match(html, /id="telegram-quiet-hours-end"/);
        strict_1.default.match(html, /id="telegram-quiet-hours-end" type="time"/);
        strict_1.default.match(html, /id="telegram-quiet-hours-timezone"/);
        strict_1.default.match(html, /lucide-hash/);
        strict_1.default.match(html, /lucide-mail/);
        strict_1.default.match(html, /aria-disabled="true"/);
    }
    // === Runtime status variants use stable badge semantics without jsdom ===
    {
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('running', true), 'bg-ds-success/15 text-ds-success');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('error', false), 'bg-ds-error/15 text-ds-error');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('starting', false), 'bg-ds-warning/15 text-ds-warning');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('stopping', false), 'bg-ds-warning/15 text-ds-warning');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('running', false), 'bg-ds-warning/15 text-ds-warning');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('disabled', false), 'bg-ds-bg text-ds-muted');
        strict_1.default.equal((0, NotificationsPanel_1.statusBadgeClass)('unknown', false), 'bg-ds-bg text-ds-muted');
    }
    // === The panel delegates Telegram RPC/state contracts to the dedicated children ===
    {
        const source = readNotificationsPanelSource();
        strict_1.default.match(source, /<TelegramConnectFlow\s+rpc=\{rpc\}\s+embedded\s*\/>/, 'NotificationsPanel must forward rpc to the pairing flow');
        strict_1.default.match(source, /<TelegramNotificationSettings\s+rpc=\{rpc\}\s*\/>/, 'NotificationsPanel must forward rpc to the settings editor');
        strict_1.default.doesNotMatch(source, /rpc\(['"]telegram\.(?:ack|mute|digest|quiet|quietHours)/, 'Alert lifecycle mutations remain owned by Telegram/runtime contracts, not the panel shell');
    }
    console.log('[contract] PASS notifications-panel (24 cases)');
}
run();
