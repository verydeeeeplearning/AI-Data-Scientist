import assert from 'node:assert/strict';

import {
  hasAudienceRenderedCardContent,
  normalizeRenderedCard,
  renderCardForAudience,
  reportAudienceSwitch,
} from '../../src/renderer/infrastructure/api/cardApi';
import { resolveAudienceRenderedCardStatus } from '../../src/renderer/hooks/useAudienceRenderedCard';

async function run(): Promise<void> {
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let cases = 0;

  Object.defineProperty(globalThis, 'window', {
    value: {
      location: {
        search: '?port=19999',
      },
    },
    configurable: true,
  });

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    fetchCalls.push({ input, init });

    if (String(input).includes('/render-for-audience')) {
      return {
        ok: true,
        json: async () => ({
          renderedCard: {
            summary: 'Revenue lifted',
            body: '## Summary\n- Revenue increased',
            sections: [
              {
                id: 'impact',
                title: 'Impact',
                body: 'Revenue increased by 12%',
              },
            ],
          },
        }),
      } as Response;
    }

    return {
      ok: true,
      json: async () => ({ ok: true }),
    } as Response;
  }) as typeof fetch;

  try {
    const rendered = await renderCardForAudience({
      cardId: 'card-1',
      audience: 'exec',
      cardType: 'insight',
    });

    assert.equal(fetchCalls[0]?.input, 'http://127.0.0.1:19999/api/cards/render-for-audience');
    assert.equal(fetchCalls[0]?.init?.method, 'POST');
    assert.equal(rendered.summary, 'Revenue lifted');
    assert.equal(rendered.body, '## Summary\n- Revenue increased');
    assert.equal(rendered.sections.length, 1);
    assert.equal(rendered.sections[0]?.id, 'impact');
    cases += 5;

    await reportAudienceSwitch({
      fromAudience: 'ds',
      toAudience: 'exec',
      sessionId: 'session-1',
    });

    assert.equal(fetchCalls[1]?.input, 'http://127.0.0.1:19999/api/cards/audience-switch');
    assert.equal(fetchCalls[1]?.init?.method, 'POST');
    assert.equal(
      (fetchCalls[1]?.init?.body as string | undefined),
      JSON.stringify({
        fromAudience: 'ds',
        toAudience: 'exec',
        sessionId: 'session-1',
      }),
    );
    cases += 3;

    const normalized = normalizeRenderedCard({
      summary: 'Title',
      body: '  ',
      sections: [
        { id: 'a', title: 'A', body: 'B' },
        { id: ' ', title: 'Ignored', body: 'Ignored' },
      ],
    });
    assert.equal(normalized.summary, 'Title');
    assert.equal(normalized.body, null);
    assert.equal(normalized.sections.length, 1);
    assert.equal(hasAudienceRenderedCardContent(normalized), true);
    assert.equal(
      hasAudienceRenderedCardContent({ summary: null, body: null, sections: [] }),
      false,
    );
    cases += 4;

    globalThis.fetch = (async () => ({
      ok: true,
      json: async () => ({
        renderedCard: {
          summary: '   ',
          body: '   ',
          sections: [],
        },
      }),
    } as Response)) as typeof fetch;

    await assert.rejects(
      renderCardForAudience({
        cardId: 'card-empty',
        audience: 'ml',
        cardType: 'risk',
      }),
      (error: unknown) => {
        assert.equal(
          error instanceof Error ? error.message : String(error),
          'Audience render response did not include usable content',
        );
        return true;
      },
    );
    cases += 1;

    assert.equal(
      resolveAudienceRenderedCardStatus({
        renderedCard: null,
        isLoading: false,
        error: null,
        usesBackendRendering: false,
      }),
      'original',
    );
    assert.equal(
      resolveAudienceRenderedCardStatus({
        renderedCard: null,
        isLoading: true,
        error: null,
        usesBackendRendering: true,
      }),
      'loading-fallback',
    );
    assert.equal(
      resolveAudienceRenderedCardStatus({
        renderedCard: null,
        isLoading: false,
        error: 'backend unavailable',
        usesBackendRendering: true,
      }),
      'error-fallback',
    );
    assert.equal(
      resolveAudienceRenderedCardStatus({
        renderedCard: {
          summary: 'Executive summary',
          body: null,
          sections: [],
        },
        isLoading: false,
        error: null,
        usesBackendRendering: true,
      }),
      'rendered',
    );
    cases += 4;
  } finally {
    if (typeof originalWindow === 'undefined') {
      delete (globalThis as { window?: Window }).window;
    } else {
      Object.defineProperty(globalThis, 'window', {
        value: originalWindow,
        configurable: true,
      });
    }
    globalThis.fetch = originalFetch;
  }

  console.log(`[contract] PASS audience-rendering-port (${cases} cases)`);
}

void run().catch((error) => {
  console.error(error);
  process.exit(1);
});
