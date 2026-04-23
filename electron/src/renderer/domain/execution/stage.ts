export type StageKey =
  | 'data_loading'
  | 'schema_diagnosis'
  | 'eda'
  | 'feature_engineering'
  | 'baseline_modeling'
  | 'model_comparison'
  | 'evaluation'
  | 'reporting'
  | 'verification_certification'
  | 'export';

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export type ToolCategory =
  | 'core_ds'
  | 'advanced'
  | 'integration'
  | 'artifact_learning'
  | 'memory'
  | 'sandbox'
  | 'domain';

export interface ArtifactRef {
  readonly kind: 'file' | 'plot' | 'report' | 'message';
  readonly id: string;
  readonly label?: string;
}

export interface ExecutionToolEvent {
  readonly toolName: string;
  readonly category: ToolCategory;
  readonly status: 'running' | 'completed' | 'failed';
  readonly args?: Readonly<Record<string, unknown>>;
  readonly outputPreview?: string;
  readonly elapsedMs?: number;
  readonly startedAt?: number;
  readonly completedAt?: number;
}

export interface StageOutcome {
  readonly summary: string;
  readonly detailRefs?: readonly ArtifactRef[];
}

export interface StageMetadata {
  readonly label: string;
  readonly labelKey: string;
}

export interface Stage {
  readonly key: StageKey;
  readonly label: string;
  readonly labelKey: string;
  readonly status: StageStatus;
  readonly toolEvents: readonly ExecutionToolEvent[];
  readonly startedAt?: number;
  readonly completedAt?: number;
  readonly outcome?: StageOutcome;
}

export const STAGE_ORDER: readonly StageKey[] = Object.freeze([
  'data_loading',
  'schema_diagnosis',
  'eda',
  'feature_engineering',
  'baseline_modeling',
  'model_comparison',
  'evaluation',
  'reporting',
  'verification_certification',
  'export',
]);

export const STAGE_METADATA: Readonly<Record<StageKey, StageMetadata>> = Object.freeze({
  data_loading: {
    label: 'Data Loading',
    labelKey: 'execution.stage.data_loading',
  },
  schema_diagnosis: {
    label: 'Schema Diagnosis',
    labelKey: 'execution.stage.schema_diagnosis',
  },
  eda: {
    label: 'Exploratory Analysis',
    labelKey: 'execution.stage.eda',
  },
  feature_engineering: {
    label: 'Feature Engineering',
    labelKey: 'execution.stage.feature_engineering',
  },
  baseline_modeling: {
    label: 'Baseline Modeling',
    labelKey: 'execution.stage.baseline_modeling',
  },
  model_comparison: {
    label: 'Model Comparison',
    labelKey: 'execution.stage.model_comparison',
  },
  evaluation: {
    label: 'Evaluation',
    labelKey: 'execution.stage.evaluation',
  },
  reporting: {
    label: 'Reporting',
    labelKey: 'execution.stage.reporting',
  },
  verification_certification: {
    label: 'Verification',
    labelKey: 'execution.stage.verification_certification',
  },
  export: {
    label: 'Export',
    labelKey: 'execution.stage.export',
  },
});

export function getStageMetadata(key: StageKey): StageMetadata {
  return STAGE_METADATA[key];
}

export function createExecutionToolEvent(
  overrides: Partial<ExecutionToolEvent> & Pick<ExecutionToolEvent, 'toolName' | 'status'>,
): ExecutionToolEvent {
  return Object.freeze({
    category: 'core_ds',
    ...overrides,
  });
}

export function createStage(
  overrides: Partial<Stage> & Pick<Stage, 'key' | 'status' | 'toolEvents'>,
): Stage {
  const metadata = getStageMetadata(overrides.key);
  return Object.freeze({
    label: metadata.label,
    labelKey: metadata.labelKey,
    startedAt: undefined,
    completedAt: undefined,
    outcome: undefined,
    ...overrides,
  });
}
