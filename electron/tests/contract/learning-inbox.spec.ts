import assert from 'node:assert/strict';

import {
  createLearningClient,
  extractHarnessWarningReviewSummary,
  isHarnessWarningLearningItem,
  normalizeLearningGovernanceStatus,
  normalizeLearningItemDetail,
  readLearningGovernanceEnabled,
} from '../../src/renderer/hooks/useLearning';

interface LearningItemView {
  item_id: string;
  type: string;
  status: string;
  title: string;
  priority_score: number;
  evidence_count: number;
  conflict_count: number;
  scope: string;
  tags: string[];
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface LearningInboxView {
  items: LearningItemView[];
  total: number;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value as Record<string, unknown>;
}

async function run(): Promise<void> {
  const proposed: LearningItemView = {
    item_id: 'LI-001',
    type: 'kb_entry',
    status: 'proposed',
    title: 'Churn definition',
    priority_score: 0.72,
    evidence_count: 3,
    conflict_count: 0,
    scope: 'domain',
    tags: ['churn', 'definition'],
    created_at: '2026-04-16T10:00:00Z',
  };

  assert.equal(proposed.item_id, 'LI-001');
  assert.equal(proposed.type, 'kb_entry');
  assert.equal(proposed.status, 'proposed');
  assert.equal(proposed.priority_score, 0.72);
  assert.deepStrictEqual(proposed.tags, ['churn', 'definition']);

  const skill: LearningItemView = {
    item_id: 'LI-002',
    type: 'custom_skill',
    status: 'under_review',
    title: 'Churn analysis pipeline',
    priority_score: 0.85,
    evidence_count: 5,
    conflict_count: 1,
    scope: 'global',
    tags: ['churn', 'pipeline'],
    created_at: '2026-04-15T10:00:00Z',
  };

  assert.equal(skill.type, 'custom_skill');
  assert.equal(skill.conflict_count, 1);

  const harnessWarning: LearningItemView = {
    item_id: 'LI-003',
    type: 'pattern',
    status: 'proposed',
    title: 'Harness warning: overfitting',
    priority_score: 0.95,
    evidence_count: 1,
    conflict_count: 0,
    scope: 'project',
    tags: ['harness.warning', 'overfitting', 'severity:high', 'surface:daemon'],
    created_at: '2026-04-21T02:00:00Z',
  };

  assert.equal(isHarnessWarningLearningItem(harnessWarning), true);
  assert.deepEqual(
    extractHarnessWarningReviewSummary(
      normalizeLearningItemDetail(harnessWarning, {
        ...harnessWarning,
        content: 'Validation score diverges from train score.\n\nSuggestion: Reduce feature leakage and rerun the split.',
        review_count: 0,
        updated_at: '2026-04-21T02:05:00Z',
        metadata: {
          warningType: 'overfitting',
          severity: 'high',
          sessionId: 'sess-19',
          runId: 'run-44',
          surface: 'daemon',
          recurrenceCount: 4,
          firstSeenAt: '2026-04-21T00:30:00Z',
          lastSeenAt: '2026-04-21T02:05:00Z',
          surfaces: ['daemon', 'ws'],
          failureTaxonomyClass: 'overfitting',
          failureTaxonomyPromotionCandidate: true,
          rawPayload: {
            type: 'overfitting',
            severity: 'high',
            message: 'Validation score diverges from train score.',
          },
        },
      }),
    ),
    {
      warningType: 'overfitting',
      severity: 'high',
      surface: 'daemon',
      surfaces: ['daemon', 'ws'],
      sessionId: 'sess-19',
      runId: 'run-44',
      message: 'Validation score diverges from train score.',
      suggestion: 'Reduce feature leakage and rerun the split.',
      recurrenceCount: 4,
      taxonomyClass: 'overfitting',
      promotionCandidate: true,
      firstSeenAt: '2026-04-21T00:30:00Z',
      lastSeenAt: '2026-04-21T02:05:00Z',
      rawPayload: {
        type: 'overfitting',
        severity: 'high',
        message: 'Validation score diverges from train score.',
      },
    },
  );

  const inbox: LearningInboxView = {
    items: [harnessWarning, skill, proposed],
    total: 3,
  };

  assert.equal(inbox.items.length, 3);
  assert.equal(inbox.total, 3);
  assert.equal(inbox.items[0].priority_score > inbox.items[1].priority_score, true);

  const empty: LearningInboxView = { items: [], total: 0 };
  assert.equal(empty.total, 0);

  const TYPE_STYLES: Record<string, string> = {
    pattern: 'sky',
    kb_entry: 'emerald',
    custom_skill: 'fuchsia',
  };

  assert.equal(TYPE_STYLES[harnessWarning.type], 'sky');
  assert.equal(TYPE_STYLES[proposed.type], 'emerald');
  assert.equal(TYPE_STYLES[skill.type], 'fuchsia');

  assert.deepEqual(
    extractHarnessWarningReviewSummary({
      ...harnessWarning,
      metadata: {
        warningType: 'overfitting',
        failureTaxonomyClass: 'overfitting',
        failureTaxonomyRecurrenceCount: 5,
      },
    }),
    {
      warningType: 'overfitting',
      severity: 'high',
      surface: 'daemon',
      surfaces: ['daemon'],
      sessionId: null,
      runId: null,
      message: null,
      suggestion: null,
      recurrenceCount: 5,
      taxonomyClass: 'overfitting',
      promotionCandidate: false,
      firstSeenAt: null,
      lastSeenAt: null,
      rawPayload: null,
    },
  );

  assert.equal(readLearningGovernanceEnabled(null), false);
  assert.equal(readLearningGovernanceEnabled({}), false);
  assert.equal(
    readLearningGovernanceEnabled({ featureFlags: { selfImproveGovernanceV1: true } }),
    true,
  );
  assert.equal(
    readLearningGovernanceEnabled({ featureFlags: { selfImproveGovernanceV1: 'yes' } }),
    true,
  );

  assert.deepEqual(
    normalizeLearningGovernanceStatus({
      reviewEnabled: false,
      backlog: {
        activeWarningItems: 2,
        activeWarningRecurrences: 5,
        promotionCandidateItems: 1,
        promotionCandidateClasses: ['overfitting'],
        warningTypes: ['overfitting'],
        surfaces: ['daemon'],
        lastGcAt: '2026-04-21T02:05:00Z',
      },
      latestCompletedRun: {
        status: 'completed',
        summary: 'Learning governance weekly GC classified 2 item(s) across 5 recurrence(s).',
        recordedAt: '2026-04-21T02:05:00Z',
        reportPath: 'Docs/operations/gc_reports/GC_REPORT_2026-04-21_020500.md',
        totalItems: 2,
        totalRecurrences: 5,
        promotionThreshold: 3,
        promotionCandidateClasses: ['overfitting'],
      },
      latestReport: {
        path: 'Docs/operations/gc_reports/GC_REPORT_2026-04-21_020500.md',
        name: 'GC_REPORT_2026-04-21_020500.md',
      },
      recentHistory: [],
      standingOrder: {
        orderId: 'learning_governance_weekly_gc',
        name: 'Learning Governance Weekly GC',
        enabled: true,
        cron: '0 9 * * MON',
        timezone: 'UTC',
        nextRunAt: '2026-04-28T09:00:00Z',
        lastRunAt: '2026-04-21T02:05:00Z',
        runCount: 3,
        failureCount: 0,
      },
    }),
    {
      reviewEnabled: false,
      backlog: {
        activeWarningItems: 2,
        activeWarningRecurrences: 5,
        promotionCandidateItems: 1,
        promotionCandidateClasses: ['overfitting'],
        warningTypes: ['overfitting'],
        surfaces: ['daemon'],
        lastGcAt: '2026-04-21T02:05:00Z',
      },
      latestCompletedRun: {
        status: 'completed',
        summary: 'Learning governance weekly GC classified 2 item(s) across 5 recurrence(s).',
        recordedAt: '2026-04-21T02:05:00Z',
        reportPath: 'Docs/operations/gc_reports/GC_REPORT_2026-04-21_020500.md',
        totalItems: 2,
        totalRecurrences: 5,
        promotionThreshold: 3,
        promotionCandidateClasses: ['overfitting'],
      },
      latestReport: {
        path: 'Docs/operations/gc_reports/GC_REPORT_2026-04-21_020500.md',
        name: 'GC_REPORT_2026-04-21_020500.md',
      },
      recentHistory: [],
      standingOrder: {
        orderId: 'learning_governance_weekly_gc',
        name: 'Learning Governance Weekly GC',
        enabled: true,
        cron: '0 9 * * MON',
        timezone: 'UTC',
        nextRunAt: '2026-04-28T09:00:00Z',
        lastRunAt: '2026-04-21T02:05:00Z',
        runCount: 3,
        failureCount: 0,
      },
    },
  );

  {
    const calls: Array<{ method: string; params?: Record<string, unknown> }> = [];
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
            activeWarningRecurrences: 1,
            promotionCandidateItems: 0,
            promotionCandidateClasses: [],
            warningTypes: ['overfitting'],
            surfaces: ['daemon'],
            lastGcAt: null,
          },
          latestCompletedRun: null,
          latestReport: null,
          recentHistory: [],
          standingOrder: null,
        };
      }
      if (method === 'learning.inbox') {
        return { items: [harnessWarning], total: 1 };
      }
      if (method === 'learning.getItem') {
        return asRecord(harnessWarning);
      }
      throw new Error(`unexpected rpc ${method}`);
    });

    const status = await client.fetchStatus();
    const result = await client.fetchInbox('all');
    const detail = await client.fetchItemDetail(harnessWarning);
    assert.equal(status.enabled, false);
    assert.equal(status.status.backlog.activeWarningItems, 1);
    assert.deepEqual(result, { enabled: false, inbox: { items: [harnessWarning], total: 1 } });
    assert.equal(detail.enabled, false);
    assert.equal(detail.item?.item_id, harnessWarning.item_id);
    assert.deepEqual(calls.map((entry) => entry.method), [
      'config.get',
      'learning.status',
      'learning.inbox',
      'learning.getItem',
    ]);
    assert.equal(await client.reviewItem('LI-001', 'approve'), false);
  }

  {
    const calls: Array<{ method: string; params?: Record<string, unknown> }> = [];
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
            activeWarningRecurrences: 4,
            promotionCandidateItems: 1,
            promotionCandidateClasses: ['overfitting'],
            warningTypes: ['overfitting'],
            surfaces: ['daemon', 'ws'],
            lastGcAt: '2026-04-21T02:05:00Z',
          },
          latestCompletedRun: null,
          latestReport: null,
          recentHistory: [],
          standingOrder: null,
        };
      }
      if (method === 'learning.inbox') {
        return { items: [harnessWarning], total: 1 };
      }
      if (method === 'learning.getItem') {
        return asRecord(harnessWarning);
      }
      if (method === 'learning.review') {
        return { ok: true };
      }
      throw new Error(`unexpected rpc ${method}`);
    });

    const status = await client.fetchStatus();
    const result = await client.fetchInbox('proposed');
    const detail = await client.fetchItemDetail(harnessWarning);
    assert.equal(status.status.reviewEnabled, true);
    assert.deepEqual(status.status.backlog.promotionCandidateClasses, ['overfitting']);
    assert.equal(result.enabled, true);
    assert.deepEqual(result.inbox, { items: [harnessWarning], total: 1 });
    assert.equal(detail.enabled, true);
    assert.equal(detail.item?.item_id, harnessWarning.item_id);
    assert.equal(detail.item?.type, harnessWarning.type);
    assert.deepEqual(detail.item?.tags, harnessWarning.tags);
    assert.equal(await client.reviewItem('LI-001', 'approve', 'ship it'), true);
    assert.deepEqual(
      calls.map((entry) => entry.method),
      ['config.get', 'learning.status', 'learning.inbox', 'learning.getItem', 'learning.review'],
    );
  }

  console.log('[contract] PASS learning-inbox model');
}

void run().catch((error) => {
  console.error(error);
  process.exit(1);
});
