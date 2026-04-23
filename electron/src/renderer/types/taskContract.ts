export type TaskContractStatus =
  | 'draft'
  | 'agreed'
  | 'in_progress'
  | 'review'
  | 'closed'
  | 'abandoned';

export type DeliveryPackStatus = 'draft' | 'rendered' | 'dispatched' | 'rejected';

export type DeliveryDispatchMode = 'auto' | 'auto_with_signature' | 'manual_review';

export type DeliveryDispatchStatus =
  | 'sent'
  | 'blocked'
  | 'duplicate'
  | 'failed'
  | 'dry_run';

export type DeliveryDispatchOutcome = 'dispatched' | 'partial' | 'blocked' | 'dry_run';

export interface TaskContractListItem {
  task_id: string;
  status: TaskContractStatus;
  type: string;
  business_goal: string;
  updated_at: string;
  version: number;
}

export interface DeliverableSpec {
  type: string;
  audience: string;
  format: string;
  count?: number | null;
}

export interface GoalBriefView {
  business_question: string;
  ds_problem_statement: string;
  comparison_baseline: string;
  decision_to_make: string;
  hypothesis?: string | null;
  expected_effort: string;
}

export interface GoalBriefDraftInput {
  business_question: string;
  ds_problem_statement: string;
  comparison_baseline: string;
  decision_to_make: string;
  hypothesis?: string | null;
  expected_effort: string;
}

export interface TaskContractCreatePayload {
  session_id: string;
  contract_type: string;
  business_goal: string;
  goal_brief: GoalBriefDraftInput;
  required_deliverables: DeliverableSpec[];
  allowed_data_sources?: Record<string, unknown>[];
  forbidden_data_patterns?: string[];
  budget?: Record<string, unknown>;
  autonomy?: Record<string, unknown>;
  decision_owner?: string | null;
  decision_deadline?: string | null;
  definition_of_done?: Record<string, unknown> | null;
  authority?: string | null;
  audience?: string | null;
  mission?: string | null;
  created_by?: string;
}

export interface TaskContractCreateResultView {
  task_id: string;
  status: TaskContractStatus;
  goal_brief_id: string;
  new_version: number;
  next_suggested_action?: string | null;
}

