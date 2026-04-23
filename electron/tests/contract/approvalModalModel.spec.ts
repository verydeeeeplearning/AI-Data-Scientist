import assert from 'node:assert/strict';

import {
  buildApprovalModalViewModel,
  mergeApprovalDetails,
  type WorkflowApprovalSnapshot,
} from '../../src/renderer/components/approval/approvalModalModel';

const baseApproval: WorkflowApprovalSnapshot = {
  approvalId: 'appr-001',
  sessionId: 'session-001',
  runId: 'run-001',
  surface: 'ws',
  question: 'Allow the agent to continue with the blocked step?',
  kind: 'generic',
  metadata: {},
  options: [],
  default: null,
  status: 'pending',
  response: null,
  source: null,
  actor: null,
  createdAt: 1_713_650_000,
  updatedAt: 1_713_650_000,
  resolvedAt: null,
};

function run(): void {
  // === mergeApprovalDetails keeps the workflow snapshot and overlays v2 fields ===
  {
    const details = mergeApprovalDetails(baseApproval, {
      workspaceId: 'workspace-42',
      riskCode: 'PAT_005_SECRET_ENV_ACCESS',
      affectedScopes: ['secret'],
      recommendedAlternative: 'Use the secret manager instead.',
      patternMatches: [
        {
          patternId: 'PAT_005_SECRET_ENV_ACCESS',
          description: 'Read environment secrets',
          highlightedLines: [{ line: 4, reason: 'os.environ access' }],
        },
      ],
    });

    assert.equal(details.workspaceId, 'workspace-42');
    assert.equal(details.riskCode, 'PAT_005_SECRET_ENV_ACCESS');
    assert.deepEqual(details.affectedScopes, ['secret']);
    assert.equal(details.patternMatches[0]?.highlightedLines[0]?.line, 4);
    assert.equal(details.recommendedAlternative, 'Use the secret manager instead.');
  }

  // === semantic proposals expose their richer context and keep non-binary responses ===
  {
    const details = mergeApprovalDetails(baseApproval, {
      kind: 'semantic_proposal',
      options: ['approve', 'apply'],
      default: 'approve',
      metadata: {
        proposalType: 'verified_query',
        targetId: 'metric.revenue',
        risk: 'high',
        confidence: 0.91,
        autoApplyEligible: true,
      },
    });
    const viewModel = buildApprovalModalViewModel(details);

    assert.equal(viewModel.title, 'Semantic proposal approval');
    assert.deepEqual(viewModel.responseOptions, ['approve', 'apply']);
    assert.equal(viewModel.severity, 'medium');
    assert.ok(viewModel.infoRows.some((row) => row.label === 'Proposal' && row.value === 'Verified Query'));
    assert.ok(viewModel.infoRows.some((row) => row.label === 'Confidence' && row.value === '91%'));
  }

  // === binary approve/reject options stay out of the response chip list ===
  {
    const details = mergeApprovalDetails(baseApproval, {
      options: ['approve', 'reject'],
      default: 'reject',
    });
    const viewModel = buildApprovalModalViewModel(details);

    assert.deepEqual(viewModel.responseOptions, []);
    assert.equal(viewModel.title, 'Operator approval required');
  }

  // === code preview trims around highlighted lines and keeps the snippet language ===
  {
    const details = mergeApprovalDetails(baseApproval, {
      affectedScopes: ['network'],
      metadata: {
        sql: [
          'SELECT metric_name, metric_value',
          'FROM warehouse.metrics_daily',
          'WHERE snapshot_date >= CURRENT_DATE - 7',
          'ORDER BY snapshot_date DESC',
        ].join('\n'),
      },
      patternMatches: [
        {
          patternId: 'PAT_008_HTTP_REQUEST_UNAPPROVED',
          description: 'Unapproved HTTP request',
          highlightedLines: [{ line: 2, reason: 'Review the selected relation before allowing outbound access.' }],
        },
      ],
    });
    const viewModel = buildApprovalModalViewModel(details);

    assert.equal(viewModel.codePreview?.language, 'sql');
    assert.equal(viewModel.codePreview?.lines[1]?.number, 2);
    assert.equal(
      viewModel.codePreview?.lines[1]?.reason,
      'Review the selected relation before allowing outbound access.',
    );
  }

  console.log('[contract] PASS approval-modal-model (4 cases)');
}

run();
