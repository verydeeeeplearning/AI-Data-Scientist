"use strict";
/**
 * CLI slash command catalog (single source of truth for the palette).
 *
 * This catalog mirrors the slash commands implemented by the Python CLI in
 * `src/ds_agent/cli/commands.py`. Entries flagged `cliOnly: true` are CLI-only
 * actions (e.g. `/clear`, `/quit`) that do not make sense as palette entries
 * and are therefore excluded from the GUI surface. Everything else is exposed
 * to the Command Palette as a safe natural-language prompt sent to the
 * mission chat — the Electron surface does not yet implement the CLI parser,
 * so we deliberately route through the existing chat transport instead of
 * pretending the slash dispatch table runs in the renderer.
 *
 * Pure data module — no React, no I/O, no stores, no framework imports.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.PALETTE_SLASH_ENTRIES = exports.CLI_SLASH_CATALOG = void 0;
exports.paletteVisibleSlashEntries = paletteVisibleSlashEntries;
exports.parseCliSlashInput = parseCliSlashInput;
exports.slashTokensForEntry = slashTokensForEntry;
exports.findCliSlashEntry = findCliSlashEntry;
exports.buildCliSlashPrompt = buildCliSlashPrompt;
exports.CLI_SLASH_CATALOG = [
    {
        id: 'slash:help',
        slash: '/help',
        labelKey: 'cmd:slash.help.label',
        descriptionKey: 'cmd:slash.help.description',
        searchTerms: ['help', 'shortcuts', 'operator'],
        prompt: 'Summarize the most useful operator-facing commands, controls, and next actions available in this session. Keep it concise.',
    },
    {
        id: 'slash:status',
        slash: '/status',
        labelKey: 'cmd:slash.status.label',
        descriptionKey: 'cmd:slash.status.description',
        searchTerms: ['status', 'progress', 'cost', 'steps'],
        prompt: 'Summarize the current project status, active step, recent progress, and cost or budget state in a concise operator update.',
    },
    {
        id: 'slash:files',
        slash: '/files',
        labelKey: 'cmd:slash.files.label',
        descriptionKey: 'cmd:slash.files.description',
        searchTerms: ['files', 'artifacts', 'workspace'],
        prompt: 'List the most relevant artifacts and workspace files produced so far, and briefly explain which ones matter next.',
    },
    {
        id: 'slash:budget',
        slash: '/budget',
        labelKey: 'cmd:slash.budget.label',
        descriptionKey: 'cmd:slash.budget.description',
        searchTerms: ['budget', 'cost', 'spend', 'usage'],
        prompt: 'Summarize the current budget usage, burn rate, and any budget risk the operator should know about.',
    },
    {
        id: 'slash:contract',
        slash: '/contract',
        labelKey: 'cmd:slash.contract.label',
        descriptionKey: 'cmd:slash.contract.description',
        searchTerms: ['contract', 'constraints', 'guardrails'],
        prompt: 'Summarize the active task contract, mission constraints, approval boundaries, and any current execution guardrails.',
    },
    {
        id: 'slash:verdict',
        slash: '/verdict',
        labelKey: 'cmd:slash.verdict.label',
        descriptionKey: 'cmd:slash.verdict.description',
        searchTerms: ['verdict', 'review', 'shadow', 'compare'],
        prompt: 'Summarize the latest verifier verdict or shadow comparison outcome for this session, including the key reasons and any follow-up action.',
    },
    {
        id: 'slash:mode',
        slash: '/mode',
        labelKey: 'cmd:slash.mode.label',
        descriptionKey: 'cmd:slash.mode.description',
        searchTerms: ['mode', 'auto', 'supervised', 'step', 'autonomy'],
        prompt: 'Explain the current execution mode (auto / supervised / step-by-step), why it was chosen, and recommend whether to switch.',
    },
    {
        id: 'slash:model',
        slash: '/model',
        labelKey: 'cmd:slash.model.label',
        descriptionKey: 'cmd:slash.model.description',
        searchTerms: ['model', 'llm', 'provider', 'switch'],
        prompt: 'Report the current LLM model in use, why it is appropriate for the active task, and suggest a switch if a better option fits.',
    },
    {
        id: 'slash:certification',
        slash: '/certification',
        labelKey: 'cmd:slash.certification.label',
        descriptionKey: 'cmd:slash.certification.description',
        searchTerms: ['certification', 'mission', 'release', 'gate'],
        prompt: 'Summarize the mission certification status, including any blockers, pending gates, or recommended next actions for release readiness.',
    },
    {
        id: 'slash:history',
        slash: '/history',
        labelKey: 'cmd:slash.history.label',
        descriptionKey: 'cmd:slash.history.description',
        searchTerms: ['history', 'transcript', 'log'],
        prompt: '',
        cliOnly: true,
    },
    {
        id: 'slash:clear',
        slash: '/clear',
        labelKey: 'cmd:slash.clear.label',
        descriptionKey: 'cmd:slash.clear.description',
        searchTerms: ['clear', 'reset', 'screen'],
        prompt: '',
        cliOnly: true,
    },
    {
        id: 'slash:quit',
        slash: '/quit',
        aliases: ['/exit', '/q'],
        labelKey: 'cmd:slash.quit.label',
        descriptionKey: 'cmd:slash.quit.description',
        searchTerms: ['quit', 'exit', 'q'],
        prompt: '',
        cliOnly: true,
    },
];
/**
 * Pure filter that returns the palette-visible subset of the catalog.
 *
 * Defined as an exported helper so contract tests can assert that the
 * `cliOnly` flag is honoured with the same logic the production palette
 * uses. The runtime `PALETTE_SLASH_ENTRIES` constant is computed once at
 * module load by calling this helper.
 */
