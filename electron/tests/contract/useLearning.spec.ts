import assert from 'node:assert/strict';

import {
  createLearningClient,
  extractHarnessWarningReviewSummary,
  readLearningGovernanceEnabled,
} from '../../src/renderer/hooks/useLearning';

type RpcCall = {
  method: string;
  params?: Record<string, unknown>;
};

async function run(): Promise<void> {
  assert.equal(readLearningGovernanceEnabled(null), false);
  assert.equal(readLearningGovernanceEnabled({}), false);
  assert.equal(
    readLearningGovernanceEnabled({ featureFlags: { selfImproveGovernanceV1: true } }),
    true,
  );
  assert.equal(
    readLearningGovernanceEnabled({ featureFlags: { selfImproveGovernanceV1: 'YES' } }),
    true,
  );
  assert.equal(
    readLearningGovernanceEnabled({ featureFlags: { selfImproveGovernanceV1: false } }),
    false,
  );

  {
    const calls: RpcCall[] = [];
    const warningItem = {
      item_id: 'LI-001',
      type: 'pattern',
      status: 'proposed',
      title: 'Harness warning: leakage',
      priority_score: 0.92,
      evidence_count: 1,
      conflict_count: 0,
      scope: 'project',
      tags: ['harness.warning', 'leakage', 'severity:high', 'surface:ws'],
      created_at: '2026-04-20T00:00:00Z',
    };
    const client = createLearningClient(async (method, params) => {
      calls.push({ method, params });
      if (method === 'config.get') {
        return { featureFlags: { selfImproveGovernanceV1: false } };
      }
      if (method === 'learning.status') {
        return {
          reviewEnabled: false,
          backlog: {
            activeWarningItems: 1,
            activeWarningRecurrences: 2,
            promotionCandidateItems: 0,
            promotionCandidateClasses: [],
            warningTypes: ['leakage'],
            surfaces: ['ws'],
            lastGcAt: null,
          },
          latestCompletedRun: null,
          latestReport: null,
          recentHistory: [],
          standingOrder: {
            orderId: 'learning_governance_weekly_gc',
            name: 'Learning Governance Weekly GC',
            enabled: true,
            cron: '0 9 * * MON',
            timezone: 'UTC',
            nextRunAt: '2026-04-21T09:00:00Z',
            lastRunAt: null,
            runCount: 0,
            failureCount: 0,
          },
        };
      }
      if (method === 'learning.inbox') {
        return { items: [warningItem], total: 1 };
      }
      if (method === 'learning.getItem') {
        return { ...warningItem, updated_at: '2026-04-20T00:05:00Z' };
      }
      throw new Error(`unexpected method: ${method}`);
    });

    const status = await client.fetchStatus();
    const inbox = await client.fetchInbox();
    const detail = await client.fetchItemDetail(warningItem);
    const reviewed = await client.reviewItem('LI-001', 'approve');
    const finalized = await client.finalizeCandidatePromotion({
      candidateId: 'failure-taxonomy-leakage',
      candidateScore: 0.82,
      baselineScore: 0.8,
      passedTasks: 1,
      totalTasks: 1,
    });

    assert.equal(status.enabled, false);
    assert.equal(status.status.reviewEnabled, false);
    assert.equal(status.status.backlog.activeWarningItems, 1);
    assert.equal(inbox.enabled, false);
    assert.deepEqual(inbox.inbox, { items: [warningItem], total: 1 });
    assert.equal(detail.enabled, false);
    assert.equal(detail.item?.item_id, 'LI-001');
    assert.equal(reviewed, false);
    assert.equal(finalized, null);
    assert.deepEqual(calls.map((call) => call.method), [
      'config.get',
      'learning.status',
      'learning.inbox',
      'learning.getItem',
    ]);
  }

  {
    const calls: RpcCall[] = [];
    const warningItem = {
      item_id: 'LI-002',
      type: 'pattern',
      status: 'proposed',
      title: 'Harness warning: leakage',
      priority_score: 0.91,
      evidence_count: 1,
      conflict_count: 0,
      scope: 'project',
      tags: ['harness.warning', 'leakage', 'severity:high', 'surface:ws'],
      created_at: '2026-04-20T00:00:00Z',
    };
    const client = createLearningClient(async (method, params) => {
      calls.push({ method, params });
      if (method === 'config.get') {
        return { featureFlags: { selfImproveGovernanceV1: true } };
      }
      if (method === 'learning.status') {
        return {
          reviewEnabled: true,
          backlog: {
            activeWarningItems: 1,
            activeWarningRecurrences: 3,
            promotionCandidateItems: 1,
            promotionCandidateClasses: ['leakage'],
            warningTypes: ['leakage'],
            surfaces: ['ws', 'daemon'],
            lastGcAt: '2026-04-20T00:05:00Z',
          },
          latestCompletedRun: {
            status: 'completed',
            summary: 'Learning governance weekly GC classified 1 item(s) across 3 recurrence(s).',
            recordedAt: '2026-04-20T00:05:00Z',
            reportPath: 'Docs/operations/gc_reports/GC_REPORT_2026-04-20_000500.md',
            totalItems: 1,
            totalRecurrences: 3,
            promotionThreshold: 3,
            promotionCandidateClasses: ['leakage'],
          },
          latestReport: {
            path: 'Docs/operations/gc_reports/GC_REPORT_2026-04-20_000500.md',
            name: 'GC_REPORT_2026-04-20_000500.md',
          },
          recentHistory: [],
          standingOrder: {
            orderId: 'learning_governance_weekly_gc',
            name: 'Learning Governance Weekly GC',
            enabled: true,
            cron: '0 9 * * MON',
            timezone: 'UTC',
            nextRunAt: '2026-04-21T09:00:00Z',
            lastRunAt: '2026-04-20T00:05:00Z',
            runCount: 1,
            failureCount: 0,
          },
        };
      }
      if (method === 'learning.inbox') {
        return {
          items: [
            {
              ...warningItem,
              metadata: {
                warningType: 'leakage',
                severity: 'high',
                surface: 'ws',
                recurrenceCount: 3,
                failureTaxonomyClass: 'leakage',
              },
            },
          ],
          total: 1,
        };
      }
      if (method === 'learning.getItem') {
        return {
          ...warningItem,
          content: 'Potential leakage detected in holdout split.\n\nSuggestion: Rebuild the split before training.',
          review_count: 0,
          updated_at: '2026-04-20T00:05:00Z',
          metadata: {
            warningType: 'leakage',
            severity: 'high',
            sessionId: 'sess-7',
            runId: 'run-2',
            surface: 'ws',
            recurrenceCount: 3,
            firstSeenAt: '2026-04-20T00:00:00Z',
            lastSeenAt: '2026-04-20T00:05:00Z',
            sessionIds: ['sess-7', 'sess-8'],
            surfaces: ['ws', 'daemon'],
            failureTaxonomyClass: 'leakage',
            failureTaxonomyRecurrenceCount: 3,
            failureTaxonomyPromotionCandidate: true,
            rawPayload: {
              type: 'leakage',
              severity: 'high',
              message: 'Potential leakage detected in holdout split.',
            },
          },
        };
      }
      if (method === 'learning.review') {
        return { ok: true };
      }
      if (method === 'learning.finalizePromotion') {
        return {
          ok: true,
          candidateId: 'failure-taxonomy-leakage',
          status: 'promoted',
          promoted: true,
          candidateScore: 0.82,
          baselineScore: 0.8,
          deltaScore: 0.02,
          deltaThreshold: 0.03,
          passedTasks: 1,
          totalTasks: 1,
          summary: 'Promoted.',
          promotedPath: 'skills/custom/failure-taxonomy-leakage.md',
          pendingPath: '.ds-agent/runtime/self_improve/pending_skills/failure-taxonomy-leakage.md',
        };
      }
      throw new Error(`unexpected method: ${method}`);
    });

    const status = await client.fetchStatus();
    const inbox = await client.fetchInbox('proposed', 'all');
    const detail = await client.fetchItemDetail(inbox.inbox.items[0]!);
    const reviewed = await client.reviewItem('LI-002', 'approve', 'ship it');
    const finalized = await client.finalizeCandidatePromotion({
      candidateId: 'failure-taxonomy-leakage',
      candidateScore: 0.82,
      baselineScore: 0.8,
      passedTasks: 1,
      totalTasks: 1,
      deltaThreshold: 0.03,
    });

    assert.equal(status.enabled, true);
    assert.equal(status.status.reviewEnabled, true);
    assert.equal(status.status.latestCompletedRun?.totalRecurrences, 3);
    assert.equal(status.status.latestReport?.name, 'GC_REPORT_2026-04-20_000500.md');
    assert.equal(inbox.enabled, true);
    assert.equal(inbox.inbox.total, 1);
    assert.equal(inbox.inbox.items[0]?.item_id, 'LI-002');
    assert.equal(inbox.inbox.items[0]?.metadata?.recurrenceCount, 3);
    assert.equal(detail.enabled, true);
    assert.equal(detail.item?.review_count, 0);
    assert.equal(detail.item?.metadata?.sessionId, 'sess-7');
    assert.deepEqual(extractHarnessWarningReviewSummary(detail.item!), {
      warningType: 'leakage',
      severity: 'high',
      surface: 'ws',
      surfaces: ['ws', 'daemon'],
      sessionId: 'sess-7',
      runId: 'run-2',
      message: 'Potential leakage detected in holdout split.',
      suggestion: 'Rebuild the split before training.',
      recurrenceCount: 3,
      taxonomyClass: 'leakage',
      promotionCandidate: true,
      firstSeenAt: '2026-04-20T00:00:00Z',
      lastSeenAt: '2026-04-20T00:05:00Z',
      rawPayload: {
        type: 'leakage',
        severity: 'high',
        message: 'Potential leakage detected in holdout split.',
      },
    });
    assert.equal(reviewed, true);
    assert.equal(finalized?.status, 'promoted');
    assert.equal(finalized?.promoted, true);
    assert.deepEqual(
      calls.map((call) => call.method),
      [
        'config.get',
        'learning.status',
        'learning.inbox',
        'learning.getItem',
        'learning.review',
        'learning.finalizePromotion',
      ],
    );
    assert.deepEqual(calls[3], {
      method: 'learning.getItem',
      params: {
        itemId: 'LI-002',
      },
    });
    assert.deepEqual(calls[4], {
      method: 'learning.review',
      params: {
        itemId: 'LI-002',
        decision: 'approve',
        comment: 'ship it',
      },
    });
    assert.deepEqual(calls[5], {
      method: 'learning.finalizePromotion',
      params: {
        candidateId: 'failure-taxonomy-leakage',
        candidateScore: 0.82,
        baselineScore: 0.8,
        passedTasks: 1,
        totalTasks: 1,
        deltaThreshold: 0.03,
      },
    });
  }

  console.log('[contract] PASS use-learning (warning detail coverage)');
}

void run().catch((error) => {
  console.error(error);
  process.exit(1);
});
