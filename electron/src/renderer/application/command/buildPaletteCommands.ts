import {
  ADMIN_SECTION_DESCRIPTORS,
  AREA_DESCRIPTORS,
} from '../../domain/navigation/area';
import type { Command } from '../../domain/command/command';
import {
  buildCliSlashPrompt,
  PALETTE_SLASH_ENTRIES,
  slashTokensForEntry,
  type CliSlashEntry,
} from '../../domain/command/cliSlashCatalog';

type TFn = (key: string, vars?: Record<string, string | number | null | undefined>) => string;
type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

export interface PaletteRunSource {
  readonly runId: string;
  readonly status: 'running' | 'succeeded' | 'failed' | 'cancelled';
  readonly surface: string;
  readonly sessionLabel?: string | null;
  readonly resultPreview?: string | null;
  readonly createdAt: number;
}

export interface PaletteModelSource {
  readonly id: string;
  readonly displayName: string;
  readonly provider: string;
  readonly groupLabel: string;
  readonly badges: readonly string[];
  readonly recommendedFor: readonly string[];
}

export interface PaletteFileSource {
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly type: string;
  readonly modifiedAt?: number;
}

export interface BuildPaletteCommandsArgs {
  readonly t: TFn;
  readonly navigate: (path: string) => void;
  readonly files: readonly PaletteFileSource[];
  readonly runs: readonly PaletteRunSource[];
  readonly selectRun: (runId: string) => void;
  readonly models: readonly PaletteModelSource[];
  readonly onChangeModel: (model: string) => void;
  readonly onSend: (message: string) => void;
  readonly rpc: RpcFn;
}

const TABLE_FILE_EXTENSIONS = new Set(['csv', 'tsv', 'xlsx', 'xls', 'parquet', 'pq']);
const PLOT_FILE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'svg', 'gif', 'webp', 'html']);

