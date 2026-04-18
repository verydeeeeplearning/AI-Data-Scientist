export type ReviewSkillName =
  | 'backtesting'
  | 'causal-assumption-check'
  | 'uncertainty-quantification'
  | 'retrain-vs-rollback';

export interface ReviewOverviewSummary {
  runCount: number;
  modelCount: number;
  decisionCount: number;
  monitorStateCount: number;
}

export interface BacktestFold {
  fold_label: string;
  metric: string;
  score: number;
  baseline_score?: number | null;
  status: 'pass' | 'warn' | 'fail';
}

export interface BacktestResult {
  artifact_type: 'backtesting';
  folds: BacktestFold[];
  consistency_score: number;
  warnings: string[];
}

export interface CausalRisk {
  assumption: string;
  severity: 'pass' | 'warn' | 'fail';
  detail: string;
}

export interface CausalReview {
  artifact_type: 'causal-assumption-check';
  risks: CausalRisk[];
  confounders: string[];
  is_causal: boolean;
}

export interface UncertaintyInterval {
  metric: string;
  lower: number;
  upper: number;
  confidence_level?: number | null;
}

export interface UncertaintyReport {
  artifact_type: 'uncertainty-quantification';
  methodology: string;
  intervals: UncertaintyInterval[];
  warnings: string[];
}

export interface RetrainVsRollback {
  artifact_type: 'retrain-vs-rollback';
  recommendation: 'retrain' | 'rollback' | 'monitor' | 'hold';
  rationale: string;
  evidence: string[];
}

export type ReviewArtifactPayload =
  | BacktestResult
  | CausalReview
  | UncertaintyReport
  | RetrainVsRollback;

export interface ReviewArtifactRecord {
  artifact_id: string;
  skill_name: ReviewSkillName;
  summary: string;
  narrative?: string | null;
  created_at: string;
  artifact: ReviewArtifactPayload;
}

export interface ReviewRun {
  run_id: string;
  experiment_group: string;
  sequence: number;
  owner: string;
  status: string;
  promotion_state: string;
  created_at: string;
  method: {
    model_family: string;
    hyperparameters: Record<string, unknown>;
  };
  result: {
    metrics: Record<string, number>;
  };
  review_artifacts: ReviewArtifactRecord[];
}

export interface ReviewModel {
  model_id: string;
  version: number;
  alias: string;
  lineage_run_id: string;
  created_at: string;
  promoted_at?: string | null;
  retired_at?: string | null;
  description: string;
}

export interface ReviewPolicyCheck {
  name: string;
  status: 'pass' | 'warn' | 'fail' | 'skipped';
  detail: string;
}

export interface ReviewApprovalStep {
  role: string;
  approver: string;
  status: string;
  decided_at?: string | null;
  note?: string | null;
}

export interface ReviewDecision {
  decision_id: string;
  candidate_run_id: string;
  candidate_model_id: string;
  target_stage: string;
  policy_checks: ReviewPolicyCheck[];
  approvals: ReviewApprovalStep[];
  chain_state: string;
  rollback_plan_ref: string;
  created_at: string;
  resolved_at?: string | null;
}

export interface ReviewMonitorState {
  model_id: string;
  model_version: number;
  alias: string;
  observed_at: string;
  overall_status: 'ok' | 'warning' | 'alert';
  alerts: string[];
  trigger_mode: string;
  drift: {
    max_psi?: number | null;
    max_ks?: number | null;
    top_drifting_features: string[];
  };
  remediation: {
    decision: string;
    severity: string;
    rationale: string;
    recommended_steps: string[];
  };
}

export interface DecisionOsOverview {
  summary: ReviewOverviewSummary;
  runs: ReviewRun[];
  models: ReviewModel[];
  promotionDecisions: ReviewDecision[];
  monitorStates: ReviewMonitorState[];
}

export interface RunDiffMetricDelta {
  metric: string;
  from_value: number;
  to_value: number;
  delta: number;
  direction: 'better' | 'worse' | 'neutral';
  significance_note?: string | null;
}

export interface RunDiffResult {
  run_a_id: string;
  run_b_id: string;
  summary_markdown: string;
  feature_set: {
    added: Array<{ feature_id: string; version: number }>;
    removed: Array<{ feature_id: string; version: number }>;
    version_changed: Array<[string, number, number]>;
  };
  metrics: RunDiffMetricDelta[];
  verifier: {
    statistical: [string, string];
    data: [string, string];
    policy: [string, string];
    new_findings: string[];
    resolved_findings: string[];
  };
  code_ref: [string, string];
  data_snapshot: [string, string];
}

export interface PostDeployStatusResult {
  model_id: string;
  model_version: number;
  window: string;
  alerts: string[];
  observations: number;
  summary: ReviewMonitorState & {
    service_level: {
      status: string;
      latency_p95_ms?: number | null;
      latency_budget_ms?: number | null;
      qps?: number | null;
      throughput_budget_qps?: number | null;
    };
    metrics: Array<{
      metric: string;
      baseline_value: number;
      current_value: number;
      delta: number;
      direction: string;
      status: string;
    }>;
  };
}

export const EXPECTED_REVIEW_SKILLS: ReviewSkillName[] = [
  'backtesting',
  'causal-assumption-check',
  'uncertainty-quantification',
  'retrain-vs-rollback',
];

export function formatDate(value?: string | null): string {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

export function metricPreview(metrics: Record<string, number>): string {
  const firstMetric = Object.entries(metrics)[0];
  if (!firstMetric) return 'No metrics';
  return `${firstMetric[0]} ${firstMetric[1].toFixed(3)}`;
}

export function runOptionLabel(run: ReviewRun): string {
  return `${run.run_id} | ${run.method.model_family} | ${metricPreview(run.result.metrics)}`;
}

export function promotionOptionLabel(run: ReviewRun): string {
  return `${run.run_id} | ${run.promotion_state} | ${run.method.model_family}`;
}

export function modelOptionLabel(model: ReviewModel): string {
  return `${model.model_id} | v${model.version} | ${model.alias}`;
}

export function reviewSkillLabel(skill: ReviewSkillName): string {
  if (skill === 'backtesting') return 'Time Split Stability';
  if (skill === 'causal-assumption-check') return 'Causal Risk';
  if (skill === 'uncertainty-quantification') return 'Uncertainty Range';
  return 'Retrain vs Rollback';
}

export function severityClass(status: string): string {
  if (status === 'fail' || status === 'alert' || status === 'rejected') {
    return 'border-ds-error/40 bg-ds-error/10 text-ds-error';
  }
  if (status === 'warn' || status === 'warning' || status.startsWith('pending')) {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-300';
  }
  if (status === 'pass' || status === 'ok' || status === 'approved') {
    return 'border-ds-success/40 bg-ds-success/10 text-ds-success';
  }
  return 'border-ds-border bg-ds-bg/70 text-ds-muted';
}

export function directionClass(direction: string): string {
  if (direction === 'better') return 'text-ds-success';
  if (direction === 'worse') return 'text-ds-error';
  return 'text-ds-muted';
}

export function parseApprovers(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((value) => value.trim())
    .filter(Boolean);
}
