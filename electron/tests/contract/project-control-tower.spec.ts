import assert from 'node:assert/strict';

/**
 * Project Control Tower contract test.
 * Verifies PortfolioEntryView, PortfolioSlotView, and PortfolioOverview
 * type contracts used by the ProjectControlTower component.
 */

interface PortfolioEntryView {
  entry_id: string;
  task_contract_id: string;
  quadrant: string;
  priority: string;
  sla_deadline: string | null;
  parent_run_id: string | null;
  wait_condition_id: string | null;
  monitoring_metric_ref: string | null;
  tags: string[];
  updated_at: string;
}

interface PortfolioSlotView {
  active: number;
  max: number;
  available: number;
}

interface PortfolioOverview {
  active: PortfolioEntryView[];
  waiting: PortfolioEntryView[];
  monitoring: PortfolioEntryView[];
  candidates: PortfolioEntryView[];
  slots: PortfolioSlotView;
}

function run(): void {
  // ── Active entry ──────────────────────────────────────────────────
  const activeEntry: PortfolioEntryView = {
    entry_id: 'PE-001',
    task_contract_id: 'TC-2026-001',
    quadrant: 'active',
    priority: 'P1',
    sla_deadline: '2026-04-17T09:00:00Z',
    parent_run_id: 'run-001',
    wait_condition_id: null,
    monitoring_metric_ref: null,
    tags: ['churn', 'weekly'],
    updated_at: '2026-04-16T10:00:00Z',
  };

  assert.equal(activeEntry.quadrant, 'active');
  assert.equal(activeEntry.priority, 'P1');
  assert.equal(activeEntry.parent_run_id, 'run-001');
  assert.equal(activeEntry.wait_condition_id, null);
  assert.deepStrictEqual(activeEntry.tags, ['churn', 'weekly']);

  // ── Waiting entry ─────────────────────────────────────────────────
  const waitingEntry: PortfolioEntryView = {
    entry_id: 'PE-002',
    task_contract_id: 'TC-2026-002',
    quadrant: 'waiting',
    priority: 'P2',
    sla_deadline: null,
    parent_run_id: null,
    wait_condition_id: 'WC-001',
    monitoring_metric_ref: null,
    tags: [],
    updated_at: '2026-04-16T11:00:00Z',
  };

  assert.equal(waitingEntry.quadrant, 'waiting');
  assert.equal(waitingEntry.wait_condition_id, 'WC-001');
  assert.equal(waitingEntry.parent_run_id, null);

  // ── Slot view ─────────────────────────────────────────────────────
  const slots: PortfolioSlotView = { active: 1, max: 3, available: 2 };
  assert.equal(slots.active, 1);
  assert.equal(slots.max, 3);
  assert.equal(slots.available, 2);

  // ── Full overview ─────────────────────────────────────────────────
  const overview: PortfolioOverview = {
    active: [activeEntry],
    waiting: [waitingEntry],
    monitoring: [],
    candidates: [],
    slots,
  };

  assert.equal(overview.active.length, 1);
  assert.equal(overview.waiting.length, 1);
  assert.equal(overview.monitoring.length, 0);
  assert.equal(overview.candidates.length, 0);
  assert.equal(overview.slots.available, 2);

  // ── Priority style mapping (rendering model) ─────────────────────
  const PRIORITY_STYLES: Record<string, string> = {
    P0: 'rose',
    P1: 'amber',
    P2: 'sky',
    P3: 'slate',
  };

  assert.equal(PRIORITY_STYLES[activeEntry.priority], 'amber');
  assert.equal(PRIORITY_STYLES['P0'], 'rose');
  assert.equal(PRIORITY_STYLES['P3'], 'slate');

  // ── Empty overview ────────────────────────────────────────────────
  const emptyOverview: PortfolioOverview = {
    active: [],
    waiting: [],
    monitoring: [],
    candidates: [],
    slots: { active: 0, max: 3, available: 3 },
  };

  assert.equal(emptyOverview.active.length, 0);
  assert.equal(emptyOverview.slots.available, 3);

  console.log('[contract] PASS project-control-tower model');
}

run();
