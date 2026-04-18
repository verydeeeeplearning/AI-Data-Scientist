export interface CertificationStatsView {
  shadow_runs_passed: number;
  critical_violations: number;
  verifier_avg_score: number | null;
  rollback_rehearsal_passed: boolean;
}

export interface CertificationRecordView {
  level: string;
  transition_from: string | null;
  approved_by: string[];
  approved_at: string;
  evidence_ref: string | null;
  next_review: string | null;
}

export interface CertificationStatusView {
  mission_name: string;
  mission_version: number;
  current_level: string | null;
  effective_level: string | null;
  next_target: string | null;
  required_approvers: number;
  certified_for_next_target: boolean;
  gaps: string[];
  stats: CertificationStatsView;
  latest_certification: CertificationRecordView | null;
}

export interface CertificationSubmissionView {
  mission_name: string;
  mission_version: number;
  target_level: string;
  status: string;
  current_level: string | null;
  required_approvers: number;
  approved_by: string[];
  gaps: string[];
  stats: CertificationStatsView;
  certification: CertificationRecordView | null;
}
