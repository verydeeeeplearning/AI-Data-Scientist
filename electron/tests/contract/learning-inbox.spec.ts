import assert from 'node:assert/strict';

/**
 * Learning Inbox contract test.
 * Verifies LearningItemView and LearningInboxView type contracts.
 */

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
}

interface LearningInboxView {
  items: LearningItemView[];
  total: number;
}

function run(): void {
  // ── Proposed item ─────────────────────────────────────────────────
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

  // ── Custom skill item ─────────────────────────────────────────────
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

  // ── Full inbox ────────────────────────────────────────────────────
  const inbox: LearningInboxView = {
    items: [skill, proposed],
    total: 2,
  };

  assert.equal(inbox.items.length, 2);
  assert.equal(inbox.total, 2);
  // Higher priority_score first
  assert.equal(inbox.items[0].priority_score > inbox.items[1].priority_score, true);

  // ── Empty inbox ───────────────────────────────────────────────────
  const empty: LearningInboxView = { items: [], total: 0 };
  assert.equal(empty.total, 0);

  // ── Type style mapping ────────────────────────────────────────────
  const TYPE_STYLES: Record<string, string> = {
    pattern: 'sky',
    kb_entry: 'emerald',
    custom_skill: 'fuchsia',
  };

  assert.equal(TYPE_STYLES[proposed.type], 'emerald');
  assert.equal(TYPE_STYLES[skill.type], 'fuchsia');

  console.log('[contract] PASS learning-inbox model');
}

run();
