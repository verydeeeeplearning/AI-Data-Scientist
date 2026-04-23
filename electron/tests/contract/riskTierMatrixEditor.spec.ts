import assert from 'node:assert/strict';

import {
  countRiskTierCellDiff,
  countRiskTierRowDiff,
  formatRiskTierSnapshotLabel,
  normalizeRiskTierMatrix,
  resolveRiskTierSavedBy,
} from '../../src/renderer/application/policy/riskTierMatrix';

function run(): void {
  // === normalizeRiskTierMatrix strips blanks and preserves populated cells ===
  {
    const normalized = normalizeRiskTierMatrix({
      prod_deploy: { supervised: 'T3', delegate: ' ' },
      ' ': { autopilot: 'T1' },
      jira_create: { delegate: 'T1' },
      bad_row: null,
    });

    assert.deepEqual(normalized, {
      prod_deploy: { supervised: 'T3' },
      jira_create: { delegate: 'T1' },
    });
  }

  // === countRiskTierCellDiff and countRiskTierRowDiff agree on changed cells ===
  {
    const current = {
      prod_deploy: { supervised: 'T2', delegate: 'T1' },
      jira_create: { delegate: 'T0' },
    };
    const draft = {
      prod_deploy: { supervised: 'T3', delegate: 'T1' },
      jira_create: { delegate: 'T0' },
      slack_post: { autopilot: 'T1' },
    };

    assert.equal(countRiskTierCellDiff(current, draft), 2);
    assert.equal(countRiskTierRowDiff(current, draft), 2);
  }

  // === resolveRiskTierSavedBy prefers higher-trust organization members ===
  {
    const savedBy = resolveRiskTierSavedBy({
      members: [
        { userId: 'viewer@example.com', role: 'viewer' },
        { userId: 'admin@example.com', role: 'admin' },
        { userId: 'editor@example.com', role: 'editor' },
      ],
    });

    assert.equal(savedBy, 'admin@example.com');
    assert.equal(resolveRiskTierSavedBy({ members: [] }), null);
  }

  // === formatRiskTierSnapshotLabel mirrors the editor header copy ===
  {
    assert.equal(formatRiskTierSnapshotLabel(null), null);
    assert.equal(
      formatRiskTierSnapshotLabel({
        savedAt: 0,
        matrix: {},
        savedBy: null,
      }),
      null,
    );

    const label = formatRiskTierSnapshotLabel({
      savedAt: 1700000000,
      matrix: {},
      savedBy: 'admin@example.com',
    });
    assert.ok(label?.includes('Last saved:'));
    assert.ok(label?.endsWith('by admin@example.com'));
  }

  console.log('[contract] PASS risk-tier-matrix-editor (4 cases)');
}

run();
