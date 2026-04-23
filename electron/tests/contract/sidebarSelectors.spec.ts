import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import type { ModelGroup } from '../../src/renderer/hooks/useModels';
import { ModeSelector } from '../../src/renderer/components/sidebar/ModeSelector';
import { ModelSelector } from '../../src/renderer/components/sidebar/ModelSelector';

const GROUPS: ModelGroup[] = [
  {
    id: 'best_quality',
    order: 1,
    titleKey: 'llm.group.best_quality.title',
    descriptionKey: 'llm.group.best_quality.description',
    emptyTitleKey: 'llm.group.best_quality.emptyTitle',
    emptyDescriptionKey: 'llm.group.best_quality.emptyDescription',
    models: [
      {
        id: 'anthropic/claude-sonnet-4-6',
        provider: 'anthropic',
        displayName: 'Claude Sonnet 4.6',
        maxContext: 200000,
        maxOutput: 64000,
        authType: 'api_key',
        providerCategory: 'api_key',
        legacy: false,
        capabilityGroup: 'best_quality',
        badges: ['strong_reasoning', 'strong_korean'],
        recommendedFor: ['data_analysis'],
      },
    ],
  },
];

function run(): void {
  const modeHtml = renderToStaticMarkup(
    createElement(ModeSelector, {
      onChange: () => undefined,
    }),
  );

  assert.match(modeHtml, /<fieldset[^>]*aria-label="Execution mode"/);
  assert.match(modeHtml, /name="sidebar-execution-mode"/);
  assert.equal((modeHtml.match(/type="radio"/g) ?? []).length, 3);
  assert.match(modeHtml, /Supervised/);

  const modelHtml = renderToStaticMarkup(
    createElement(ModelSelector, {
      onChangeModel: () => undefined,
      onChangeQualityPreset: () => undefined,
      groups: GROUPS,
    }),
  );

  assert.match(modelHtml, /aria-haspopup="dialog"/);
  assert.match(modelHtml, /aria-expanded="false"/);
  assert.match(modelHtml, /aria-controls="sidebar-model-selector-panel-[^"]+"/);
  assert.match(modelHtml, /type="button"/);

  console.log('[contract] PASS sidebar-selectors (2 cases)');
}

run();
