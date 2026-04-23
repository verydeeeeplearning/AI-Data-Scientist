import type { Command } from '../../domain/command/command';

const RECENT_COMMAND_IDS_STORAGE_KEY = 'ds-agent-command-palette-recent';
const MAX_RECENT_COMMANDS = 12;

function loadRecentIdsFromStorage(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_COMMAND_IDS_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((value): value is string => typeof value === 'string');
  } catch {
    return [];
  }
}

function persistRecentIds(ids: readonly string[]): void {
  try {
    window.localStorage.setItem(RECENT_COMMAND_IDS_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Ignore storage failures. The palette still works without persistence.
  }
}

export function loadRecentCommandIds(): string[] {
  return loadRecentIdsFromStorage();
}

export function recordRecentCommandId(commandId: string): string[] {
  const current = loadRecentIdsFromStorage();
  const next = [
    commandId,
    ...current.filter((candidate) => candidate !== commandId),
  ].slice(0, MAX_RECENT_COMMANDS);
  persistRecentIds(next);
  return next;
}

export function buildCommandMap(commands: readonly Command[]): Map<string, Command> {
  return new Map(commands.map((command) => [command.id, command]));
}
