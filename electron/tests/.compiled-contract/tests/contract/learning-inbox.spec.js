"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const useLearning_1 = require("../../src/renderer/hooks/useLearning");
function asRecord(value) {
    return value;
}
async function run() {
    const proposed = {
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
    strict_1.default.equal(proposed.item_id, 'LI-001');
    strict_1.default.equal(proposed.type, 'kb_entry');
    strict_1.default.equal(proposed.status, 'proposed');
    strict_1.default.equal(proposed.priority_score, 0.72);
    strict_1.default.deepStrictEqual(proposed.tags, ['churn', 'definition']);
    const skill = {
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
    strict_1.default.equal(skill.type, 'custom_skill');
    strict_1.default.equal(skill.conflict_count, 1);
    const harnessWarning = {
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
    strict_1.default.equal((0, useLearning_1.isHarnessWarningLearningItem)(harnessWarning), true);
    strict_1.default.deepEqual((0, useLearning_1.extractHarnessWarningReviewSummary)((0, useLearning_1.normalizeLearningItemDetail)(harnessWarning, {
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
    })), {
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
    });
    const inbox = {
        items: [harnessWarning, skill, proposed],
        total: 3,
    };
    strict_1.default.equal(inbox.items.length, 3);
    strict_1.default.equal(inbox.total, 3);
    strict_1.default.equal(inbox.items[0].priority_score > inbox.items[1].priority_score, true);
    const empty = { items: [], total: 0 };
    strict_1.default.equal(empty.total, 0);
    const TYPE_STYLES = {
        pattern: 'sky',
        kb_entry: 'emerald',
        custom_skill: 'fuchsia',
    };
    strict_1.default.equal(TYPE_STYLES[harnessWarning.type], 'sky');
    strict_1.default.equal(TYPE_STYLES[proposed.type], 'emerald');
    strict_1.default.equal(TYPE_STYLES[skill.type], 'fuchsia');
    strict_1.default.deepEqual((0, useLearning_1.extractHarnessWarningReviewSummary)({
        ...harnessWarning,
        metadata: {
            warningType: 'overfitting',
            failureTaxonomyClass: 'overfitting',
            failureTaxonomyRecurrenceCount: 5,
        },
    }), {
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
    });
    strict_1.default.equal((0, useLearning_1.readLearningGovernanceEnabled)(null), false);
    strict_1.default.equal((0, useLearning_1.readLearningGovernanceEnabled)({}), false);
    strict_1.default.equal((0, useLearning_1.readLearningGovernanceEnabled)({ featureFlags: { selfImproveGovernanceV1: true } }), true);
    strict_1.default.equal((0, useLearning_1.readLearningGovernanceEnabled)({ featureFlags: { selfImproveGovernanceV1: 'yes' } }), true);
    strict_1.default.deepEqual((0, useLearning_1.normalizeLearningGovernanceStatus)({
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
    }), {
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
    });
    {
        const calls = [];
        const client = (0, useLearning_1.createLearningClient)(async (method, params) => {
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
        strict_1.default.equal(status.enabled, false);
        strict_1.default.equal(status.status.backlog.activeWarningItems, 1);
        strict_1.default.deepEqual(result, { enabled: false, inbox: { items: [harnessWarning], total: 1 } });
        strict_1.default.equal(detail.enabled, false);
        strict_1.default.equal(detail.item?.item_id, harnessWarning.item_id);
        strict_1.default.deepEqual(calls.map((entry) => entry.method), [
            'config.get',
            'learning.status',
            'learning.inbox',
            'learning.getItem',
        ]);
        strict_1.default.equal(await client.reviewItem('LI-001', 'approve'), false);
    }
    {
        const calls = [];
        const client = (0, useLearning_1.createLearningClient)(async (method, params) => {
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
        strict_1.default.equal(status.status.reviewEnabled, true);
        strict_1.default.deepEqual(status.status.backlog.promotionCandidateClasses, ['overfitting']);
        strict_1.default.equal(result.enabled, true);
        strict_1.default.deepEqual(result.inbox, { items: [harnessWarning], total: 1 });
        strict_1.default.equal(detail.enabled, true);
        strict_1.default.equal(detail.item?.item_id, harnessWarning.item_id);
        strict_1.default.equal(detail.item?.type, harnessWarning.type);
        strict_1.default.deepEqual(detail.item?.tags, harnessWarning.tags);
        strict_1.default.equal(await client.reviewItem('LI-001', 'approve', 'ship it'), true);
        strict_1.default.deepEqual(calls.map((entry) => entry.method), ['config.get', 'learning.status', 'learning.inbox', 'learning.getItem', 'learning.review']);
    }
    console.log('[contract] PASS learning-inbox model');
}
void run().catch((error) => {
    console.error(error);
    process.exit(1);
});
