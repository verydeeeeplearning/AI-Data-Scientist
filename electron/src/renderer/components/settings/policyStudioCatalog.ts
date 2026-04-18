import type { MatrixAuthority, MatrixVerdict } from '../../stores/policyStore';

export type ContractAuthorityDraft =
  | 'inherit'
  | 'shadow'
  | 'supervised'
  | 'delegate'
  | 'autopilot';

export type AudienceDraft =
  | 'inherit'
  | 'junior_mentor'
  | 'peer_ds'
  | 'senior_staff'
  | 'executive'
  | 'auditor';

export type EffectiveAuthorityMode =
  | Exclude<ContractAuthorityDraft, 'inherit'>
  | 'incident'
  | 'freeze';

export interface AuthorityOption {
  value: ContractAuthorityDraft;
  label: string;
  summary: string;
}

export interface EffectiveAuthorityCard {
  value: EffectiveAuthorityMode;
  label: string;
  summary: string;
}

export interface AudiencePreview {
  label: string;
  tone: string;
  depth: string;
  uncertaintyStyle: string;
  defaultArtifacts: string[];
  sample: string[];
}

export type LegacyMode = 'auto' | 'supervised' | 'step-by-step';

export interface LegacyModeMigrationPreview {
  legacyMode: LegacyMode;
  authority: Exclude<ContractAuthorityDraft, 'inherit'>;
  audience: Exclude<AudienceDraft, 'inherit'>;
  exactMatch: boolean;
  summary: string;
  notes: string[];
}

export interface PolicyStudioPreset {
  id: string;
  label: string;
  authority: Exclude<ContractAuthorityDraft, 'inherit'>;
  audience: Exclude<AudienceDraft, 'inherit'>;
  summary: string;
}

export const CONTRACT_AUTHORITY_OPTIONS: AuthorityOption[] = [
  {
    value: 'inherit',
    label: 'Inherit',
    summary: 'Use the mission default first, then fall back to the legacy runtime mode.',
  },
  {
    value: 'shadow',
    label: 'Shadow',
    summary: 'Rehearse and explain without causing side effects.',
  },
  {
    value: 'supervised',
    label: 'Supervised',
    summary: 'Execute safe actions directly and route sensitive work to approval.',
  },
  {
    value: 'delegate',
    label: 'Delegate',
    summary: 'Run low-risk repeatable work autonomously inside the delegated scope.',
  },
  {
    value: 'autopilot',
    label: 'Autopilot',
    summary: 'Operate autonomously inside the certified mission boundary.',
  },
];

export const EFFECTIVE_AUTHORITY_CARDS: EffectiveAuthorityCard[] = [
  {
    value: 'shadow',
    label: 'Shadow',
    summary: 'Dry-run planning and explicit escalation notes.',
  },
  {
    value: 'supervised',
    label: 'Supervised',
    summary: 'Safe actions execute, sensitive actions stop for approval.',
  },
  {
    value: 'delegate',
    label: 'Delegate',
    summary: 'Routine work is autonomous, sensitive work still escalates.',
  },
  {
    value: 'autopilot',
    label: 'Autopilot',
    summary: 'Mission-certified execution continues without routine approvals.',
  },
  {
    value: 'incident',
    label: 'Incident',
    summary: 'Prioritize mitigation, but keep irreversible actions on approval paths.',
  },
  {
    value: 'freeze',
    label: 'Freeze',
    summary: 'Treat the environment as read-only for write-side actions.',
  },
];

export const AUDIENCE_OPTIONS: { value: AudienceDraft; label: string }[] = [
  { value: 'inherit', label: 'Inherit' },
  { value: 'junior_mentor', label: 'Junior Mentor' },
  { value: 'peer_ds', label: 'Peer DS' },
  { value: 'senior_staff', label: 'Senior/Staff' },
  { value: 'executive', label: 'Executive' },
  { value: 'auditor', label: 'Auditor' },
];

