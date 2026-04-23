import type { Command } from '../../domain/command/command';
import {
  buildCliSlashPrompt,
  findCliSlashEntry,
  parseCliSlashInput,
} from '../../domain/command/cliSlashCatalog';

export interface CliSlashDispatchResolution {
  readonly kind: 'palette' | 'cli-only' | 'unknown';
  readonly entryId?: string;
  readonly slashToken: string;
  readonly normalizedInput: string;
  readonly command?: Command;
  readonly prompt?: string;
}

export function resolveCliSlashDispatch(
  input: string,
  commands: readonly Command[],
): CliSlashDispatchResolution | null {
  const parsed = parseCliSlashInput(input);
  if (!parsed) {
    return null;
  }

  const entry = findCliSlashEntry(parsed.token);
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
    prompt: buildCliSlashPrompt(entry, parsed.normalizedInput),
  };
}

export function dispatchCliSlashCommand(
  input: string,
  commands: readonly Command[],
): Command | null {
  const resolution = resolveCliSlashDispatch(input, commands);
  if (resolution?.kind !== 'palette') {
    return null;
  }

  return resolution.command
    ?? commands.find((command) => command.id === resolution.entryId)
    ?? null;
}
