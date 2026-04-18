"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
function run() {
    // ── Proposed item ─────────────────────────────────────────────────
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
    // ── Custom skill item ─────────────────────────────────────────────
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
    // ── Full inbox ────────────────────────────────────────────────────
    const inbox = {
        items: [skill, proposed],
        total: 2,
    };
    strict_1.default.equal(inbox.items.length, 2);
    strict_1.default.equal(inbox.total, 2);
    // Higher priority_score first
    strict_1.default.equal(inbox.items[0].priority_score > inbox.items[1].priority_score, true);
    // ── Empty inbox ───────────────────────────────────────────────────
    const empty = { items: [], total: 0 };
    strict_1.default.equal(empty.total, 0);
    // ── Type style mapping ────────────────────────────────────────────
    const TYPE_STYLES = {
        pattern: 'sky',
        kb_entry: 'emerald',
        custom_skill: 'fuchsia',
    };
    strict_1.default.equal(TYPE_STYLES[proposed.type], 'emerald');
    strict_1.default.equal(TYPE_STYLES[skill.type], 'fuchsia');
    console.log('[contract] PASS learning-inbox model');
}
run();