export const AUDIENCE_PREVIEWS: Record<Exclude<AudienceDraft, 'inherit'>, AudiencePreview> = {
  junior_mentor: {
    label: 'Junior Mentor',
    tone: 'Educational and explicit',
    depth: 'Very detailed',
    uncertaintyStyle: 'Call out caveats and what to verify next.',
    defaultArtifacts: ['checklist', 'annotated_notes', 'commented_code'],
    sample: [
      'What changed: revenue dipped after the checkout rollout.',
      'Why we think it happened: the new flow adds one extra required field and abandonment rose in that step.',
      'Next step: verify the field-level drop-off and prepare a rollback checklist before touching production.',
    ],
  },
  peer_ds: {
    label: 'Peer DS',
    tone: 'Collegial and concise',
    depth: 'Medium',
    uncertaintyStyle: 'Use confidence intervals or explicit error bars.',
    defaultArtifacts: ['reproducible_notebook', 'sql', 'analysis_appendix'],
    sample: [
      'Observed a 4.2% WoW conversion drop concentrated in the checkout submit stage.',
      'Primary hypothesis is friction from the new mandatory field; matched-control traffic suggests a real effect but sample size is still modest.',
      'Recommended follow-up is a rollback rehearsal plus a stratified funnel cut by browser and acquisition channel.',
    ],
  },
  senior_staff: {
    label: 'Senior/Staff',
    tone: 'Direct and decision-focused',
    depth: 'Focused',
    uncertaintyStyle: 'Lead with confidence and the caveat that changes the decision.',
    defaultArtifacts: ['decision_memo', 'diff', 'risk_summary'],
    sample: [
      'Decision: pause the checkout variant and revert the required-field change.',
      'Risk: holding the current state likely costs roughly one week of conversion and complicates attribution if more traffic accumulates.',
      'Caveat: root cause is high-confidence at the step level, but device-specific degradation still needs one more cut after rollback.',
    ],
  },
  executive: {
    label: 'Executive',
    tone: 'Business-first and brief',
    depth: 'Minimal',
    uncertaintyStyle: 'Use SAFE / REVIEW / DANGER labels.',
    defaultArtifacts: ['exec_brief', 'action_card'],
    sample: [
      'Situation: checkout conversion fell immediately after the latest release.',
      'Impact: DANGER. Revenue exposure is material if we keep the change live through the week.',
      'Recommendation: revert now, confirm recovery today, and return with a root-cause note plus options tomorrow morning.',
    ],
  },
  auditor: {
    label: 'Auditor',
    tone: 'Provenance-first and factual',
    depth: 'Very detailed',
    uncertaintyStyle: 'State evidence sources and policy references explicitly.',
    defaultArtifacts: ['audit_trail', 'lineage_report', 'approval_history'],
    sample: [
      'Source evidence: warehouse funnel query `checkout_drop_v3.sql`, release ticket WEB-241, and approval history from runtime audit log.',
      'Observed variance exceeds the pre-release tolerance documented in the launch checklist; rollback remains pending approval because production writes are restricted.',
      'Open item: no direct user-level replay is attached yet, so field-specific causality remains unverified in current records.',
    ],
  },
};

export const POLICY_STUDIO_PRESETS: PolicyStudioPreset[] = [
  {
    id: 'delegate-peer',
    label: 'Delegated Peer',
    authority: 'delegate',
    audience: 'peer_ds',
    summary: 'Routine autonomous analysis with the default peer DS reporting style.',
  },
  {
    id: 'executive-review',
    label: 'Executive Review',
    authority: 'supervised',
    audience: 'executive',
    summary: 'Keep approvals in the loop and shape the output as an executive brief.',
  },
  {
    id: 'audit-guard',
    label: 'Audit Guard',
    authority: 'supervised',
    audience: 'auditor',
    summary: 'Preserve approval gates while shifting the output toward provenance and policy references.',
  },
  {
    id: 'mentor-walkthrough',
    label: 'Mentor Walkthrough',
    authority: 'supervised',
    audience: 'junior_mentor',
    summary: 'Use step-by-step mentoring tone without keeping the whole session in legacy step-by-step mode.',
  },
];

const AUTHORITY_LABELS: Record<EffectiveAuthorityMode, string> = {
  shadow: 'Shadow',
  supervised: 'Supervised',
  delegate: 'Delegate',
  autopilot: 'Autopilot',
  incident: 'Incident',
  freeze: 'Freeze',
};

