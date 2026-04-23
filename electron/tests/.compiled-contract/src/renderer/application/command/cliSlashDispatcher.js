"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveCliSlashDispatch = resolveCliSlashDispatch;
exports.dispatchCliSlashCommand = dispatchCliSlashCommand;
const cliSlashCatalog_1 = require("../../domain/command/cliSlashCatalog");
function resolveCliSlashDispatch(input, commands) {
    const parsed = (0, cliSlashCatalog_1.parseCliSlashInput)(input);
    if (!parsed) {
        return null;
    }
    const entry = (0, cliSlashCatalog_1.findCliSlashEntry)(parsed.token);
    if (!entry) {
        return {
            kind: 'unknown',
            slashToken: parsed.token,
            normalizedInput: parsed.normalizedInput,
        };
    }
    if (entry.cliOnly) {
        return {
            kind: 'cli-only',
            entryId: entry.id,
            slashToken: parsed.token,
            normalizedInput: parsed.normalizedInput,
        };
    }
    const command = commands.find((candidate) => candidate.id === entry.id);
    return {
        kind: 'palette',
        entryId: entry.id,
        slashToken: parsed.token,
        normalizedInput: parsed.normalizedInput,
        command,
        prompt: (0, cliSlashCatalog_1.buildCliSlashPrompt)(entry, parsed.normalizedInput),
    };
}
function dispatchCliSlashCommand(input, commands) {
    const resolution = resolveCliSlashDispatch(input, commands);
    if (resolution?.kind !== 'palette') {
        return null;
    }
    return resolution.command
        ?? commands.find((command) => command.id === resolution.entryId)
        ?? null;
}
