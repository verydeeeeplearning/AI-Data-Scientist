import assert from 'node:assert/strict';

import {
  applyMissionPatch,
  COLLAPSED_SLOT_KEYS,
  deriveMissionBudgetState,
  isSnoozeActive,
  listVisibleSlotKeys,
  MISSION_BUDGET_SNOOZE_KEY,
  nextBudgetWarningVisibility,
  parseSnoozeStorage,
  projectConnection,
  serializeSnoozeStorage,
  shouldShowBudgetWarning,
  snoozeUntil,
} from '../../src/renderer/application/mission/missionHeaderState';
import {
  getMissionBudgetState,
  getMissionConnectionStateFromWs,
  type MissionContext,
} from '../../src/renderer/domain/mission';

const BASE_MISSION: MissionContext = {
  goal: {
    title: 'Reduce churn for premium users',
    successCriteria: ['Deliver retention analysis'],
  },
  dataSources: [{ type: 'file', label: 'train.csv', rowCount: 1200 }],
  deliverables: ['report'],
  constraints: {
    language: 'ko',
    requiresApproval: true,
    localOnlyModel: false,
  },
  stage: { current: 1, total: 4, label: 'Mission agreed' },
  mode: 'supervised',
  model: {
    primary: 'anthropic/claude-sonnet-4-6',
    fallbacks: ['openai/gpt-4.1'],
    capabilities: ['balanced_reasoning'],
  },
  budget: {
    spentUsd: 1.5,
    limitUsd: 10,
    elapsedSec: 30,
    nearLimit: false,
  },
  connection: { state: 'connected' },
};

function run(): void {
  // Scenario 1: WS reconnect updates mission connection without losing prior data.
  {
    const projected = projectConnection(BASE_MISSION, 'connecting');
    assert.equal(projected.connection.state, 'reconnecting');
    assert.equal(projected.goal.title, BASE_MISSION.goal.title);
    assert.equal(getMissionConnectionStateFromWs('connected'), 'connected');
    assert.equal(getMissionConnectionStateFromWs('connecting'), 'reconnecting');
    assert.equal(getMissionConnectionStateFromWs('disconnected'), 'disconnected');

    const reconnected = projectConnection(projected, 'connected');
    assert.equal(reconnected.connection.state, 'connected');
  }

  // Scenario 2: Budget 80% threshold triggers BudgetWarning, ESC dismiss only resets state.
  {
    const warningMission: MissionContext = {
      ...BASE_MISSION,
      budget: { ...BASE_MISSION.budget, spentUsd: 8.4, nearLimit: true },
    };
    assert.equal(deriveMissionBudgetState(warningMission), 'warning');
    assert.equal(deriveMissionBudgetState(BASE_MISSION), 'default');

    const errorMission: MissionContext = {
      ...BASE_MISSION,
      budget: { ...BASE_MISSION.budget, spentUsd: 11, nearLimit: true },
    };
    assert.equal(deriveMissionBudgetState(errorMission), 'error');

    assert.equal(
      shouldShowBudgetWarning({
        previous: 'default',
        next: 'warning',
        streaming: true,
      }),
      true,
    );
    assert.equal(
      shouldShowBudgetWarning({
        previous: 'default',
        next: 'warning',
        streaming: false,
      }),
      false,
    );
    assert.equal(
      shouldShowBudgetWarning({
        previous: 'warning',
        next: 'warning',
        streaming: true,
      }),
      false,
    );
    assert.equal(
      shouldShowBudgetWarning({
        previous: 'warning',
        next: 'error',
        streaming: true,
      }),
      true,
    );
    assert.equal(
      shouldShowBudgetWarning({
        previous: 'error',
        next: 'error',
        streaming: true,
      }),
      false,
    );
  }

  // Scenario 3: Collapsed shows core 3 slots, expanded reveals all 9.
  {
    const collapsedKeys = listVisibleSlotKeys(true);
    assert.deepEqual(Array.from(collapsedKeys), Array.from(COLLAPSED_SLOT_KEYS));
    assert.equal(collapsedKeys.length, 3);
    assert.deepEqual(Array.from(collapsedKeys).sort(), ['budget', 'goal', 'stage']);

    const expandedKeys = listVisibleSlotKeys(false);
    assert.equal(expandedKeys.length, 9);
    assert.deepEqual(Array.from(expandedKeys).sort(), [
      'budget',
      'connection',
      'constraints',
      'dataSources',
      'deliverables',
      'goal',
      'mode',
      'model',
      'stage',
    ]);
  }

  // Scenario 4: mission.context.updated patch performs partial merge.
  {
    const updated = applyMissionPatch(BASE_MISSION, {
      stage: { current: 2, label: 'Analysis running' },
      budget: { spentUsd: 8.2, nearLimit: true },
    });
    assert.notEqual(updated, null);
    assert.equal(updated!.stage.current, 2);
    assert.equal(updated!.stage.total, 4);
    assert.equal(updated!.stage.label, 'Analysis running');
    assert.equal(updated!.budget.spentUsd, 8.2);
    assert.equal(updated!.budget.limitUsd, 10);
    assert.equal(updated!.goal.title, BASE_MISSION.goal.title);
    assert.equal(getMissionBudgetState(updated!.budget), 'warning');

    const noOp = applyMissionPatch(null, { mode: 'auto' });
    assert.equal(noOp, null);
  }

  // Snooze interactions: snoozed timer suppresses warning, expired snooze allows it.
  {
    const now = 1_000_000_000;
    const future = snoozeUntil(now, '5m');
    assert.equal(future, now + 5 * 60 * 1000);
    assert.equal(isSnoozeActive({ until: future }, now), true);
    assert.equal(isSnoozeActive({ until: future }, future + 1), false);
    assert.equal(isSnoozeActive({ until: null }, now), false);

    const blocked = nextBudgetWarningVisibility({
      previous: 'default',
      next: 'warning',
      streaming: true,
      snoozedUntil: future,
      now,
    });
    assert.equal(blocked, false);

    const allowed = nextBudgetWarningVisibility({
      previous: 'default',
      next: 'warning',
      streaming: true,
      snoozedUntil: null,
      now,
    });
    assert.equal(allowed, true);

    const expired = nextBudgetWarningVisibility({
      previous: 'default',
      next: 'warning',
      streaming: true,
      snoozedUntil: now - 1,
      now,
    });
    assert.equal(expired, true);

    assert.equal(parseSnoozeStorage(null).until, null);
    assert.equal(parseSnoozeStorage('not-a-number').until, null);
    assert.equal(parseSnoozeStorage('-5').until, null);
    assert.equal(parseSnoozeStorage('123').until, 123);

    assert.equal(serializeSnoozeStorage({ until: null }), null);
    assert.equal(serializeSnoozeStorage({ until: 0 }), null);
    assert.equal(serializeSnoozeStorage({ until: 555 }), '555');

    assert.equal(MISSION_BUDGET_SNOOZE_KEY, 'ds-agent-budget-snooze-until');
  }

  console.log('[contract] PASS mission-header-integration (28 cases)');
}

run();
