import assert from 'node:assert/strict';

import {
  filterWorkObjectItems,
  formatExternalReferenceLabel,
  formatWorkObjectPhaseLabel,
  getPendingPolicyActionCount,
} from '../../src/renderer/components/workflow/workObjectPanelModel';
import type { WorkObjectListItemView } from '../../src/renderer/types/workObject';

function run(): void {
  const items: WorkObjectListItemView[] = [
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

  assert.equal(formatWorkObjectPhaseLabel('followup'), 'Follow-up');
  assert.deepEqual(
    filterWorkObjectItems(items, 'retention').map((item) => item.work_object_id),
    ['WO-2026-001'],
  );
  assert.deepEqual(
    filterWorkObjectItems(items, 'tc-2026-002').map((item) => item.work_object_id),
    ['WO-2026-002'],
  );
  assert.equal(
    formatExternalReferenceLabel({
      system: 'jira',
      resource_type: 'issue',
      resource_id: 'DS-101',
      metadata: {},
      created_at: '2026-04-16T12:00:00Z',
      idempotency_key: 'wo_WO-2026-001:jira:create_issue:abc123',
    }),
    'jira:issue:DS-101',
  );
  assert.equal(
    getPendingPolicyActionCount({
      pending_policy_actions: [
        { status: 'pending' },
        { status: 'completed' },
        { status: 'pending' },
      ],
    }),
    2,
  );

  console.log('[contract] PASS work-object-panel model');
}

run();
