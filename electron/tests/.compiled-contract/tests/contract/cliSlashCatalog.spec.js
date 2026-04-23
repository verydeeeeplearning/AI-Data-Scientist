"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = __importDefault(require("node:fs"));
const node_path_1 = __importDefault(require("node:path"));
const cliSlashCatalog_1 = require("../../src/renderer/domain/command/cliSlashCatalog");
const EXPECTED_CLI_ONLY_SLASHES = ['/history', '/clear', '/quit'];
const I18N_KEY_PATTERN = /^(?:cmd|command)[.:]/;
function isNonEmptyString(value) {
    return typeof value === 'string' && value.length > 0;
}
function resolveCliCommandsPath() {
    const candidates = [
        node_path_1.default.resolve(process.cwd(), '../src/ds_agent/cli/commands.py'),
        node_path_1.default.resolve(process.cwd(), 'src/ds_agent/cli/commands.py'),
    ];
    for (const candidate of candidates) {
        if (node_fs_1.default.existsSync(candidate)) {
            return candidate;
        }
    }
    throw new Error('Could not locate src/ds_agent/cli/commands.py from the contract test');
}
function uniqueSorted(values) {
    return [...new Set(values)].sort();
}
function extractHelpTextCommands(source) {
    const helpMatch = source.match(/HELP_TEXT = """\\\r?\n([\s\S]*?)"""/);
    strict_1.default.ok(helpMatch, 'HELP_TEXT block must exist in src/ds_agent/cli/commands.py');
    return uniqueSorted(helpMatch[1]
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith('/'))
        .map((line) => line.split(/\s+/, 1)[0] ?? '')
        .filter(isNonEmptyString));
}
function extractHandledCommands(source) {
    const exactMatches = [...source.matchAll(/if cmd == "([^"]+)":/g)].map((match) => match[1]);
    const groupedMatches = [...source.matchAll(/if cmd in \(([^)]+)\):/g)].flatMap((match) => [...match[1].matchAll(/"([^"]+)"/g)].map((tokenMatch) => tokenMatch[1]));
    return uniqueSorted([...exactMatches, ...groupedMatches]);
}
function run() {
    let cases = 0;
    const cliCommandsSource = node_fs_1.default.readFileSync(resolveCliCommandsPath(), 'utf8');
    const helpCommands = extractHelpTextCommands(cliCommandsSource);
    const handledCommands = extractHandledCommands(cliCommandsSource);
    // === catalog is non-empty and every entry is structurally valid ===
    {
        strict_1.default.ok(cliSlashCatalog_1.CLI_SLASH_CATALOG.length > 0, 'catalog must not be empty');
        for (const entry of cliSlashCatalog_1.CLI_SLASH_CATALOG) {
            strict_1.default.ok(isNonEmptyString(entry.id), `entry.id must be a non-empty string (got ${String(entry.id)})`);
            strict_1.default.ok(isNonEmptyString(entry.slash), `entry.slash must be non-empty for ${entry.id}`);
            strict_1.default.ok(entry.slash.startsWith('/'), `entry.slash must start with '/' for ${entry.id}`);
            strict_1.default.ok(isNonEmptyString(entry.labelKey), `entry.labelKey must be non-empty for ${entry.id}`);
            strict_1.default.ok(isNonEmptyString(entry.descriptionKey), `entry.descriptionKey must be non-empty for ${entry.id}`);
            strict_1.default.equal(typeof entry.prompt, 'string', `entry.prompt must be a string for ${entry.id}`);
            strict_1.default.ok(Array.isArray(entry.searchTerms), `entry.searchTerms must be an array for ${entry.id}`);
            if (entry.aliases) {
                strict_1.default.ok(Array.isArray(entry.aliases), `entry.aliases must be an array for ${entry.id}`);
                for (const alias of entry.aliases) {
                    strict_1.default.ok(isNonEmptyString(alias), `entry.aliases must contain only non-empty strings for ${entry.id}`);
                    strict_1.default.ok(alias.startsWith('/'), `entry alias must start with '/' for ${entry.id} (got ${alias})`);
                }
            }
        }
        cases += 1;
    }
    // === ids and all slash tokens are unique across the catalog ===
    {
        const seenIds = new Set();
        const seenTokens = new Set();
        for (const entry of cliSlashCatalog_1.CLI_SLASH_CATALOG) {
            strict_1.default.ok(!seenIds.has(entry.id), `duplicate id in catalog: ${entry.id}`);
            seenIds.add(entry.id);
            for (const token of (0, cliSlashCatalog_1.slashTokensForEntry)(entry)) {
                strict_1.default.ok(!seenTokens.has(token), `duplicate slash token in catalog: ${token}`);
                seenTokens.add(token);
            }
        }
        cases += 1;
    }
    // === canonical catalog slashes match the Python CLI help table exactly ===
    {
        const catalogCanonicalSlashes = uniqueSorted(cliSlashCatalog_1.CLI_SLASH_CATALOG.map((entry) => entry.slash));
        strict_1.default.deepEqual(catalogCanonicalSlashes, helpCommands, 'catalog canonical slashes must stay in sync with src/ds_agent/cli/commands.py HELP_TEXT');
        cases += 1;
    }
    // === canonical slashes plus aliases match the Python handler tokens exactly ===
    {
        const catalogTokens = uniqueSorted(cliSlashCatalog_1.CLI_SLASH_CATALOG.flatMap((entry) => [...(0, cliSlashCatalog_1.slashTokensForEntry)(entry)]));
        strict_1.default.deepEqual(catalogTokens, handledCommands, 'catalog slash tokens must stay in sync with src/ds_agent/cli/commands.py handle_slash_command');
        cases += 1;
    }
    // === cliOnly entries are exactly the palette-excluded canonical commands ===
    {
        const cliOnlyCanonicalSlashes = uniqueSorted(cliSlashCatalog_1.CLI_SLASH_CATALOG
            .filter((entry) => entry.cliOnly === true)
            .map((entry) => entry.slash));
        strict_1.default.deepEqual(cliOnlyCanonicalSlashes, uniqueSorted(EXPECTED_CLI_ONLY_SLASHES), 'cliOnly canonical slash set must remain explicit and reviewable');
        const expectedPaletteSlashes = helpCommands.filter((slash) => !EXPECTED_CLI_ONLY_SLASHES.includes(slash));
        strict_1.default.deepEqual(uniqueSorted(cliSlashCatalog_1.PALETTE_SLASH_ENTRIES.map((entry) => entry.slash)), uniqueSorted(expectedPaletteSlashes), 'palette-visible entries must equal the CLI help table minus the explicit CLI-only set');
        cases += 1;
    }
    // === helper output matches the runtime constant and honors arbitrary input ===
    {
        const filtered = (0, cliSlashCatalog_1.paletteVisibleSlashEntries)();
        strict_1.default.deepEqual(filtered.map((entry) => entry.id), cliSlashCatalog_1.PALETTE_SLASH_ENTRIES.map((entry) => entry.id), 'paletteVisibleSlashEntries() must match PALETTE_SLASH_ENTRIES');
        const synthetic = [
            {
                id: 'slash:keep',
                slash: '/keep',
                labelKey: 'cmd:slash.keep.label',
                descriptionKey: 'cmd:slash.keep.description',
                searchTerms: [],
                prompt: 'noop',
            },
            {
                id: 'slash:drop',
                slash: '/drop',
                aliases: ['/drop-now'],
                labelKey: 'cmd:slash.drop.label',
                descriptionKey: 'cmd:slash.drop.description',
                searchTerms: [],
                prompt: '',
                cliOnly: true,
            },
        ];
        const syntheticFiltered = (0, cliSlashCatalog_1.paletteVisibleSlashEntries)(synthetic);
        strict_1.default.deepEqual(syntheticFiltered.map((entry) => entry.id), ['slash:keep'], 'helper must drop cliOnly entries from arbitrary catalog input');
        cases += 1;
    }
    // === labelKey and descriptionKey stay in the command namespace ===
    {
        for (const entry of cliSlashCatalog_1.CLI_SLASH_CATALOG) {
            strict_1.default.ok(I18N_KEY_PATTERN.test(entry.labelKey), `labelKey must start with 'cmd.' / 'command.' / 'cmd:' / 'command:' for ${entry.id} (got ${entry.labelKey})`);
            strict_1.default.ok(I18N_KEY_PATTERN.test(entry.descriptionKey), `descriptionKey must start with 'cmd.' / 'command.' / 'cmd:' / 'command:' for ${entry.id} (got ${entry.descriptionKey})`);
        }
        cases += 1;
    }
    console.log(`[contract] PASS cli-slash-catalog (${cases} cases)`);
}
run();
