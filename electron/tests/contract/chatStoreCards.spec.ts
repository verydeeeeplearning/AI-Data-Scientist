import assert from 'node:assert/strict';

import {
  normalizeResultCardPayload,
  normalizeStreamDonePayload,
  useChatStore,
  type ResultCardRecord,
} from '../../src/renderer/stores/chatStore';

function makeCard(
  overrides: Partial<ResultCardRecord> = {},
): ResultCardRecord {
  return {
    cardId: 'card-1',
    resultId: 'result-1',
    type: 'other',
    createdAt: 1_713_650_000,
    source: {
      messageId: 'msg-assistant-1',
      runId: 'run-1',
      toolCallId: null,
    },
    pinned: false,
    archived: false,
    trustStrip: null,
    title: 'Fallback',
    body: 'payload',
    ...overrides,
  };
}

function resetStore(): void {
  useChatStore.setState({
    messages: [],
    toolActivities: [],
    isStreaming: false,
    streamBuffer: '',
    sessionId: null,
    cardsById: {},
    cardIdsByMessageId: {},
  });
}

function run(): void {
  // === stream.done normalization preserves explicit messageId/cardId/resultId split ===
  {
    const normalized = normalizeStreamDonePayload({
      content: 'Analysis complete.',
      cost: 0.42,
      messageId: 'msg-assistant-1',
      cards: [
        {
          cardId: 'card-1',
          resultId: 'result-1',
          type: 'insight',
          createdAt: 1_713_650_000,
          source: {
            messageId: 'msg-assistant-1',
            runId: 'run-1',
          },
          pinned: false,
          archived: false,
          title: 'Retention lifted',
        },
      ],
    });

    assert.equal(normalized.messageId, 'msg-assistant-1');
    assert.equal(normalized.cards.length, 1);
    assert.equal(normalized.cards[0].cardId, 'card-1');
    assert.equal(normalized.cards[0].resultId, 'result-1');
    assert.equal(normalized.cards[0].source.messageId, 'msg-assistant-1');
  }

  // === legacy id fallback stays at normalization boundary ===
  {
    const normalized = normalizeResultCardPayload(
      {
        id: 'legacy-card-1',
        type: 'other',
        createdAt: 1_713_650_000,
        source: {
          runId: 'run-legacy',
        },
        title: 'Legacy',
        body: 'legacy payload',
      },
      { messageIdFallback: 'msg-legacy-1' },
    );

    assert.ok(normalized);
    assert.equal(normalized?.cardId, 'legacy-card-1');
    assert.equal(normalized?.resultId, 'legacy-card-1');
    assert.equal(normalized?.source.messageId, 'msg-legacy-1');
    assert.equal('id' in (normalized ?? {}), false);
  }

  // === store hydrates cards and indexes them by source message id ===
  {
    resetStore();
    useChatStore.getState().replaceConversation(
      [
        { messageId: 'msg-user-1', role: 'user', content: 'Analyze retention' },
        { messageId: 'msg-assistant-1', role: 'assistant', content: 'Summary' },
      ],
      'session-1',
      [
        makeCard(),
        makeCard({
          cardId: 'card-2',
          resultId: 'result-2',
          createdAt: 1_713_650_010,
          title: 'Follow-up',
        }),
      ],
    );

    const state = useChatStore.getState();
    assert.equal(state.sessionId, 'session-1');
    assert.deepEqual(state.cardIdsByMessageId['msg-assistant-1'], ['card-1', 'card-2']);
    assert.equal(state.cardsById['card-2']?.resultId, 'result-2');
  }

  // === upsertCards merges updates and replaceConversation clears prior card state ===
  {
    useChatStore.getState().upsertCards([
      makeCard({
        cardId: 'card-1',
        resultId: 'result-1',
        pinned: true,
      }),
    ]);

    let state = useChatStore.getState();
    assert.equal(state.cardsById['card-1']?.pinned, true);

    useChatStore.getState().replaceConversation(
      [{ messageId: 'msg-user-2', role: 'user', content: 'New session' }],
      'session-2',
      [],
    );

    state = useChatStore.getState();
    assert.equal(state.sessionId, 'session-2');
    assert.deepEqual(state.cardsById, {});
    assert.deepEqual(state.cardIdsByMessageId, {});
  }

  console.log('[contract] PASS chat-store-cards (4 cases)');
}

run();
