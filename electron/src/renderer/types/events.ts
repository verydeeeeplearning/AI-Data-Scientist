/**
 * Canonical backend→frontend event payload types.
 *
 * Each interface here is the single source of truth for an event received via
 * the WebSocket RPC channel. The matching Python TypedDicts live in
 * ``src/ds_agent/api/event_schemas.py``.
 *
 * Keep both files in sync when adding or changing events.
 */

import type { MissionContextPatch } from '../domain/mission';

// ---------------------------------------------------------------------------
// DS Workflow events
// ---------------------------------------------------------------------------

/** ``workflow.step`` — DS pipeline stage transition. */
export interface WorkflowStepEvent {
  stage: string;   // e.g. "data_loading" | "profiling" | "modeling"
  status: string;  // "running" | "done" | "error"
  score?: number;
}

/** ``quality.update`` — per-stage quality score update. */
export interface QualityUpdateEvent {
  stage: string;
  score?: number;
  overall?: number;  // 0-100 overall quality score
  grade?: string;    // "A" | "B" | "C" | "D" | "F"
}

/**
 * ``experiment.log`` — ML model training/evaluation result.
 *
 * Emitted by ``ExperimentTrackerHook`` after ``train_model`` or
 * ``evaluate_model`` succeeds. Matches ``Experiment`` in ``workflowStore.ts``.
 */
export interface ExperimentLogEvent {
  id: string;
  model: string;
  isBaseline: boolean;
  metrics: Record<string, number>;
  trainingTime?: number;    // seconds
  timestamp: number;        // Unix epoch milliseconds
}

/** ``harness.warning`` — DS harness quality warning. */
export interface HarnessWarningEvent {
  id: string;
  type: string;
  severity: 'high' | 'medium' | 'low';
  message: string;
  suggestion?: string;
}

export interface VerifierAutoRunEvent {
  sessionId: string | null;
  runId: string | null;
  taskId: string;
  mode: string;
  status: 'success' | 'timeout' | 'error';
  durationMs: number;
  verdictId?: string;
  result?: string;
  blockingIssueCount?: number;
  confidenceScore?: number;
  confidenceGrade?: 'high' | 'medium' | 'low' | 'insufficient';
  errorType?: string;
}

/**
 * ``profile.results`` — structured data profiling results.
 *
 * Emitted by ``ProfileResultsHook`` after ``data_profiler`` succeeds.
 */
export interface ProfileResultsEvent {
  summary: string;           // truncated profile output (max 500 chars)
  grade: string;             // "A" | "B" | "C" | "D"
  rows: number;
  columns: number;
  missingPct: number;        // 0-100
  issues: Array<{ issue: string; detail: string }>;
}

// ---------------------------------------------------------------------------
// Budget / context events
// ---------------------------------------------------------------------------

/** ``budget.detail`` — token/cost usage update. */
export interface BudgetDetailEvent {
  tokensUsed: number;
  tokensMax: number;
  costUsd: number;
  costMax: number;
  iterationsUsed: number;
  iterationsMax: number;
}

export interface BudgetWarningEvent {
  dimension: string;
  level: 'warning' | 'critical' | 'exhausted';
  pct: number;
  message: string;
}

/** ``context.status`` — context window usage. */
export interface ContextStatusEvent {
  usedPct: number;    // 0-100
  compressed: boolean;
}

export interface MissionContextDeltaPayload {
  dataSources?: MissionContextPatch['dataSources'];
  deliverables?: MissionContextPatch['deliverables'];
  constraints?: MissionContextPatch['constraints'];
}

export interface MissionContextUpdatedEvent extends MissionContextPatch {
  sessionId?: string | null;
  delta?: MissionContextDeltaPayload;
}

// ---------------------------------------------------------------------------
// Plan / reasoning events
// ---------------------------------------------------------------------------

export type PlanNodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface PlanNode {
  id: string;
  parentId?: string | null;
  label: string;
  description?: string;
  status: PlanNodeStatus;
  estimatedDurationSec?: number;
  startedAt?: number;
  completedAt?: number;
  reasoningRefs: string[];
  toolEventRefs: string[];
  children: PlanNode[];
}

export type PlanNodePatch = Partial<Omit<PlanNode, 'id'>>;

export interface ReplanDiff {
  oldNodes: PlanNode[];
  newNodes: PlanNode[];
  added: string[];
  removed: string[];
  modified: string[];
  reason: string;
}

export interface PlanCreatedEvent {
  planTree: PlanNode;
}

export interface PlanUpdatedEvent {
  nodeId: string;
  updates: PlanNodePatch;
}

export interface PlanReplannedEvent {
  diff: ReplanDiff;
}

