"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const server_1 = require("react-dom/server");
const react_1 = require("react");
const primitives_1 = require("../../src/renderer/design-system/primitives");
function run() {
    // === Select generates a stable fallback control id when none is provided ===
    {
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(primitives_1.Select, {
            label: 'Sort',
            options: [
                { value: 'newest', label: 'Newest first' },
                { value: 'oldest', label: 'Oldest first' },
            ],
            value: 'newest',
            onChange: () => undefined,
        }));
        const labelMatch = html.match(/<label for="(ds-select-[^"]+)"/);
        const selectMatch = html.match(/<select id="(ds-select-[^"]+)"/);
        strict_1.default.ok(labelMatch, 'expected select label to reference generated id');
        strict_1.default.ok(selectMatch, 'expected select element to expose generated id');
        strict_1.default.equal(labelMatch?.[1], selectMatch?.[1]);
    }
    // === DrawerShell exposes dialog semantics and dismiss label ===
    {
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(primitives_1.DrawerShell, {
            open: true,
            title: 'Inspector',
            description: 'Inspect run metadata.',
            dismissLabel: 'Close inspector',
            onDismiss: () => undefined,
        }, (0, react_1.createElement)('div', null, 'Body')));
        strict_1.default.match(html, /role="dialog"/);
        strict_1.default.match(html, /aria-modal="true"/);
        strict_1.default.match(html, /aria-labelledby="ds-drawer-[^"]+-title"/);
        strict_1.default.match(html, /aria-describedby="ds-drawer-[^"]+-description"/);
        strict_1.default.match(html, /aria-label="Close inspector"/);
    }
    // === Tabs render tablist, selected tab, and panel wiring ===
    {
        const items = [
            { value: 'summary', label: 'Summary', content: 'Summary panel' },
            { value: 'details', label: 'Details', content: 'Details panel' },
        ];
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(primitives_1.Tabs, {
            value: 'details',
            onValueChange: () => undefined,
            items,
        }));
        strict_1.default.match(html, /role="tablist"/);
        strict_1.default.match(html, /role="tab"[^>]*aria-selected="false"/);
        strict_1.default.match(html, /role="tab"[^>]*aria-selected="true"/);
        strict_1.default.match(html, /role="tabpanel"/);
        strict_1.default.match(html, /aria-controls="ds-tabs-[^"]+-panel-details"/);
        strict_1.default.match(html, /aria-labelledby="ds-tabs-[^"]+-tab-details"/);
    }
    // === Tooltip wires describedby and tooltip semantics when open ===
    {
        const tooltipTrigger = (0, react_1.createElement)('button', { type: 'button' }, 'Trigger');
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(primitives_1.Tooltip, {
            content: 'Open workflow settings',
            open: true,
            delayMs: 0,
            children: tooltipTrigger,
        }));
        strict_1.default.match(html, /role="tooltip"/);
        strict_1.default.match(html, /id="ds-tooltip-[^"]+"/);
        strict_1.default.match(html, /aria-describedby="ds-tooltip-[^"]+"/);
    }
    // === Popover exposes dialog trigger wiring and panel semantics when open ===
    {
        const popoverTrigger = (0, react_1.createElement)('button', { type: 'button' }, 'Open');
        const html = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(primitives_1.Popover, {
            open: true,
            title: 'Respond',
            description: 'Provide an approval response.',
            trigger: popoverTrigger,
            children: (0, react_1.createElement)('div', null, 'Body'),
        }));
        strict_1.default.match(html, /aria-haspopup="dialog"/);
        strict_1.default.match(html, /aria-expanded="true"/);
        strict_1.default.match(html, /aria-controls="ds-popover-[^"]+"/);
        strict_1.default.match(html, /role="dialog"/);
        strict_1.default.match(html, /aria-modal="false"/);
        strict_1.default.match(html, /aria-labelledby="ds-popover-[^"]+-title"/);
        strict_1.default.match(html, /aria-describedby="ds-popover-[^"]+-description"/);
    }
    console.log('[contract] PASS design-system-interactive-a11y (5 cases)');
}
run();
