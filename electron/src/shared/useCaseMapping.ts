export const DEFAULT_USE_CASE_ID = 'general' as const;

export const ONBOARDING_USE_CASE_IDS = [
  'data_analysis',
  'reporting',
  'prediction',
  'dashboard',
  'sql_exploration',
  'weekly_kpi_triage',
  'ab_test_analysis',
  'general',
] as const;

export type OnboardingUseCaseId = (typeof ONBOARDING_USE_CASE_IDS)[number];

export interface UseCaseSpec {
  useCaseId: OnboardingUseCaseId;
  contractType: string;
  defaultMission: string | null;
  defaultAuthority: 'shadow' | 'supervised' | 'delegate' | 'autopilot';
  defaultAudience: 'junior_mentor' | 'peer_ds' | 'senior_staff' | 'executive' | 'auditor';
  defaultDeliverableSpecs: ReadonlyArray<{
    type: string;
    audience: string;
    format: string;
  }>;
}

export const USE_CASE_SPECS: Record<OnboardingUseCaseId, UseCaseSpec> = {
  data_analysis: {
    useCaseId: 'data_analysis',
    contractType: 'eda',
    defaultMission: 'data_analysis',
    defaultAuthority: 'supervised',
    defaultAudience: 'senior_staff',
    defaultDeliverableSpecs: [
      { type: 'dashboard', audience: 'pm', format: 'html' },
    ],
  },
  reporting: {
    useCaseId: 'reporting',
    contractType: 'reporting',
    defaultMission: 'reporting',
    defaultAuthority: 'supervised',
    defaultAudience: 'executive',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
      { type: 'exec_brief', audience: 'executive', format: 'pptx' },
    ],
  },
  prediction: {
    useCaseId: 'prediction',
    contractType: 'prediction',
    defaultMission: 'prediction',
    defaultAuthority: 'supervised',
    defaultAudience: 'peer_ds',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
      { type: 'notebook', audience: 'ml_engineer', format: 'ipynb' },
    ],
  },
  dashboard: {
    useCaseId: 'dashboard',
    contractType: 'dashboard',
    defaultMission: 'dashboard',
    defaultAuthority: 'supervised',
    defaultAudience: 'senior_staff',
    defaultDeliverableSpecs: [
      { type: 'dashboard', audience: 'pm', format: 'html' },
      { type: 'exec_brief', audience: 'executive', format: 'pptx' },
    ],
  },
  sql_exploration: {
    useCaseId: 'sql_exploration',
    contractType: 'sql_exploration',
    defaultMission: 'sql_exploration',
    defaultAuthority: 'delegate',
    defaultAudience: 'peer_ds',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
    ],
  },
  weekly_kpi_triage: {
    useCaseId: 'weekly_kpi_triage',
    contractType: 'kpi_triage',
    defaultMission: 'weekly-kpi-triage',
    defaultAuthority: 'delegate',
    defaultAudience: 'senior_staff',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
      { type: 'exec_brief', audience: 'executive', format: 'pptx' },
    ],
  },
  ab_test_analysis: {
    useCaseId: 'ab_test_analysis',
    contractType: 'experiment_compare',
    defaultMission: 'ab-test-analysis',
    defaultAuthority: 'supervised',
    defaultAudience: 'executive',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
      { type: 'exec_brief', audience: 'executive', format: 'pptx' },
    ],
  },
  general: {
    useCaseId: 'general',
    contractType: 'eda',
    defaultMission: 'general',
    defaultAuthority: 'supervised',
    defaultAudience: 'senior_staff',
    defaultDeliverableSpecs: [
      { type: 'ds_appendix', audience: 'ds_peer', format: 'markdown' },
    ],
  },
};

export function resolveUseCase(useCaseId: string | null | undefined): UseCaseSpec {
  if (!useCaseId) {
    return USE_CASE_SPECS[DEFAULT_USE_CASE_ID];
  }
  return USE_CASE_SPECS[useCaseId as OnboardingUseCaseId] ?? USE_CASE_SPECS[DEFAULT_USE_CASE_ID];
}
