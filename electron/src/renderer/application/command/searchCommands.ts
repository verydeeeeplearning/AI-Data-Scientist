import type { Command } from '../../domain/command/command';

export interface CommandSearchResult {
  readonly command: Command;
  readonly score: number;
  readonly recentIndex: number;
}

function normalize(value: string): string {
  return value.trim().toLowerCase().replace(/[\s_-]+/g, ' ');
}

function buildHaystacks(command: Command): string[] {
  return [
    command.title,
    command.subtitle ?? '',
    command.category,
    ...command.searchTerms,
  ]
    .map(normalize)
    .filter((value) => value.length > 0);
}

function subsequenceScore(query: string, candidate: string): number {
  if (!query || !candidate) {
    return 0;
  }

  let searchIndex = 0;
  let gaps = 0;
  for (const char of query) {
    const foundIndex = candidate.indexOf(char, searchIndex);
    if (foundIndex === -1) {
      return 0;
    }
    gaps += Math.max(0, foundIndex - searchIndex);
    searchIndex = foundIndex + 1;
  }

  return Math.max(8, 36 - gaps);
}

function scoreCommand(query: string, command: Command): number {
  if (!query) {
    return 1;
  }

  const haystacks = buildHaystacks(command);
  let best = 0;

  for (const haystack of haystacks) {
    if (haystack === query) {
      best = Math.max(best, 120);
      continue;
    }
    if (haystack.startsWith(query)) {
      best = Math.max(best, 90);
      continue;
    }
    if (haystack.includes(query)) {
      best = Math.max(best, 64);
      continue;
    }
    best = Math.max(best, subsequenceScore(query, haystack));
  }

  return best;
}

export function searchCommands(
  query: string,
  commands: readonly Command[],
  recentIds: readonly string[],
  limit = 40,
): CommandSearchResult[] {
  const normalizedQuery = normalize(query);
  const recentIndexById = new Map(recentIds.map((id, index) => [id, index]));

  const scored = commands
    .map((command) => {
      const score = scoreCommand(normalizedQuery, command);
      const recentIndex = recentIndexById.get(command.id) ?? Number.POSITIVE_INFINITY;
      const recentBoost = Number.isFinite(recentIndex)
        ? Math.max(0, 24 - (recentIndex * 2))
        : 0;
      return {
        command,
        score: score + recentBoost,
        recentIndex,
      };
    })
    .filter((entry) => normalizedQuery.length === 0 || entry.score > 0);

  scored.sort((left, right) => {
    if (left.score !== right.score) {
      return right.score - left.score;
    }
    if (left.recentIndex !== right.recentIndex) {
      return left.recentIndex - right.recentIndex;
    }
    return left.command.title.localeCompare(right.command.title);
  });

  return scored.slice(0, limit);
}