function paletteVisibleSlashEntries(catalog = exports.CLI_SLASH_CATALOG) {
    return catalog.filter((entry) => entry.cliOnly !== true);
}
/** Palette-visible subset of the catalog (CLI-only entries filtered out). */
exports.PALETTE_SLASH_ENTRIES = paletteVisibleSlashEntries();
function parseCliSlashInput(input) {
    const trimmed = input.trim();
    if (!trimmed.startsWith('/')) {
        return null;
    }
    const [rawToken = '', ...rest] = trimmed.split(/\s+/);
    const token = rawToken.toLowerCase();
    if (!token.startsWith('/')) {
        return null;
    }
    const args = rest.join(' ').trim();
    return {
        token,
        args,
        normalizedInput: args ? `${token} ${args}` : token,
    };
}
function slashTokensForEntry(entry) {
    return [entry.slash, ...(entry.aliases ?? [])];
}
function findCliSlashEntry(token, catalog = exports.CLI_SLASH_CATALOG) {
    const normalizedToken = token.trim().toLowerCase();
    if (!normalizedToken.startsWith('/')) {
        return null;
    }
    return (catalog.find((entry) => slashTokensForEntry(entry).includes(normalizedToken))
        ?? null);
}
function quotedArgs(args) {
    return `"${args}"`;
}
function buildCliSlashPrompt(entry, input = entry.slash) {
    const parsed = parseCliSlashInput(input);
    const args = parsed?.args ?? '';
    const normalizedInput = parsed?.normalizedInput ?? entry.slash;
    if (!args) {
        return entry.prompt;
    }
    switch (entry.id) {
        case 'slash:mode':
            return `Handle the operator's CLI-style request \`${normalizedInput}\`. Treat ${quotedArgs(args)} as the requested execution mode, confirm the current mode, and switch if supported. If an exact switch is not available here, explain the closest supported next step concisely.`;
        case 'slash:model':
            return `Handle the operator's CLI-style request \`${normalizedInput}\`. Treat ${quotedArgs(args)} as the requested model. Confirm the current model, say whether switching to ${quotedArgs(args)} is possible here, and either switch or explain the closest supported next step concisely.`;
        case 'slash:contract':
            return `Handle the operator's CLI-style request \`${normalizedInput}\`. Preserve its intent to inspect or transition the active task contract for this session. If the exact action cannot be taken from chat, explain the closest supported next step concisely.`;
        case 'slash:certification':
            return `Handle the operator's CLI-style request \`${normalizedInput}\`. Preserve its intent around mission certification status or submission, using ${quotedArgs(args)} as the operator-supplied certification context. Keep the response concise and action-oriented.`;
        case 'slash:verdict':
            return `Handle the operator's CLI-style request \`${normalizedInput}\`. Preserve its verifier or shadow-comparison intent, using ${quotedArgs(args)} as the operator-supplied verdict context. Keep the response concise and action-oriented.`;
        default:
            return `Handle the operator's CLI-style request \`${normalizedInput}\` as faithfully as possible in this chat surface. Preserve the command intent and keep the response concise.`;
    }
}
