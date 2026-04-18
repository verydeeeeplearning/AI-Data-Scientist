"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const workObjectPanelModel_1 = require("../../src/renderer/components/workflow/workObjectPanelModel");
function run() {
    const items = [
        {
            work_object_id: 'WO-2026-001',
            task_contract_id: 'TC-2026-001',
            title: 'Retention workflow',
            phase: 'review',
            updated_at: '2026-04-16T12:00:00Z',
            reference_count: 1,
            follow_up_count: 2,
        },
        {
            work_object_id: 'WO-2026-002',
            task_contract_id: 'TC-2026-002',
            title: 'Pricing workflow',
            phase: 'documenting',
            updated_at: '2026-04-16T13:00:00Z',
            reference_count: 0,
            follow_up_count: 0,
        },
    ];
    strict_1.default.equal((0, workObjectPanelModel_1.formatWorkObjectPhaseLabel)('followup'), 'Follow-up');
    strict_1.default.deepEqual((0, workObjectPanelModel_1.filterWorkObjectItems)(items, 'retention').map((item) => item.work_object_id), ['WO-2026-001']);
    strict_1.default.deepEqual((0, workObjectPanelModel_1.filterWorkObjectItems)(items, 'tc-2026-002').map((item) => item.work_object_id), ['WO-2026-002']);
    strict_1.default.equal((0, workObjectPanelModel_1.formatExternalReferenceLabel)({
        system: 'jira',
        resource_type: 'issue',
        resource_id: 'DS-101',
        metadata: {},
        created_at: '2026-04-16T12:00:00Z',
        idempotency_key: 'wo_WO-2026-001:jira:create_issue:abc123',
    }), 'jira:issue:DS-101');
    strict_1.default.equal((0, workObjectPanelModel_1.getPendingPolicyActionCount)({
        pending_policy_actions: [
            { status: 'pending' },
            { status: 'completed' },
            { status: 'pending' },
        ],
    }), 2);
    console.log('[contract] PASS work-object-panel model');
}
run();
