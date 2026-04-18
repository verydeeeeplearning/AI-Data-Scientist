"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
function run() {
    // ── Active entry ──────────────────────────────────────────────────
    const activeEntry = {
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
    strict_1.default.equal(activeEntry.quadrant, 'active');
    strict_1.default.equal(activeEntry.priority, 'P1');
    strict_1.default.equal(activeEntry.parent_run_id, 'run-001');
    strict_1.default.equal(activeEntry.wait_condition_id, null);
    strict_1.default.deepStrictEqual(activeEntry.tags, ['churn', 'weekly']);
    // ── Waiting entry ─────────────────────────────────────────────────
    const waitingEntry = {
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
    strict_1.default.equal(waitingEntry.quadrant, 'waiting');
    strict_1.default.equal(waitingEntry.wait_condition_id, 'WC-001');
    strict_1.default.equal(waitingEntry.parent_run_id, null);
    // ── Slot view ─────────────────────────────────────────────────────
    const slots = { active: 1, max: 3, available: 2 };
    strict_1.default.equal(slots.active, 1);
    strict_1.default.equal(slots.max, 3);
    strict_1.default.equal(slots.available, 2);
    // ── Full overview ─────────────────────────────────────────────────
    const overview = {
        active: [activeEntry],
        waiting: [waitingEntry],
        monitoring: [],
        candidates: [],
        slots,
    };
    strict_1.default.equal(overview.active.length, 1);
    strict_1.default.equal(overview.waiting.length, 1);
    strict_1.default.equal(overview.monitoring.length, 0);
    strict_1.default.equal(overview.candidates.length, 0);
    strict_1.default.equal(overview.slots.available, 2);
    // ── Priority style mapping (rendering model) ─────────────────────
    const PRIORITY_STYLES = {
        P0: 'rose',
        P1: 'amber',
        P2: 'sky',
        P3: 'slate',
    };
    strict_1.default.equal(PRIORITY_STYLES[activeEntry.priority], 'amber');
    strict_1.default.equal(PRIORITY_STYLES['P0'], 'rose');
    strict_1.default.equal(PRIORITY_STYLES['P3'], 'slate');
    // ── Empty overview ────────────────────────────────────────────────
    const emptyOverview = {
        active: [],
        waiting: [],
        monitoring: [],
        candidates: [],
        slots: { active: 0, max: 3, available: 3 },
    };
    strict_1.default.equal(emptyOverview.active.length, 0);
    strict_1.default.equal(emptyOverview.slots.available, 3);
    console.log('[contract] PASS project-control-tower model');
}
run();