function shortenRunId(runId: string): string {
  if (runId.length <= 18) {
    return runId;
  }
  return `${runId.slice(0, 8)}...${runId.slice(-6)}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes}B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)}KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function resolveFileCommandTarget(
  file: PaletteFileSource,
): {
  path: string;
  surfaceLabel: string;
  searchTerms: string[];
} {
  const normalizedType = file.type.toLowerCase();

  if (PLOT_FILE_EXTENSIONS.has(normalizedType)) {
    return {
      path: '/artifacts/workspace/charts',
      surfaceLabel: 'Open in Workspace Charts',
      searchTerms: ['chart', 'plot', 'gallery', 'workspace'],
    };
  }

  if (TABLE_FILE_EXTENSIONS.has(normalizedType)) {
    return {
      path: '/artifacts/workspace/tables',
      surfaceLabel: 'Open in Workspace Tables',
      searchTerms: ['table', 'dataset', 'metrics', 'workspace'],
    };
  }

  return {
    path: '/artifacts/workspace/files',
    surfaceLabel: 'Open in Workspace Files',
    searchTerms: ['file', 'artifact', 'workspace'],
  };
}

function dispatchPromptCommand(
  navigate: (path: string) => void,
  onSend: (message: string) => void,
  message: string,
): void {
  navigate('/mission');
  onSend(message);
}

function buildNavigationCommands(
  t: TFn,
  navigate: (path: string) => void,
): Command[] {
  const base = AREA_DESCRIPTORS.map((descriptor) => ({
    id: `nav:${descriptor.id}`,
    category: 'navigation' as const,
    title: t(descriptor.labelKey),
    subtitle: t(descriptor.descriptionKey),
    shortcut: descriptor.shortcut,
    searchTerms: [descriptor.id, descriptor.defaultPath],
    execute: () => navigate(descriptor.defaultPath),
  }));

  const workspaceCommands: Command[] = [
    {
      id: 'nav:artifacts:files',
      category: 'navigation',
      title: t('area.artifacts.views.files'),
      subtitle: t('area.artifacts.description'),
      shortcut: 'mod+3',
      searchTerms: ['artifacts', 'files', '/artifacts/files'],
      execute: () => navigate('/artifacts/files'),
    },
    {
      id: 'nav:artifacts:workspace',
      category: 'navigation',
      title: 'Evidence Workspace',
      subtitle: 'Open the workspace evidence hub',
      searchTerms: ['workspace', 'evidence', 'artifacts', '/artifacts/workspace'],
      execute: () => navigate('/artifacts/workspace'),
    },
    {
      id: 'nav:artifacts:experiments',
      category: 'navigation',
      title: t('area.artifacts.views.experiments'),
      subtitle: 'Inspect experiment and metric tables',
      searchTerms: ['experiments', 'metrics', '/artifacts/experiments'],
      execute: () => navigate('/artifacts/experiments'),
    },
    {
      id: 'nav:governance:policy',
      category: 'navigation',
      title: 'Governance Policy',
      subtitle: 'Open the governance policy surface',
      searchTerms: ['governance', 'policy', '/governance/policy'],
      execute: () => navigate('/governance/policy'),
    },
  ];

  const adminCommands = ADMIN_SECTION_DESCRIPTORS.map((descriptor) => ({
    id: `admin:${descriptor.id}`,
    category: 'navigation' as const,
    title: t(descriptor.labelKey),
    subtitle: 'Open an admin section',
    searchTerms: ['admin', descriptor.id, descriptor.defaultPath],
    execute: () => navigate(descriptor.defaultPath),
  }));

  return [...base, ...workspaceCommands, ...adminCommands];
}

function buildFileCommands(
  files: readonly PaletteFileSource[],
  navigate: (path: string) => void,
): Command[] {
  return [...files]
    .sort((left, right) => {
      const timestampDelta = (right.modifiedAt ?? 0) - (left.modifiedAt ?? 0);
      if (timestampDelta !== 0) {
        return timestampDelta;
      }
      return left.path.localeCompare(right.path);
    })
    .slice(0, 5)
    .map((file) => {
      const target = resolveFileCommandTarget(file);
      return {
        id: `file:${file.path}`,
        category: 'file',
        title: file.name,
        subtitle: `${target.surfaceLabel} | ${file.path} | ${formatFileSize(file.size)}`,
        searchTerms: [
          file.name,
          file.path,
          file.type,
          target.path,
          ...target.searchTerms,
        ],
        execute: () => navigate(target.path),
      };
    });
}

function buildRunCommands(
  runs: readonly PaletteRunSource[],
  selectRun: (runId: string) => void,
  navigate: (path: string) => void,
  rpc: RpcFn,
): Command[] {
  return [...runs]
    .sort((left, right) => right.createdAt - left.createdAt)
    .slice(0, 8)
    .flatMap((run) => {
      const inspectCommand: Command = {
        id: `run:inspect:${run.runId}`,
        category: 'run',
        title: `Inspect ${shortenRunId(run.runId)}`,
        subtitle: `${run.status} | ${run.surface}${run.sessionLabel ? ` | ${run.sessionLabel}` : ''}`,
        searchTerms: [
          run.runId,
          run.status,
          run.surface,
          run.sessionLabel ?? '',
          run.resultPreview ?? '',
        ],
        execute: () => {
          selectRun(run.runId);
          navigate('/runs');
        },
      };

      if (run.status !== 'running') {
        return [inspectCommand];
      }

      return [
        inspectCommand,
        {
          id: `run:abort:${run.runId}`,
          category: 'run',
          title: `Abort ${shortenRunId(run.runId)}`,
          subtitle: `Stop the active run on ${run.surface}`,
          searchTerms: [run.runId, 'abort', 'stop', run.surface],
          execute: async () => {
            await rpc('run.abort', { runId: run.runId });
          },
        },
      ];
    });
}

function buildModelCommands(
  models: readonly PaletteModelSource[],
  onChangeModel: (model: string) => void,
): Command[] {
  return models.map((model) => ({
    id: `model:${model.id}`,
    category: 'model' as const,
    title: model.displayName,
    subtitle: `${model.provider} | ${model.groupLabel}`,
    searchTerms: [
      model.id,
      model.provider,
      model.groupLabel,
      ...model.badges,
      ...model.recommendedFor,
    ],
    execute: () => onChangeModel(model.id),
  }));
}

function buildPolicyCommands(
  navigate: (path: string) => void,
): Command[] {
  return [
    {
      id: 'policy:studio',
      category: 'policy',
      title: 'Open Policy Studio',
      subtitle: 'Edit runtime authority and matrix overrides',
      searchTerms: ['policy', 'studio', 'admin', '/admin/policies'],
      execute: () => navigate('/admin/policies'),
    },
    {
      id: 'policy:governance',
      category: 'policy',
      title: 'Open Governance Review',
      subtitle: 'Inspect verifier and review workflow',
      searchTerms: ['governance', 'review', '/governance/review'],
      execute: () => navigate('/governance/review'),
    },
    {
      id: 'policy:surface',
      category: 'policy',
      title: 'Open Governance Policy',
      subtitle: 'Jump to the governance policy section',
      searchTerms: ['governance', 'policy', '/governance/policy'],
      execute: () => navigate('/governance/policy'),
    },
  ];
}

const SLASH_FALLBACK_SUBTITLES: Readonly<Record<string, string>> = {
  'slash:help': 'Ask for the most useful operator shortcuts and next actions',
  'slash:status': 'Ask for the current project status, cost, and active step',
  'slash:files': 'Ask for the current artifact and workspace file summary',
  'slash:budget': 'Ask for the current budget summary and burn rate',
  'slash:contract': 'Ask for the active task contract and operating constraints',
  'slash:verdict': 'Ask for the latest verifier or shadow-comparison verdict',
  'slash:mode': 'Ask the agent to summarize the current execution mode and recommend a switch',
  'slash:model': 'Ask the agent to report the active model and suggest a better fit',
  'slash:certification':
    'Ask the agent to summarize mission certification status and remaining gates',
};

function resolveSlashTitle(entry: CliSlashEntry, t: TFn): string {
  const localized = t(entry.labelKey);
  if (localized && localized !== entry.labelKey) {
    return localized;
  }
  return entry.slash;
}

function resolveSlashSubtitle(entry: CliSlashEntry, t: TFn): string {
  const localized = t(entry.descriptionKey);
  if (localized && localized !== entry.descriptionKey) {
    return localized;
  }
  return SLASH_FALLBACK_SUBTITLES[entry.id] ?? entry.slash;
}

function buildSlashCommands(
  onSend: (message: string) => void,
  navigate: (path: string) => void,
  t: TFn,
): Command[] {
  return PALETTE_SLASH_ENTRIES.map((entry) => ({
    id: entry.id,
    category: 'slash' as const,
    title: resolveSlashTitle(entry, t),
    subtitle: resolveSlashSubtitle(entry, t),
    searchTerms: [...slashTokensForEntry(entry), ...entry.searchTerms],
    execute: (request) =>
      dispatchPromptCommand(
        navigate,
        onSend,
        buildCliSlashPrompt(entry, request?.input ?? entry.slash),
      ),
  }));
}

function buildAgentCommands(
  runs: readonly PaletteRunSource[],
  onSend: (message: string) => void,
  navigate: (path: string) => void,
): Command[] {
  const sortedRuns = [...runs].sort((left, right) => right.createdAt - left.createdAt);
  const latestRun = sortedRuns[0] ?? null;
  const previousRun = sortedRuns[1] ?? null;

  const commands: Command[] = [
    {
      id: 'agent:plan-next-step',
      category: 'agent',
      title: 'Plan Next Step',
      subtitle: 'Ask the agent to summarize progress and continue from the next incomplete step',
      searchTerms: ['plan', 'next step', 'continue', 'resume'],
      execute: () =>
        dispatchPromptCommand(
          navigate,
          onSend,
          'Summarize what is already complete, identify the next incomplete step, and continue from there. Keep the update concise and action-oriented.',
        ),
    },
    {
      id: 'agent:rerun-review',
      category: 'agent',
      title: 'Review Rerun Strategy',
      subtitle: 'Ask whether a rerun is warranted and what the minimal rerun should be',
      searchTerms: ['rerun', 'retry', 'checkpoint', 'step'],
      execute: () =>
        dispatchPromptCommand(
          navigate,
          onSend,
          'Review the latest completed work, explain whether a rerun is warranted, and if so propose the smallest safe rerun scope with the reason.',
        ),
    },
  ];

  if (latestRun && previousRun) {
    commands.push({
      id: 'agent:compare-latest-runs',
      category: 'agent',
      title: 'Compare Latest Runs',
      subtitle: `Compare ${shortenRunId(previousRun.runId)} and ${shortenRunId(latestRun.runId)}`,
      searchTerms: [
        'compare',
        'diff',
        latestRun.runId,
        previousRun.runId,
        latestRun.sessionLabel ?? '',
        previousRun.sessionLabel ?? '',
      ],
      execute: () =>
        dispatchPromptCommand(
          navigate,
          onSend,
          `Compare run ${previousRun.runId} with run ${latestRun.runId}. Summarize the key differences in outcome, metrics, risks, and the recommended next decision.`,
        ),
    });
  } else if (latestRun) {
    commands.push({
      id: 'agent:review-latest-run',
      category: 'agent',
      title: 'Review Latest Run',
      subtitle: `Ask for a concise review of ${shortenRunId(latestRun.runId)}`,
      searchTerms: ['review', 'latest run', latestRun.runId, latestRun.sessionLabel ?? ''],
      execute: () =>
        dispatchPromptCommand(
          navigate,
          onSend,
          `Review run ${latestRun.runId}. Summarize what succeeded, what failed, and the best next action.`,
        ),
    });
  }

  return commands;
}

export function buildPaletteCommands(args: BuildPaletteCommandsArgs): Command[] {
  return [
    ...buildNavigationCommands(args.t, args.navigate),
    ...buildFileCommands(args.files, args.navigate),
    ...buildRunCommands(args.runs, args.selectRun, args.navigate, args.rpc),
    ...buildModelCommands(args.models, args.onChangeModel),
    ...buildPolicyCommands(args.navigate),
    ...buildSlashCommands(args.onSend, args.navigate, args.t),
    ...buildAgentCommands(args.runs, args.onSend, args.navigate),
  ];
}
