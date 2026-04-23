"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.USE_CASE_SPECS = exports.ONBOARDING_USE_CASE_IDS = exports.DEFAULT_USE_CASE_ID = void 0;
exports.resolveUseCase = resolveUseCase;
exports.DEFAULT_USE_CASE_ID = 'general';
exports.ONBOARDING_USE_CASE_IDS = [
    'data_analysis',
    'reporting',
    'prediction',
    'dashboard',
    'sql_exploration',
    'weekly_kpi_triage',
    'ab_test_analysis',
    'general',
];
exports.USE_CASE_SPECS = {
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
function resolveUseCase(useCaseId) {
    if (!useCaseId) {
        return exports.USE_CASE_SPECS[exports.DEFAULT_USE_CASE_ID];
    }
    return exports.USE_CASE_SPECS[useCaseId] ?? exports.USE_CASE_SPECS[exports.DEFAULT_USE_CASE_ID];
}
