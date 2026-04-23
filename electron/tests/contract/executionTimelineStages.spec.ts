import assert from 'node:assert/strict';

import { aggregateStages, type ToolActivityLike } from '../../src/renderer/application/execution/aggregateStages';
import { inferOutcome } from '../../src/renderer/application/execution/inferOutcome';
import { createExecutionToolEvent } from '../../src/renderer/domain/execution/stage';
import {
  isAgentControlTool,
  mapToolToStage,
} from '../../src/renderer/domain/execution/stageMapper';

// Mirror of @tool(name=...) in src/ds_agent/tools/* (87 entries as of 2026-04-19).
// Sourced via: rg '@tool\(\s*name="([^"]+)"' src/ds_agent/tools.
const BACKEND_TOOL_NAMES: readonly string[] = Object.freeze([
  'ab_test', 'add_assumption', 'advance_work_object_phase', 'ask_user',
  'build_delivery_pack', 'close_task_contract', 'close_work_object',
  'compare_runs', 'create_calendar_event', 'create_git_pr', 'create_jira_ticket',
  'create_task_contract', 'create_work_object', 'dashboard_spec', 'data_loader',
  'data_profiler', 'describe_table_trust', 'dispatch_delivery', 'distributed_exec',
  'drift_monitor', 'evaluate_model', 'execute_code', 'feature_engineer',
  'generate_deployment', 'generate_report', 'get_learning_item',
  'get_post_deploy_status', 'get_review_artifacts', 'get_review_verdict',
  'get_task_contract', 'get_verifier_shadow_comparison', 'get_work_object',
  'get_work_object_timeline', 'lineage_capture', 'link_external_resource',
  'list_delivery_log', 'list_deprecations', 'list_files', 'list_learning_inbox',
  'list_my_contracts', 'list_my_portfolio', 'list_promotions',
  'list_verifier_shadow_comparisons', 'list_work_objects', 'load_semantic_pack',
  'lookup_term', 'memory_search', 'memory_store', 'notebook_generate',
  'open_git_pr', 'pause_task', 'policy_check', 'post_to_slack', 'profile_data',
  'publish_confluence_page', 'publish_notion_page', 'read_file',
  'record_delivery_pack', 'record_review_artifact', 'record_review_verdict',
  'register_feature', 'render_delivery_artifact', 'render_stakeholder_artifact',
  'request_monitoring', 'request_promotion', 'resume_task',
  'review_learning_item', 'rollback_promotion', 'run_eda', 'run_verifier',
  'schema_inspect', 'search_sessions', 'semantic_query', 'send_email',
  'send_to_slack', 'set_sla', 'skill_list', 'skill_search', 'skill_view',
  'slide_generate', 'sql_query', 'standing_order', 'train_model',
  'update_task_contract', 'verify_assumption', 'web_search', 'write_file',
]);

function makeActivity(
  name: string,
  overrides: Partial<ToolActivityLike> = {},
): ToolActivityLike {
  return {
    name,
    status: 'done',
    startedAt: 1_000,
    ...overrides,
  };
}

function run(): void {
  {
    assert.equal(mapToolToStage('read_csv'), 'data_loading');
    assert.equal(mapToolToStage('data_profiler.scan'), 'schema_diagnosis');
    assert.equal(mapToolToStage('feature_engineering.encode'), 'feature_engineering');
    assert.equal(mapToolToStage('exporter.to_pdf'), 'export');
    assert.equal(mapToolToStage('unknown_tool'), undefined);
  }

  {
    const stages = aggregateStages([
      makeActivity('read_csv', {
        result: 'Loaded 1200 rows from train.csv',
      }),
      makeActivity('read_excel', {
        result: 'Loaded 300 rows from lookup.xlsx',
        startedAt: 1_500,
      }),
      makeActivity('eda.summary_statistics', {
        startedAt: 2_000,
      }),
    ]);

    assert.equal(stages.length, 2);
    assert.equal(stages[0].key, 'data_loading');
    assert.equal(stages[1].key, 'eda');
    assert.equal(stages[0].status, 'completed');
    assert.equal(stages[0].outcome?.summary, 'Loaded 2 file(s) and scanned 1,500 rows.');
  }

  {
    const stages = aggregateStages([
      makeActivity('schema_validator.check', {
        status: 'error',
        result: 'warning: missing values found',
      }),
      makeActivity('eda.plot', {
        status: 'running',
      }),
    ]);

    assert.equal(stages[0].key, 'schema_diagnosis');
    assert.equal(stages[0].status, 'failed');
    assert.equal(stages[1].key, 'eda');
    assert.equal(stages[1].status, 'running');
  }

  {
    const stages = aggregateStages([
      makeActivity('custom.experiment.step', {
        result: 'No mapped tool found',
      }),
    ]);

    assert.equal(stages.length, 1);
    assert.equal(stages[0].key, 'eda');
  }

  {
    const outcome = inferOutcome({
      key: 'evaluation',
      toolEvents: [
        createExecutionToolEvent({
          toolName: 'evaluation.score',
          status: 'completed',
          outputPreview: 'accuracy 0.89, f1 0.84',
        }),
      ],
    });

    assert.equal(outcome?.summary, 'Captured 1 evaluation signal(s).');
  }

  // Backend tool registry coverage: every @tool() name must either map to a
  // pipeline stage OR be flagged as agent-control (out-of-pipeline).
  {
    const unmapped: string[] = [];
    for (const tool of BACKEND_TOOL_NAMES) {
      const stage = mapToolToStage(tool);
      const isControl = isAgentControlTool(tool);
      if (stage === undefined && !isControl) {
        unmapped.push(tool);
      }
    }
    assert.equal(
      unmapped.length,
      0,
      `Backend tools missing stage mapping or agent-control classification: ${unmapped.join(', ')}`,
    );
    assert.ok(
      BACKEND_TOOL_NAMES.length >= 87,
      'Expected at least 87 backend tools (registry size as of 2026-04-19).',
    );
  }

  // Agent-control tools must be filtered out of the stage timeline entirely.
  {
    const stages = aggregateStages([
      makeActivity('ask_user'),
      makeActivity('memory_search'),
      makeActivity('skill_list'),
      makeActivity('read_file', { startedAt: 100 }),
    ]);
    assert.equal(stages.length, 1, 'Only read_file should produce a stage');
    assert.equal(stages[0].key, 'data_loading');
  }

  console.log('[contract] PASS execution timeline stages (16 cases)');
}

run();
