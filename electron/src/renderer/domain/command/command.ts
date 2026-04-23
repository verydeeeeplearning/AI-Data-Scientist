export type CommandCategory =
  | 'navigation'
  | 'file'
  | 'run'
  | 'model'
  | 'policy'
  | 'slash'
  | 'agent';

export interface CommandExecutionRequest {
  readonly input?: string;
}

export interface Command {
  readonly id: string;
  readonly category: CommandCategory;
  readonly title: string;
  readonly subtitle?: string;
  readonly shortcut?: string;
  readonly searchTerms: readonly string[];
  readonly execute: (request?: CommandExecutionRequest) => Promise<void> | void;
}

export const COMMAND_CATEGORY_ORDER: readonly CommandCategory[] = [
  'navigation',
  'file',
  'run',
  'model',
  'policy',
  'slash',
  'agent',
] as const;
