"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const buildSuggestedActionPrompt_1 = require("../../src/renderer/application/workspace/buildSuggestedActionPrompt");
function fakeAction(overrides = {}) {
    return {
        id: 'run_eda',
        label: 'workspace.upload.suggestedActions.runEda.label',
        description: 'workspace.upload.suggestedActions.runEda.description',
        icon: 'chart',
        requiresTarget: false,
        ...overrides,
    };
}
function fakePreview(overrides = {}) {
    return {
        fileId: 'churn.csv',
        workspacePath: 'churn.csv',
        fileName: 'churn.csv',
        sizeBytes: 1024,
        mimeType: 'text/csv',
        format: 'csv',
        rowCountEstimate: 1000,
        columns: [],
        sampleRows: [],
        dataQuality: { missingRatio: 0, duplicateRowRatio: 0, outlierColumns: [] },
        suggestedTarget: null,
        suggestedActions: [],
        ...overrides,
    };
}
function run() {
    // run_eda → references file by name
    {
        const prompt = (0, buildSuggestedActionPrompt_1.buildSuggestedActionPrompt)(fakeAction({ id: 'run_eda', requiresTarget: false }), fakePreview({ fileName: 'churn.csv' }));
        strict_1.default.match(prompt, /churn\.csv/);
        strict_1.default.match(prompt, /EDA|exploratory/i);
    }
    // baseline_after_target → uses target column when suggestedTarget present
    {
        const prompt = (0, buildSuggestedActionPrompt_1.buildSuggestedActionPrompt)(fakeAction({ id: 'baseline_after_target', requiresTarget: true }), fakePreview({
            fileName: 'churn.csv',
            suggestedTarget: { columnName: 'churn', confidence: 'high', reason: 'name_hint' },
        }));
        strict_1.default.match(prompt, /churn\.csv/);
        strict_1.default.match(prompt, /churn/);
        strict_1.default.match(prompt, /baseline/i);
    }
    // baseline_after_target → without target falls back to neutral phrasing (no `undefined`)
    {
        const prompt = (0, buildSuggestedActionPrompt_1.buildSuggestedActionPrompt)(fakeAction({ id: 'baseline_after_target', requiresTarget: true }), fakePreview({ fileName: 'data.csv', suggestedTarget: null }));
        strict_1.default.doesNotMatch(prompt, /undefined|null/);
        strict_1.default.match(prompt, /data\.csv/);
    }
    // validate_schema → mentions schema validation and file name
    {
        const prompt = (0, buildSuggestedActionPrompt_1.buildSuggestedActionPrompt)(fakeAction({ id: 'validate_schema', requiresTarget: false }), fakePreview({ fileName: 'orders.parquet' }));
        strict_1.default.match(prompt, /orders\.parquet/);
        strict_1.default.match(prompt, /schema|validate|column/i);
    }
    // isSuggestedActionAvailable: requiresTarget=true and target missing → unavailable
    {
        const available = (0, buildSuggestedActionPrompt_1.isSuggestedActionAvailable)(fakeAction({ id: 'baseline_after_target', requiresTarget: true }), fakePreview({ suggestedTarget: null }));
        strict_1.default.equal(available, false);
    }
    // isSuggestedActionAvailable: requiresTarget=false → always available
    {
        const available = (0, buildSuggestedActionPrompt_1.isSuggestedActionAvailable)(fakeAction({ id: 'run_eda', requiresTarget: false }), fakePreview({ suggestedTarget: null }));
        strict_1.default.equal(available, true);
    }
    // isSuggestedActionAvailable: requiresTarget=true with target → available
    {
        const available = (0, buildSuggestedActionPrompt_1.isSuggestedActionAvailable)(fakeAction({ id: 'baseline_after_target', requiresTarget: true }), fakePreview({
            suggestedTarget: { columnName: 'y', confidence: 'medium', reason: 'binary_values' },
        }));
        strict_1.default.equal(available, true);
    }
    // Unknown action id (forward-compat): builder must still produce a prompt referring to the file
    {
        const prompt = (0, buildSuggestedActionPrompt_1.buildSuggestedActionPrompt)(fakeAction({ id: 'run_eda', label: 'workspace.upload.future.label' }), fakePreview({ fileName: 'mystery.csv' }));
        strict_1.default.match(prompt, /mystery\.csv/);
        strict_1.default.ok(prompt.length > 0);
    }
}
run();
console.log('suggestedActionsWiring contract — OK');
