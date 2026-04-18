export type WorkObjectPhase =
  | 'intake'
  | 'executing'
  | 'review'
  | 'documenting'
  | 'followup'
  | 'closed'
  | 'failed';

export type FollowUpActionStatus = 'pending' | 'completed' | 'cancelled';

export type IntegrationEventStatus = 'pending' | 'success' | 'failed' | 'dlq' | 'duplicate';

export interface ExternalReferenceView {
  system: string;
  resource_type: string;
  resource_id: string;
  url?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  idempotency_key: string;
}

export interface RequestSectionView {
  source: string;
  requestor_id: string;
  requestor_display: string;
  original_text: string;
  channel?: string | null;
  received_at: string;
  external_ref?: ExternalReferenceView | null;
  metadata: Record<string, unknown>;
}

export interface ExecutionSectionView {
  task_contract_id: string;
  run_ids: string[];
  current_phase: WorkObjectPhase;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface DocumentationSectionView {
  delivery_pack_id?: string | null;
  references: ExternalReferenceView[];
}

export interface FollowUpActionView {
  action_type: 'ticket' | 'calendar' | 'message' | 'dashboard_update';
  description: string;
  external_ref: ExternalReferenceView;
  policy_decision_id?: string | null;
  status: FollowUpActionStatus;
}

export interface FollowUpSectionView {
  actions: FollowUpActionView[];
}

export interface WorkObjectViewModel {
  work_object_id: string;
  title: string;
  request: RequestSectionView;
  execution: ExecutionSectionView;
  documentation: DocumentationSectionView;
  follow_up: FollowUpSectionView;
  created_at: string;
  updated_at: string;
  owner_agent: string;
  tags: string[];
  parent_work_object_id?: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkObjectListItemView {
  work_object_id: string;
  task_contract_id: string;
  title: string;
  phase: WorkObjectPhase;
  updated_at: string;
  reference_count: number;
  follow_up_count: number;
}

export interface IntegrationEventView {
  event_id: string;
  work_object_id: string;
  system: string;
  action: string;
  request_payload_hash: string;
  idempotency_key: string;
  status: IntegrationEventStatus;
  external_ref?: ExternalReferenceView | null;
  attempt: number;
  latency_ms: number;
  started_at: string;
  finished_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  policy_decision_id?: string | null;
}

export interface WorkObjectDetailView {
  work_object: WorkObjectViewModel;
  timeline: IntegrationEventView[];
}
