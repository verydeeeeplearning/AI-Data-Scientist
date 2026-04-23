/**
 * Contract test for ExportWizardModal helper expectations.
 *
 * The modal is a pure render component, so we exercise the component's
 * default port shape and its serialization surface without mounting React.
 */

import assert from 'node:assert/strict';
import {
  ExportWizardModal,
  type ExportPort,
  type ExportWizardCandidate,
} from '../../src/renderer/components/workspace/ExportWizardModal';

const results: Array<{ name: string; ok: boolean; error?: unknown }> = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, ok: true });
  } catch (error) {
    results.push({ name, ok: false, error });
  }
}

test('ExportWizardModal default export is a React component function', () => {
  assert.equal(typeof ExportWizardModal, 'function');
});

test('ExportPort type accepts the documented call shape including audience', () => {
  const port: ExportPort = async ({ path, format, audience }) => ({
    path,
    format,
    audience,
    ok: true,
  });
  return port({ path: '/tmp/file.csv', format: 'html', audience: 'exec' }).then((payload) => {
    assert.equal(payload.path, '/tmp/file.csv');
    assert.equal(payload.format, 'html');
    assert.equal(payload.audience, 'exec');
  });
});

test('ExportWizardCandidate accepts the documented field set', () => {
  const sample: ExportWizardCandidate = {
    id: 'c1',
    name: 'Sample',
    path: '/tmp/sample.csv',
    type: 'csv',
    formats: ['json', 'parquet'],
  };
  assert.equal(sample.formats.length, 2);
});

test('ExportWizardModal props can carry a default audience', () => {
  const props = {
    open: true,
    candidates: [] satisfies ExportWizardCandidate[],
    defaultAudience: 'ml' as const,
    exportPort: (async () => ({})) satisfies ExportPort,
    onClose: () => undefined,
  };
  assert.equal(props.defaultAudience, 'ml');
});

const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
  console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
  if (!entry.ok) {
    console.log('       ', entry.error);
  }
}
console.log(
  `\nexportWizardModal.spec — ${results.length - failed.length}/${results.length} passed`,
);
if (failed.length > 0) {
  process.exitCode = 1;
}
