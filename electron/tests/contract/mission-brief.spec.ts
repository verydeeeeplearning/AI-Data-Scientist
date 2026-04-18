import assert from 'node:assert/strict';

import {
  buildDeliveryGlobalContext,
  formatRenderResultNotice,
  normalizeDeliveryTenant,
  resolveProviderBackedRenderOptions,
  resolveThemeId,
} from '../../src/renderer/components/mission/missionBriefModel';

function run(): void {
  assert.equal(normalizeDeliveryTenant('  acme  '), 'acme');
  assert.equal(normalizeDeliveryTenant(''), 'default');
  assert.equal(resolveThemeId({ theme_id: ' deloitte_v1 ', region: 'apac' }), 'deloitte_v1');
  assert.deepEqual(
    buildDeliveryGlobalContext({ region: 'apac', theme_id: 'legacy_v1' }, ' acme_v2 '),
    { region: 'apac', theme_id: 'acme_v2' },
  );
  assert.deepEqual(
    buildDeliveryGlobalContext({ region: 'apac', theme_id: 'legacy_v1' }, '   '),
    { region: 'apac' },
  );
  assert.deepEqual(
    resolveProviderBackedRenderOptions(false, 'openai/gpt-5.4'),
    { providerBacked: false },
  );
  assert.deepEqual(
    resolveProviderBackedRenderOptions(true, ' openai/gpt-5.4 '),
    { providerBacked: true, model: 'openai/gpt-5.4' },
  );
  assert.equal(
    formatRenderResultNotice({
      pack_id: 'DP-2026-001',
      artifact_id: 'ART-2026-001',
      output_path: 'C:/tmp/exec-brief.pptx',
      format: 'pptx',
      verifier_status: 'pass',
      flagged_claims: [],
      pack_status: 'rendered',
      new_version: 4,
      renderer_mode: 'provider-backed',
      renderer_model: 'openai/gpt-5.4',
    }),
    'Rendered ART-2026-001 (pptx) to C:/tmp/exec-brief.pptx. Renderer: provider-backed | Model: openai/gpt-5.4.',
  );

  console.log('[contract] PASS mission-brief model');
}

run();
