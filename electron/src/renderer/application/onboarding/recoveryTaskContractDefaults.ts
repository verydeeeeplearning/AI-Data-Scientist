import {
  resolveUseCase,
  type OnboardingUseCaseId,
  type UseCaseSpec,
} from '../../../shared/useCaseMapping';

export interface RecoveryTaskContractGoalBriefTemplate {
  ds_problem_statement: string;
  comparison_baseline: string;
  decision_to_make: string;
  expected_effort: string;
}

export interface RecoveryTaskContractDefaults {
  label: string;
  useCaseSpec: UseCaseSpec;
  goalBriefTemplate: RecoveryTaskContractGoalBriefTemplate;
}

export const RECOVERY_TASK_CONTRACT_USE_CASE_LABELS = {
  data_analysis: 'Data Analysis',
  reporting: 'Reporting',
  prediction: 'Prediction',
  dashboard: 'Dashboard',
  sql_exploration: 'SQL Exploration',
  weekly_kpi_triage: 'Weekly KPI Triage',
  ab_test_analysis: 'A/B Test Analysis',
  general: 'General',
} satisfies Record<OnboardingUseCaseId, string>;

const RECOVERY_TASK_CONTRACT_GOAL_BRIEF_TEMPLATES = {
  data_analysis: {
    ds_problem_statement: 'Perform exploratory analysis and surface the main drivers.',
    comparison_baseline: 'Descriptive statistics and the current reporting baseline.',
    decision_to_make: 'Decide which findings merit action or deeper follow-up.',
    expected_effort: 'S',
  },
  reporting: {
    ds_problem_statement: 'Synthesize the analysis into a stakeholder-ready narrative.',
    comparison_baseline: 'Current reporting outputs and recent period comparisons.',
    decision_to_make: 'Decide what conclusions and actions should be communicated.',
    expected_effort: 'S',
  },
  prediction: {
    ds_problem_statement: 'Frame the supervised prediction problem and evaluation plan.',
    comparison_baseline: 'A baseline model and the current heuristic process.',
    decision_to_make: 'Decide whether a predictive model is viable and what to ship next.',
    expected_effort: 'M',
  },
  dashboard: {
    ds_problem_statement: 'Define the KPIs, slices, and views needed for the dashboard.',
    comparison_baseline: 'Existing KPI reporting and current dashboard coverage.',
    decision_to_make: 'Decide which dashboard views and metrics should be prioritized.',
    expected_effort: 'S',
  },
  sql_exploration: {
    ds_problem_statement: 'Investigate the dataset with SQL-oriented analysis.',
    comparison_baseline: 'Current KPI pulls and known query outputs.',
    decision_to_make: 'Decide which findings or follow-up queries are needed.',
    expected_effort: 'S',
  },
  weekly_kpi_triage: {
    ds_problem_statement:
      'Triage the weekly KPI movement, identify the likely driver, and assign the next action.',
    comparison_baseline: 'The prior weekly baseline and the most comparable recent period.',
    decision_to_make:
      'Decide whether to escalate, remediate, or monitor the KPI movement.',
    expected_effort: 'S',
  },
  ab_test_analysis: {
    ds_problem_statement:
      'Validate the A/B test design, quantify the effect size, and prepare the ship-or-hold recommendation.',
    comparison_baseline:
      'The control cohort, pre-launch expectations, and guardrail metrics.',
    decision_to_make:
      'Decide whether to ship, iterate, or stop based on the experiment evidence.',
    expected_effort: 'M',
  },
  general: {
    ds_problem_statement: 'Clarify the first data-science workflow and next analysis step.',
    comparison_baseline: 'Current qualitative understanding and available descriptive data.',
    decision_to_make: 'Decide the next best analysis path and expected output.',
    expected_effort: 'S',
  },
} satisfies Record<OnboardingUseCaseId, RecoveryTaskContractGoalBriefTemplate>;

export function resolveRecoveryTaskContractDefaults(
  useCaseId: string | null | undefined,
): RecoveryTaskContractDefaults {
  const useCaseSpec = resolveUseCase(useCaseId);

  return {
    label: RECOVERY_TASK_CONTRACT_USE_CASE_LABELS[useCaseSpec.useCaseId],
    useCaseSpec,
    goalBriefTemplate: RECOVERY_TASK_CONTRACT_GOAL_BRIEF_TEMPLATES[useCaseSpec.useCaseId],
  };
}
