import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import {
  CLI_SLASH_CATALOG,
  PALETTE_SLASH_ENTRIES,
  paletteVisibleSlashEntries,
  slashTokensForEntry,
  type CliSlashEntry,
} from '../../src/renderer/domain/command/cliSlashCatalog';

const EXPECTED_CLI_ONLY_SLASHES = ['/history', '/clear', '/quit'];
const I18N_KEY_PATTERN = /^(?:cmd|command)[.:]/;

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function resolveCliCommandsPath(): string {
  const candidates = [
    path.resolve(process.cwd(), '../src/ds_agent/cli/commands.py'),
    path.resolve(process.cwd(), 'src/ds_agent/cli/commands.py'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  throw new Error('Could not locate src/ds_agent/cli/commands.py from the contract test');
}

function uniqueSorted(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

function extractHelpTextCommands(source: string): string[] {
  const helpMatch = source.match(/HELP_TEXT = """\\\r?\n([\s\S]*?)"""/);
  assert.ok(helpMatch, 'HELP_TEXT block must exist in src/ds_agent/cli/commands.py');

  return uniqueSorted(
    helpMatch[1]
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.startsWith('/'))
      .map((line) => line.split(/\s+/, 1)[0] ?? '')
      .filter(isNonEmptyString),
  );
}

function extractHandledCommands(source: string): string[] {
  const exactMatches = [...source.matchAll(/if cmd == "([^"]+)":/g)].map((match) => match[1]);
  const groupedMatches = [...source.matchAll(/if cmd in \(([^)]+)\):/g)].flatMap((match) =>
    [...match[1].matchAll(/"([^"]+)"/g)].map((tokenMatch) => tokenMatch[1]),
  );
  return uniqueSorted([...exactMatches, ...groupedMatches]);
}

function run(): void {
  let cases = 0;

  const cliCommandsSource = fs.readFileSync(resolveCliCommandsPath(), 'utf8');
  const helpCommands = extractHelpTextCommands(cliCommandsSource);
  const handledCommands = extractHandledCommands(cliCommandsSource);

  // === catalog is non-empty and every entry is structurally valid ===
  {
    assert.ok(CLI_SLASH_CATALOG.length > 0, 'catalog must not be empty');
    for (const entry of CLI_SLASH_CATALOG) {
      assert.ok(isNonEmptyString(entry.id), `entry.id must be a non-empty string (got ${String(entry.id)})`);
      assert.ok(isNonEmptyString(entry.slash), `entry.slash must be non-empty for ${entry.id}`);
      assert.ok(entry.slash.startsWith('/'), `entry.slash must start with '/' for ${entry.id}`);
      assert.ok(isNonEmptyString(entry.labelKey), `entry.labelKey must be non-empty for ${entry.id}`);
      assert.ok(isNonEmptyString(entry.descriptionKey), `entry.descriptionKey must be non-empty for ${entry.id}`);
      assert.equal(typeof entry.prompt, 'string', `entry.prompt must be a string for ${entry.id}`);
      assert.ok(Array.isArray(entry.searchTerms), `entry.searchTerms must be an array for ${entry.id}`);
      if (entry.aliases) {
        assert.ok(Array.isArray(entry.aliases), `entry.aliases must be an array for ${entry.id}`);
        for (const alias of entry.aliases) {
          assert.ok(isNonEmptyString(alias), `entry.aliases must contain only non-empty strings for ${entry.id}`);
          assert.ok(alias.startsWith('/'), `entry alias must start with '/' for ${entry.id} (got ${alias})`);
        }
      }
    }
    cases += 1;
  }

  // === ids and all slash tokens are unique across the catalog ===
  {
    const seenIds = new Set<string>();
    const seenTokens = new Set<string>();
    for (const entry of CLI_SLASH_CATALOG) {
      assert.ok(!seenIds.has(entry.id), `duplicate id in catalog: ${entry.id}`);
      seenIds.add(entry.id);

      for (const token of slashTokensForEntry(entry)) {
        assert.ok(!seenTokens.has(token), `duplicate slash token in catalog: ${token}`);
        seenTokens.add(token);
      }
    }
    cases += 1;
  }

  // === canonical catalog slashes match the Python CLI help table exactly ===
  {
    const catalogCanonicalSlashes = uniqueSorted(CLI_SLASH_CATALOG.map((entry) => entry.slash));
    assert.deepEqual(
      catalogCanonicalSlashes,
      helpCommands,
      'catalog canonical slashes must stay in sync with src/ds_agent/cli/commands.py HELP_TEXT',
    );
    cases += 1;
  }

  // === canonical slashes plus aliases match the Python handler tokens exactly ===
  {
    const catalogTokens = uniqueSorted(
      CLI_SLASH_CATALOG.flatMap((entry) => [...slashTokensForEntry(entry)]),
    );
    assert.deepEqual(
      catalogTokens,
      handledCommands,
      'catalog slash tokens must stay in sync with src/ds_agent/cli/commands.py handle_slash_command',
    );
    cases += 1;
  }

  // === cliOnly entries are exactly the palette-excluded canonical commands ===
  {
    const cliOnlyCanonicalSlashes = uniqueSorted(
      CLI_SLASH_CATALOG
        .filter((entry) => entry.cliOnly === true)
        .map((entry) => entry.slash),
    );
    assert.deepEqual(
      cliOnlyCanonicalSlashes,
      uniqueSorted(EXPECTED_CLI_ONLY_SLASHES),
      'cliOnly canonical slash set must remain explicit and reviewable',
    );

    const expectedPaletteSlashes = helpCommands.filter(
      (slash) => !EXPECTED_CLI_ONLY_SLASHES.includes(slash),
    );
    assert.deepEqual(
      uniqueSorted(PALETTE_SLASH_ENTRIES.map((entry) => entry.slash)),
      uniqueSorted(expectedPaletteSlashes),
      'palette-visible entries must equal the CLI help table minus the explicit CLI-only set',
    );
    cases += 1;
  }

  // === helper output matches the runtime constant and honors arbitrary input ===
  {
    const filtered = paletteVisibleSlashEntries();
    assert.deepEqual(
      filtered.map((entry) => entry.id),
      PALETTE_SLASH_ENTRIES.map((entry) => entry.id),
      'paletteVisibleSlashEntries() must match PALETTE_SLASH_ENTRIES',
    );

    const synthetic: readonly CliSlashEntry[] = [
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
    const syntheticFiltered = paletteVisibleSlashEntries(synthetic);
    assert.deepEqual(
      syntheticFiltered.map((entry) => entry.id),
      ['slash:keep'],
      'helper must drop cliOnly entries from arbitrary catalog input',
    );
    cases += 1;
  }

  // === labelKey and descriptionKey stay in the command namespace ===
  {
    for (const entry of CLI_SLASH_CATALOG) {
      assert.ok(
        I18N_KEY_PATTERN.test(entry.labelKey),
        `labelKey must start with 'cmd.' / 'command.' / 'cmd:' / 'command:' for ${entry.id} (got ${entry.labelKey})`,
      );
      assert.ok(
        I18N_KEY_PATTERN.test(entry.descriptionKey),
        `descriptionKey must start with 'cmd.' / 'command.' / 'cmd:' / 'command:' for ${entry.id} (got ${entry.descriptionKey})`,
      );
    }
    cases += 1;
  }

  console.log(`[contract] PASS cli-slash-catalog (${cases} cases)`);
}

run();
