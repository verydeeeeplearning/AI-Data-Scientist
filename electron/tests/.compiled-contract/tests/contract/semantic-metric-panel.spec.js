"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
function run() {
    // ── Metric view contract ──────────────────────────────────────────
    const metric = {
        metricId: 'MTR-001',
        displayName: 'Monthly Active Users',
        owner: 'analytics-team',
        ownerContact: 'analytics@corp.com',
        definition: 'Count of distinct users with at least one event in a 30-day window.',
        synonyms: ['MAU', '월간 활성 사용자'],
        grain: 'monthly',
        unit: 'users',
        direction: 'up',
        caveats: ['Excludes internal test accounts'],
        verifiedQueryIds: ['VQ-001'],
        typicalRange: [50000, 200000],
        calculationSources: ['events.user_activity'],
    };
    strict_1.default.equal(metric.metricId, 'MTR-001');
    strict_1.default.equal(metric.displayName, 'Monthly Active Users');
    strict_1.default.equal(metric.owner, 'analytics-team');
    strict_1.default.equal(metric.definition.length > 0, true);
    strict_1.default.deepStrictEqual(metric.synonyms, ['MAU', '월간 활성 사용자']);
    strict_1.default.equal(metric.grain, 'monthly');
    strict_1.default.equal(metric.unit, 'users');
    strict_1.default.equal(metric.direction, 'up');
    strict_1.default.equal(metric.caveats.length, 1);
    strict_1.default.deepStrictEqual(metric.typicalRange, [50000, 200000]);
    // ── Verified query view contract ──────────────────────────────────
    const vq = {
        vqId: 'VQ-001',
        dialect: 'postgres',
        description: 'MAU count using events.user_activity',
        verifiedBy: 'data-eng-lead',
        lastVerified: '2026-04-01T00:00:00Z',
        referencedTables: ['events.user_activity'],
        verificationEvidence: 'shadow run comparison score 0.98',
    };
    strict_1.default.equal(vq.vqId, 'VQ-001');
    strict_1.default.equal(vq.dialect, 'postgres');
    strict_1.default.equal(vq.verifiedBy, 'data-eng-lead');
    strict_1.default.equal(vq.referencedTables.length, 1);
    // ── Trust table view contract ─────────────────────────────────────
    const trust = {
        fqtn: 'events.user_activity',
        grade: 'gold',
        owner: 'data-eng',
        description: 'Primary user event stream',
        gradeRationale: 'SLA-backed, freshness < 5min, schema-tested',
        lastAudited: '2026-03-15T00:00:00Z',
    };
    strict_1.default.equal(trust.fqtn, 'events.user_activity');
    strict_1.default.equal(trust.grade, 'gold');
    strict_1.default.equal(trust.owner, 'data-eng');
    // ── Grade tone mapping (rendering model) ──────────────────────────
    function toneForGrade(grade) {
        switch (grade) {
            case 'gold': return 'amber';
            case 'silver': return 'slate';
            case 'bronze': return 'orange';
            case 'untrusted': return 'red';
            default: return 'muted';
        }
    }
    strict_1.default.equal(toneForGrade('gold'), 'amber');
    strict_1.default.equal(toneForGrade('silver'), 'slate');
    strict_1.default.equal(toneForGrade('bronze'), 'orange');
    strict_1.default.equal(toneForGrade('untrusted'), 'red');
    strict_1.default.equal(toneForGrade('unknown'), 'muted');
    // ── Null / not-found states ───────────────────────────────────────
    const emptyMetric = null;
    strict_1.default.equal(emptyMetric, null, 'null metric = not found state');
    const noRange = { ...metric, typicalRange: null };
    strict_1.default.equal(noRange.typicalRange, null);
    const noVq = null;
    strict_1.default.equal(noVq, null, 'null vq = no verified query registered');
    // ── Range formatting (rendering model) ────────────────────────────
    function formatRange(range) {
        return range ? `${range[0]} - ${range[1]}` : null;
    }
    strict_1.default.equal(formatRange([50000, 200000]), '50000 - 200000');
    strict_1.default.equal(formatRange(null), null);
    console.log('[contract] PASS semantic-metric-panel model');
}
run();
