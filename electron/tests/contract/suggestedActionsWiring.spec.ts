import assert from 'node:assert/strict';

import {
  buildSuggestedActionPrompt,
  isSuggestedActionAvailable,
} from '../../src/renderer/application/workspace/buildSuggestedActionPrompt';
import type {
  UploadedFileSchemaPreview,
  UploadedFileSuggestedAction,
} from '../../src/renderer/domain/workspace/uploadedFile';

function fakeAction(
  overrides: Partial<UploadedFileSuggestedAction> = {},
): UploadedFileSuggestedAction {
  return {
    id: 'run_eda',
    label: 'workspace.upload.suggestedActions.runEda.label',
    description: 'workspace.upload.suggestedActions.runEda.description',
    icon: 'chart',
    requiresTarget: false,
    ...overrides,
  };
}

function fakePreview(
  overrides: Partial<UploadedFileSchemaPreview> = {},
): UploadedFileSchemaPreview {
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

function run(): void {
  // run_eda → references file by name
  {
    const prompt = buildSuggestedActionPrompt(
      fakeAction({ id: 'run_eda', requiresTarget: false }),
      fakePreview({ fileName: 'churn.csv' }),
    );
    assert.match(prompt, /churn\.csv/);
    assert.match(prompt, /EDA|exploratory/i);
  }

  // baseline_after_target → uses target column when suggestedTarget present
  {
    const prompt = buildSuggestedActionPrompt(
      fakeAction({ id: 'baseline_after_target', requiresTarget: true }),
      fakePreview({
        fileName: 'churn.csv',
        suggestedTarget: { columnName: 'churn', confidence: 'high', reason: 'name_hint' },
      }),
    );
    assert.match(prompt, /churn\.csv/);
    assert.match(prompt, /churn/);
    assert.match(prompt, /baseline/i);
  }

  // baseline_after_target → without target falls back to neutral phrasing (no `undefined`)
  {
    const prompt = buildSuggestedActionPrompt(
      fakeAction({ id: 'baseline_after_target', requiresTarget: true }),
      fakePreview({ fileName: 'data.csv', suggestedTarget: null }),
    );
    assert.doesNotMatch(prompt, /undefined|null/);
    assert.match(prompt, /data\.csv/);
  }

  // validate_schema → mentions schema validation and file name
  {
    const prompt = buildSuggestedActionPrompt(
      fakeAction({ id: 'validate_schema', requiresTarget: false }),
      fakePreview({ fileName: 'orders.parquet' }),
    );
    assert.match(prompt, /orders\.parquet/);
    assert.match(prompt, /schema|validate|column/i);
  }

  // isSuggestedActionAvailable: requiresTarget=true and target missing → unavailable
  {
    const available = isSuggestedActionAvailable(
      fakeAction({ id: 'baseline_after_target', requiresTarget: true }),
      fakePreview({ suggestedTarget: null }),
    );
    assert.equal(available, false);
  }

  // isSuggestedActionAvailable: requiresTarget=false → always available
  {
    const available = isSuggestedActionAvailable(
      fakeAction({ id: 'run_eda', requiresTarget: false }),
      fakePreview({ suggestedTarget: null }),
    );
    assert.equal(available, true);
  }

  // isSuggestedActionAvailable: requiresTarget=true with target → available
  {
    const available = isSuggestedActionAvailable(
      fakeAction({ id: 'baseline_after_target', requiresTarget: true }),
      fakePreview({
        suggestedTarget: { columnName: 'y', confidence: 'medium', reason: 'binary_values' },
      }),
    );
    assert.equal(available, true);
  }

  // Unknown action id (forward-compat): builder must still produce a prompt referring to the file
  {
    const prompt = buildSuggestedActionPrompt(
      fakeAction({ id: 'run_eda' as UploadedFileSuggestedAction['id'], label: 'workspace.upload.future.label' }),
      fakePreview({ fileName: 'mystery.csv' }),
    );
    assert.match(prompt, /mystery\.csv/);
    assert.ok(prompt.length > 0);
  }
}

run();
console.log('suggestedActionsWiring contract — OK');
