import assert from 'node:assert/strict';

import {
  dispatchCliSlashCommand,
  resolveCliSlashDispatch,
} from '../../src/renderer/application/command/cliSlashDispatcher';
import { PALETTE_SLASH_ENTRIES } from '../../src/renderer/domain/command/cliSlashCatalog';
import type { Command } from '../../src/renderer/domain/command/command';

function makeCommands(): Command[] {
  return PALETTE_SLASH_ENTRIES.map((entry) => ({
    id: entry.id,
    category: 'slash',
    title: entry.slash,
    subtitle: entry.prompt || entry.descriptionKey,
    searchTerms: [entry.slash, ...entry.searchTerms],
    execute: () => undefined,
  }));
}

function run(): void {
  const commands = makeCommands();
  let cases = 0;

  // === known slash commands resolve to their palette command ===
  {
    const resolved = dispatchCliSlashCommand('/status', commands);
    assert.ok(resolved);
    assert.equal(resolved?.id, 'slash:status');
    cases += 1;
  }

  // === slash tokens are normalized before matching ===
  {
    const resolved = dispatchCliSlashCommand('   /model   gpt-4.1  ', commands);
    assert.ok(resolved);
    assert.equal(resolved?.id, 'slash:model');
    cases += 1;
  }

  // === typed slash arguments are preserved in the synthesized prompt ===
  {
    const resolved = resolveCliSlashDispatch('/model openai/gpt-4.1', commands);
    assert.ok(resolved);
    assert.equal(resolved?.kind, 'palette');
    assert.equal(resolved?.command?.id, 'slash:model');
    assert.match(
      resolved?.prompt ?? '',
      /openai\/gpt-4\.1/i,
      'typed slash arguments must be preserved in the synthesized prompt',
    );
    cases += 1;
  }

  // === contract-like slash arguments preserve intent rather than dropping them ===
  {
    const resolved = resolveCliSlashDispatch('/contract agree task-123', commands);
    assert.ok(resolved);
    assert.equal(resolved?.kind, 'palette');
    assert.match(
      resolved?.prompt ?? '',
      /transition the active task contract/i,
      'contract prompt should preserve transition intent for CLI-style args',
    );
    assert.match(
      resolved?.prompt ?? '',
      /task-123/i,
      'contract prompt should preserve the operator-supplied task identifier',
    );
    cases += 1;
  }

  // === CLI-only aliases are recognized and blocked from palette dispatch ===
  {
    const resolved = resolveCliSlashDispatch('/exit', commands);
    assert.ok(resolved);
    assert.equal(resolved?.kind, 'cli-only');
    assert.equal(dispatchCliSlashCommand('/exit', commands), null);
    cases += 1;
  }

  // === canonical CLI-only commands are recognized and blocked from palette dispatch ===
  {
    const resolved = resolveCliSlashDispatch('/history 5', commands);
    assert.ok(resolved);
    assert.equal(resolved?.kind, 'cli-only');
    assert.equal(dispatchCliSlashCommand('/history 5', commands), null);
    cases += 1;
  }

  // === unknown slash commands fall back to natural language ===
  {
    const resolved = resolveCliSlashDispatch('/not-a-real-command', commands);
    assert.ok(resolved);
    assert.equal(resolved?.kind, 'unknown');
    assert.equal(dispatchCliSlashCommand('/not-a-real-command', commands), null);
    cases += 1;
  }

  // === non-slash input is ignored by the dispatcher ===
  {
    const resolved = resolveCliSlashDispatch('status please', commands);
    assert.equal(resolved, null);
    assert.equal(dispatchCliSlashCommand('status please', commands), null);
    cases += 1;
  }

  console.log(`[contract] PASS cli-slash-dispatcher (${cases} cases)`);
}

run();