export interface ReasoningEmittedEvent {
  emittedAt: number;
  id?: string;
  planNodeId?: string;
  thinking?: string;
  hypothesis?: string;
  action?: string;
  observation?: string;
  decision?: string;
}

// ---------------------------------------------------------------------------
// Result-card transport
// ---------------------------------------------------------------------------

/**
 * Shared result-card payload shape used by ``stream.done`` and persisted chat
 * history hydration. Legacy ``id`` fallback is handled only at normalization
 * boundaries in the renderer; canonical wire payloads use ``cardId``.
 */
export type ResultCardType = 'insight' | 'experiment' | 'risk' | 'artifact' | 'other';

export interface ResultCardSourcePayload {
  messageId: string;
  runId: string;
  toolCallId?: string | null;
}

export interface ResultCardPayload {
  cardId: string;
  resultId: string;
  type: ResultCardType;
  createdAt: number;
  source: ResultCardSourcePayload;
  trustStrip?: Record<string, unknown> | null;
  pinned: boolean;
  archived: boolean;
  [key: string]: unknown;
}

export interface CardLifecycleEvent {
  cardId: string;
  resultId: string;
  messageId?: string | null;
}

export interface StreamDoneEvent {
  content: string;
  cost?: number;
  messageId?: string | null;
  cards?: ResultCardPayload[];
}

// ---------------------------------------------------------------------------
// Approval events
// ---------------------------------------------------------------------------

export interface ApprovalEvent {
  approvalId: string;
  sessionId: string;
  runId?: string | null;
  surface: string;
  question: string;
  kind: string;
  metadata: Record<string, unknown>;
  options: string[];
  default?: string | null;
  status: 'pending' | 'approved' | 'rejected';
  response?: string | null;
  source?: string | null;
  actor?: string | null;
  createdAt: number;
  updatedAt: number;
  resolvedAt?: number | null;
}

/**
 * ``sandbox.violation`` — sandbox blocked or flagged a runtime action.
 *
 * Mirror of ``SandboxViolationEvent`` in ``api/event_schemas.py``. Emitted
 * once per `SandboxViolation` after a tool runs in the sandbox.
 */
export interface SandboxViolationEvent {
  kind: 'filesystem' | 'network' | 'subprocess' | 'resource';
  detail: string;
  blocked: boolean;
  sessionId?: string | null;
  runId?: string | null;
  tool: string;
  timestamp: number;  // seconds since epoch
}

// ---------------------------------------------------------------------------
// File / artifact events
// ---------------------------------------------------------------------------

/** ``file.created`` — a file was written in the workspace. */
export interface FileCreatedEvent {
  path: string;  // workspace-relative path (forward slashes)
  type: string;  // file extension without dot
  size: number;  // bytes
}

/** ``workspace.changed`` — workspace contents changed; refresh file list. */
export interface WorkspaceChangedEvent {
  tool: string;
}

// ---------------------------------------------------------------------------
// Agent events
// ---------------------------------------------------------------------------

/** ``agent.thinking`` — LLM extended thinking block. */
export interface AgentThinkingEvent {
  thinking: string;
}

/** ``agent.delta`` — streaming LLM token delta. */
export interface AgentDeltaEvent {
  delta: string;
}

/** ``agent.done`` — agent turn completed. */
export interface AgentDoneEvent {
  content: string;
  iterations: number;
  totalCostUsd: number;
}

// ---------------------------------------------------------------------------
// Union for typed event dispatch
// ---------------------------------------------------------------------------

export interface EventPayloadMap {
  'workflow.step': WorkflowStepEvent;
  'quality.update': QualityUpdateEvent;
  'experiment.log': ExperimentLogEvent;
  'harness.warning': HarnessWarningEvent;
  'verifier.auto_run': VerifierAutoRunEvent;
  'profile.results': ProfileResultsEvent;
  'budget.detail': BudgetDetailEvent;
  'budget.warning': BudgetWarningEvent;
  'context.status': ContextStatusEvent;
  'mission.context.updated': MissionContextUpdatedEvent;
  'plan.created': PlanCreatedEvent;
  'plan.updated': PlanUpdatedEvent;
  'plan.replanned': PlanReplannedEvent;
  'reasoning.emitted': ReasoningEmittedEvent;
  'stream.done': StreamDoneEvent;
  'card.created': CardLifecycleEvent;
  'card.updated': CardLifecycleEvent;
  'card.pinned': CardLifecycleEvent;
  'approval.requested': ApprovalEvent;
  'approval.resolved': ApprovalEvent;
  'sandbox.violation': SandboxViolationEvent;
  'file.created': FileCreatedEvent;
  'workspace.changed': WorkspaceChangedEvent;
  'agent.thinking': AgentThinkingEvent;
  'agent.delta': AgentDeltaEvent;
  'agent.done': AgentDoneEvent;
}
