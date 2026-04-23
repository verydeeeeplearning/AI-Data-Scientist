"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const cliSlashDispatcher_1 = require("../../src/renderer/application/command/cliSlashDispatcher");
const cliSlashCatalog_1 = require("../../src/renderer/domain/command/cliSlashCatalog");
function makeCommands() {
    return cliSlashCatalog_1.PALETTE_SLASH_ENTRIES.map((entry) => ({
        id: entry.id,
        category: 'slash',
        title: entry.slash,
        subtitle: entry.prompt || entry.descriptionKey,
        searchTerms: [entry.slash, ...entry.searchTerms],
        execute: () => undefined,
    }));
}
function run() {
    const commands = makeCommands();
    let cases = 0;
    // === known slash commands resolve to their palette command ===
    {
        const resolved = (0, cliSlashDispatcher_1.dispatchCliSlashCommand)('/status', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.id, 'slash:status');
        cases += 1;
    }
    // === slash tokens are normalized before matching ===
    {
        const resolved = (0, cliSlashDispatcher_1.dispatchCliSlashCommand)('   /model   gpt-4.1  ', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.id, 'slash:model');
        cases += 1;
    }
    // === typed slash arguments are preserved in the synthesized prompt ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('/model openai/gpt-4.1', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.kind, 'palette');
        strict_1.default.equal(resolved?.command?.id, 'slash:model');
        strict_1.default.match(resolved?.prompt ?? '', /openai\/gpt-4\.1/i, 'typed slash arguments must be preserved in the synthesized prompt');
        cases += 1;
    }
    // === contract-like slash arguments preserve intent rather than dropping them ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('/contract agree task-123', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.kind, 'palette');
        strict_1.default.match(resolved?.prompt ?? '', /transition the active task contract/i, 'contract prompt should preserve transition intent for CLI-style args');
        strict_1.default.match(resolved?.prompt ?? '', /task-123/i, 'contract prompt should preserve the operator-supplied task identifier');
        cases += 1;
    }
    // === CLI-only aliases are recognized and blocked from palette dispatch ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('/exit', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.kind, 'cli-only');
        strict_1.default.equal((0, cliSlashDispatcher_1.dispatchCliSlashCommand)('/exit', commands), null);
        cases += 1;
    }
    // === canonical CLI-only commands are recognized and blocked from palette dispatch ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('/history 5', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.kind, 'cli-only');
        strict_1.default.equal((0, cliSlashDispatcher_1.dispatchCliSlashCommand)('/history 5', commands), null);
        cases += 1;
    }
    // === unknown slash commands fall back to natural language ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('/not-a-real-command', commands);
        strict_1.default.ok(resolved);
        strict_1.default.equal(resolved?.kind, 'unknown');
        strict_1.default.equal((0, cliSlashDispatcher_1.dispatchCliSlashCommand)('/not-a-real-command', commands), null);
        cases += 1;
    }
    // === non-slash input is ignored by the dispatcher ===
    {
        const resolved = (0, cliSlashDispatcher_1.resolveCliSlashDispatch)('status please', commands);
        strict_1.default.equal(resolved, null);
        strict_1.default.equal((0, cliSlashDispatcher_1.dispatchCliSlashCommand)('status please', commands), null);
        cases += 1;
    }
    console.log(`[contract] PASS cli-slash-dispatcher (${cases} cases)`);
}
run();
