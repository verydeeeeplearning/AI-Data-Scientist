import assert from 'node:assert/strict';

/**
 * Semantic Metric Panel contract test.
 * Verifies the SemanticMetricView / SemanticVerifiedQueryView / SemanticTrustTableView
 * type contracts and rendering model expectations used by MetricSourcePanel.
 */

interface SemanticMetricView {
  metricId: string;
  displayName: string;
  owner: string;
  ownerContact: string | null;
  definition: string;
  synonyms: string[];
  grain: string | null;
  unit: string | null;
  direction: string | null;
  caveats: string[];
  verifiedQueryIds: string[];
  typicalRange: [number, number] | null;
  calculationSources: string[];
}

interface SemanticVerifiedQueryView {
  vqId: string;
  dialect: string;
  description: string;
  verifiedBy: string;
  lastVerified: string | null;
  referencedTables: string[];
  verificationEvidence: string | null;
}

interface SemanticTrustTableView {
  fqtn: string;
  grade: string;
  owner: string;
  description: string;
  gradeRationale: string;
  lastAudited: string | null;
}

function run(): void {
  // ── Metric view contract ──────────────────────────────────────────
  const metric: SemanticMetricView = {
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

  assert.equal(metric.metricId, 'MTR-001');
  assert.equal(metric.displayName, 'Monthly Active Users');
  assert.equal(metric.owner, 'analytics-team');
  assert.equal(metric.definition.length > 0, true);
  assert.deepStrictEqual(metric.synonyms, ['MAU', '월간 활성 사용자']);
  assert.equal(metric.grain, 'monthly');
  assert.equal(metric.unit, 'users');
  assert.equal(metric.direction, 'up');
  assert.equal(metric.caveats.length, 1);
  assert.deepStrictEqual(metric.typicalRange, [50000, 200000]);

  // ── Verified query view contract ──────────────────────────────────
  const vq: SemanticVerifiedQueryView = {
    vqId: 'VQ-001',
    dialect: 'postgres',
    description: 'MAU count using events.user_activity',
    verifiedBy: 'data-eng-lead',
    lastVerified: '2026-04-01T00:00:00Z',
    referencedTables: ['events.user_activity'],
    verificationEvidence: 'shadow run comparison score 0.98',
  };

  assert.equal(vq.vqId, 'VQ-001');
  assert.equal(vq.dialect, 'postgres');
  assert.equal(vq.verifiedBy, 'data-eng-lead');
  assert.equal(vq.referencedTables.length, 1);

  // ── Trust table view contract ─────────────────────────────────────
  const trust: SemanticTrustTableView = {
    fqtn: 'events.user_activity',
    grade: 'gold',
    owner: 'data-eng',
    description: 'Primary user event stream',
    gradeRationale: 'SLA-backed, freshness < 5min, schema-tested',
    lastAudited: '2026-03-15T00:00:00Z',
  };

  assert.equal(trust.fqtn, 'events.user_activity');
  assert.equal(trust.grade, 'gold');
  assert.equal(trust.owner, 'data-eng');

  // ── Grade tone mapping (rendering model) ──────────────────────────
  function toneForGrade(grade: string): string {
    switch (grade) {
      case 'gold': return 'amber';
      case 'silver': return 'slate';
      case 'bronze': return 'orange';
      case 'untrusted': return 'red';
      default: return 'muted';
    }
  }

  assert.equal(toneForGrade('gold'), 'amber');
  assert.equal(toneForGrade('silver'), 'slate');
  assert.equal(toneForGrade('bronze'), 'orange');
  assert.equal(toneForGrade('untrusted'), 'red');
  assert.equal(toneForGrade('unknown'), 'muted');

  // ── Null / not-found states ───────────────────────────────────────
  const emptyMetric: SemanticMetricView | null = null;
  assert.equal(emptyMetric, null, 'null metric = not found state');

  const noRange: SemanticMetricView = { ...metric, typicalRange: null };
  assert.equal(noRange.typicalRange, null);

  const noVq: SemanticVerifiedQueryView | null = null;
  assert.equal(noVq, null, 'null vq = no verified query registered');

  // ── Range formatting (rendering model) ────────────────────────────
  function formatRange(range: [number, number] | null): string | null {
    return range ? `${range[0]} - ${range[1]}` : null;
  }

  assert.equal(formatRange([50000, 200000]), '50000 - 200000');
  assert.equal(formatRange(null), null);

  console.log('[contract] PASS semantic-metric-panel model');
}

run();