export interface TaskContractErrorDetailView {
  message: string;
  error_code?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TaskContractIpcErrorResult {
  ok: false;
  error: string;
  errorDetail?: TaskContractErrorDetailView;
}

export interface AssumptionEntry {
  entry_id: string;
  statement: string;
  rationale: string;
  risk_level: 'low' | 'medium' | 'high';
  verified: boolean;
  verification_note?: string | null;
  asked_user: boolean;
  created_at: string;
}

export interface AssumptionLogView {
  log_id: string;
  task_id: string;
  entries: AssumptionEntry[];
}

export interface AssumptionVerificationResultView {
  entry_id: string;
  verified: boolean;
  verification_note?: string | null;
  new_version: number;
}

export interface ReviewVerdictView {
  verdict_id: string;
  task_id: string;
  category: string;
  result: 'pass' | 'warn' | 'fail';
  reviewer: string;
  summary: string;
  evidence_refs: string[];
  created_at: string;
  confidence?: {
    score: number;
    grade: 'high' | 'medium' | 'low' | 'insufficient' | null;
    rationale: string;
  } | null;
  blocking_issues?: {
    layer?: string | null;
    check_id?: string | null;
    severity: 'low' | 'medium' | 'high' | 'critical';
    message: string;
    blocking: boolean;
  }[];
  layers?: {
    layer: string;
    overall?: 'pass' | 'warn' | 'fail' | 'error' | null;
    score?: number | null;
    summary?: string | null;
    metadata?: Record<string, unknown>;
  }[];
  metadata?: Record<string, unknown>;
}

export interface DeliveryItemView {
  deliverable_type: string;
  audience: string;
  format: string;
  artifact_path: string;
  checksum?: string | null;
  delivered: boolean;
  delivery_channel?: string | null;
  artifact_id?: string | null;
  verifier_report_id?: string | null;
}

export interface DeliveryReceiverView {
  role: string;
  resolver: 'org_directory' | 'static_list' | 'task_contract';
  static_addresses: string[];
}

export interface DeliveryContentPolicyView {
  structure: string[];
  max_pages?: number | null;
  chart_count_range?: [number, number] | null;
  technical_detail: 'minimal' | 'balanced' | 'deep';
  tone: 'decisive' | 'actionable' | 'precise' | 'neutral' | 'mentoring';
  include_code: boolean;
  include_verifier_results: boolean;
  include_jira_links: boolean;
  include_feature_registry_refs: boolean;
  speculative_claims: 'allowed' | 'flagged' | 'forbidden';
}

export interface DeliveryArtifactView {
  artifact_id: string;
  type: string;
  audience: string;
  format: string;
  content_policy: DeliveryContentPolicyView;
  template_ref: string;
  delivery_channel: string[];
  dispatch_mode: DeliveryDispatchMode;
  receivers: DeliveryReceiverView[];
  rendered_uri?: string | null;
  verifier_report_id?: string | null;
}

export interface DeliveryPackView {
  pack_id: string;
  task_id: string;
  source_analysis_id?: string | null;
  confidence?: number | null;
  signed_by?: string | null;
  signature?: string | null;
  global_context: Record<string, string>;
  artifacts: DeliveryArtifactView[];
  items: DeliveryItemView[];
  follow_up_actions: string[];
  generated_at: string;
  status: DeliveryPackStatus;
  tenant: string;
}

export interface DeliveryReceiptView {
  artifact_id: string;
  channel: string;
  status: DeliveryDispatchStatus;
  idempotency_key: string;
  recorded_at: string;
  reason?: string | null;
  receipt_id?: string | null;
  adapter_name?: string | null;
}

export interface DeliveryBuildResultView {
  pack_id: string;
  items: number;
  artifacts: number;
  audiences: string[];
  artifact_ids: string[];
  status: DeliveryPackStatus;
  new_version: number;
}

export interface DeliveryRenderResultView {
  pack_id: string;
  artifact_id: string;
  output_path: string;
  format: string;
  verifier_status: string;
  verifier_report_id?: string | null;
  flagged_claims: string[];
  pack_status: DeliveryPackStatus;
  new_version: number;
  renderer_mode?: string | null;
  renderer_model?: string | null;
}

export interface DeliveryDispatchResultView {
  task_id: string;
  pack_id: string;
  dispatch_status: DeliveryDispatchOutcome;
  dry_run: boolean;
  receipts: DeliveryReceiptView[];
  log_path?: string | null;
  sent: number;
  blocked: number;
  failed: number;
  duplicates: number;
  pack_status: DeliveryPackStatus;
  new_version: number;
}

export interface DeliveryLogRecordView {
  task_id: string;
  pack_id: string;
  artifact_id: string;
  channel: string;
  status: DeliveryDispatchStatus;
  idempotency_key: string;
  recorded_at: string;
  reason?: string | null;
  receipt_id?: string | null;
  adapter_name?: string | null;
}

export interface DeliveryLogSummaryView {
  task_id: string;
  pack_id: string;
  pack_status: string;
  artifact_count: number;
  rendered_count: number;
  sent: number;
  blocked: number;
  duplicate: number;
  failed: number;
  dry_run: number;
  last_attempt?: string | null;
}

export interface DeliveryLogQueryResultView {
  task_id: string;
  pack_id?: string | null;
  log_path?: string | null;
  records: DeliveryLogRecordView[];
  summary?: DeliveryLogSummaryView | null;
  returned: number;
}

export interface PptxPreviewSlideView {
  index: number;
  section?: string | null;
  title: string;
  bullets: string[];
  excerpt: string;
  chart_count: number;
}

export type RenderedArtifactPreviewView =
  | {
      kind: 'markdown';
      path: string;
      fileUrl: string;
      content: string;
      truncated: boolean;
      sections: string[];
      lineCount: number;
    }
  | {
      kind: 'ipynb';
      path: string;
      fileUrl: string;
      markdownCells: string[];
      codeCells: string[];
      outputCells: string[];
      truncated: boolean;
      cellCount: number;
    }
  | {
      kind: 'pdf';
      path: string;
      fileUrl: string;
      size: number;
    }
  | {
      kind: 'pptx';
      path: string;
      fileUrl: string;
      slides: PptxPreviewSlideView[];
      slideCount: number;
      manifestFound: boolean;
    }
  | {
      kind: 'unavailable';
      path: string;
      fileUrl: string;
      message: string;
    };

export type ShadowLegacyState = 'triggered' | 'clear' | 'not_applicable';

export type ShadowMismatchKind =
  | 'legacy_only'
  | 'verifier_only'
  | 'agreement'
  | 'not_applicable';

export interface ShadowComparisonItemView {
  comparison_key: string;
  legacy_source: string;
  verifier_targets: string[];
  applicable: boolean;
  legacy_state: ShadowLegacyState;
  verifier_state: ShadowLegacyState;
  matches: boolean;
  mismatch_kind: ShadowMismatchKind;
  legacy_evidence: Record<string, unknown>[];
  verifier_evidence: Record<string, unknown>[];
  note?: string | null;
}

export interface ShadowComparisonView {
  comparison_id: string;
  verdict_id: string;
  task_id: string;
  run_id?: string | null;
  session_id?: string | null;
  created_at: string;
  items: ShadowComparisonItemView[];
  applicable_count: number;
  mismatch_count: number;
  match_rate: number;
  metadata?: Record<string, unknown>;
}

export interface TaskContractEntity {
  task_id: string;
  session_id: string;
  type: string;
  status: TaskContractStatus;
  business_goal: string;
  decision_owner?: string | null;
  authority?: string | null;
  audience?: string | null;
  mission?: string | null;
  forbidden_data_patterns: string[];
  required_deliverables: DeliverableSpec[];
  autonomy: {
    agent_will_do: string[];
    agent_will_ask: string[];
    agent_will_escalate: string[];
  };
  created_at: string;
  updated_at: string;
  version: number;
}

export interface TaskContractView {
  contract: TaskContractEntity;
  goal_brief?: GoalBriefView | null;
  assumption_log?: AssumptionLogView | null;
  review_verdicts: ReviewVerdictView[];
  delivery_pack?: DeliveryPackView | null;
  dod_summary: string[];
}