const AUDIENCE_LABELS: Record<Exclude<AudienceDraft, 'inherit'>, string> = {
  junior_mentor: 'Junior Mentor',
  peer_ds: 'Peer DS',
  senior_staff: 'Senior/Staff',
  executive: 'Executive',
  auditor: 'Auditor',
};

export const MATRIX_AUTHORITY_COLUMNS: { value: MatrixAuthority; label: string }[] = [
  { value: 'shadow', label: 'Shadow' },
  { value: 'supervised', label: 'Supervised' },
  { value: 'delegate', label: 'Delegate' },
  { value: 'autopilot', label: 'Autopilot' },
  { value: 'incident', label: 'Incident' },
  { value: 'freeze', label: 'Freeze' },
];

export const MATRIX_VERDICT_OPTIONS: { value: MatrixVerdict; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'ask', label: 'Ask' },
  { value: 'approve', label: 'Approve' },
  { value: 'dual', label: 'Dual' },
  { value: 'skip', label: 'Skip' },
];

export function isContractAuthorityDraft(value: string | null | undefined): value is Exclude<ContractAuthorityDraft, 'inherit'> {
  return value === 'shadow'
    || value === 'supervised'
    || value === 'delegate'
    || value === 'autopilot';
}

export function isAudienceDraft(value: string | null | undefined): value is Exclude<AudienceDraft, 'inherit'> {
  return value === 'junior_mentor'
    || value === 'peer_ds'
    || value === 'senior_staff'
    || value === 'executive'
    || value === 'auditor';
}

export function isEffectiveAuthorityMode(value: string | null | undefined): value is EffectiveAuthorityMode {
  return value === 'shadow'
    || value === 'supervised'
    || value === 'delegate'
    || value === 'autopilot'
    || value === 'incident'
    || value === 'freeze';
}

export function formatAuthorityLabel(value: string | null | undefined): string {
  if (!value) {
    return 'Inherit';
  }
  if (isEffectiveAuthorityMode(value)) {
    return AUTHORITY_LABELS[value];
  }
  return value;
}

export function formatAudienceLabel(value: string | null | undefined): string {
  if (!value) {
    return 'Inherit';
  }
  if (isAudienceDraft(value)) {
    return AUDIENCE_LABELS[value];
  }
  return value;
}

export function formatMatrixVerdictLabel(value: MatrixVerdict): string {
  return MATRIX_VERDICT_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function isLegacyMode(value: string | null | undefined): value is LegacyMode {
  return value === 'auto'
    || value === 'supervised'
    || value === 'step-by-step';
}

export function buildLegacyModeMigrationPreview(
  value: string | null | undefined,
): LegacyModeMigrationPreview {
  const legacyMode: LegacyMode = isLegacyMode(value) ? value : 'auto';

  if (legacyMode === 'auto') {
    return {
      legacyMode,
      authority: 'delegate',
      audience: 'peer_ds',
      exactMatch: true,
      summary: 'Auto maps cleanly to delegated autonomous execution with the peer DS reporting default.',
      notes: [
        'Apply these defaults when you want explicit TaskContract control instead of inheriting the legacy runtime mode.',
        'Add a mission pack before moving the same workflow into autopilot.',
      ],
    };
  }

  if (legacyMode === 'supervised') {
    return {
      legacyMode,
      authority: 'supervised',
      audience: 'peer_ds',
      exactMatch: true,
      summary: 'Supervised maps directly to explicit supervised authority while keeping the peer DS reporting default.',
      notes: [
        'Sensitive or write-side work still routes to approval under supervised authority.',
        'Leave the contract on inherit if you want the whole app to keep following the shared legacy mode.',
      ],
    };
  }

  return {
    legacyMode,
    authority: 'supervised',
    audience: 'junior_mentor',
    exactMatch: false,
    summary: 'Step-by-step has no exact authority-axis equivalent; supervised plus a mentor-style audience is the closest migration baseline.',
    notes: [
      'Keep the legacy mode if you still need approval on every step.',
      'Use action-matrix overrides or a freeze/shadow guardrail before removing the legacy step-by-step mode.',
    ],
  };
}
