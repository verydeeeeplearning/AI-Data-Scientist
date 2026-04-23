"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.STAGE_METADATA = exports.STAGE_ORDER = void 0;
exports.getStageMetadata = getStageMetadata;
exports.createExecutionToolEvent = createExecutionToolEvent;
exports.createStage = createStage;
exports.STAGE_ORDER = Object.freeze([
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
exports.STAGE_METADATA = Object.freeze({
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
function getStageMetadata(key) {
    return exports.STAGE_METADATA[key];
}
function createExecutionToolEvent(overrides) {
    return Object.freeze({
        category: 'core_ds',
        ...overrides,
    });
}
function createStage(overrides) {
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
