"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const aggregateStages_1 = require("../../src/renderer/application/execution/aggregateStages");
const inferOutcome_1 = require("../../src/renderer/application/execution/inferOutcome");
const stage_1 = require("../../src/renderer/domain/execution/stage");
const stageMapper_1 = require("../../src/renderer/domain/execution/stageMapper");
// Mirror of @tool(name=...) in src/ds_agent/tools/* (87 entries as of 2026-04-19).
// Sourced via: rg '@tool\(\s*name="([^"]+)"' src/ds_agent/tools.
const BACKEND_TOOL_NAMES = Object.freeze([
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
function makeActivity(name, overrides = {}) {
    return {
        name,
        status: 'done',
        startedAt: 1000,
        ...overrides,
    };
}
function run() {
    {
        strict_1.default.equal((0, stageMapper_1.mapToolToStage)('read_csv'), 'data_loading');
        strict_1.default.equal((0, stageMapper_1.mapToolToStage)('data_profiler.scan'), 'schema_diagnosis');
        strict_1.default.equal((0, stageMapper_1.mapToolToStage)('feature_engineering.encode'), 'feature_engineering');
        strict_1.default.equal((0, stageMapper_1.mapToolToStage)('exporter.to_pdf'), 'export');
        strict_1.default.equal((0, stageMapper_1.mapToolToStage)('unknown_tool'), undefined);
    }
    {
        const stages = (0, aggregateStages_1.aggregateStages)([
            makeActivity('read_csv', {
                result: 'Loaded 1200 rows from train.csv',
            }),
            makeActivity('read_excel', {
                result: 'Loaded 300 rows from lookup.xlsx',
                startedAt: 1500,
            }),
            makeActivity('eda.summary_statistics', {
                startedAt: 2000,
            }),
        ]);
        strict_1.default.equal(stages.length, 2);
        strict_1.default.equal(stages[0].key, 'data_loading');
        strict_1.default.equal(stages[1].key, 'eda');
        strict_1.default.equal(stages[0].status, 'completed');
        strict_1.default.equal(stages[0].outcome?.summary, 'Loaded 2 file(s) and scanned 1,500 rows.');
    }
    {
        const stages = (0, aggregateStages_1.aggregateStages)([
            makeActivity('schema_validator.check', {
                status: 'error',
                result: 'warning: missing values found',
            }),
            makeActivity('eda.plot', {
                status: 'running',
            }),
        ]);
        strict_1.default.equal(stages[0].key, 'schema_diagnosis');
        strict_1.default.equal(stages[0].status, 'failed');
        strict_1.default.equal(stages[1].key, 'eda');
        strict_1.default.equal(stages[1].status, 'running');
    }
    {
        const stages = (0, aggregateStages_1.aggregateStages)([
            makeActivity('custom.experiment.step', {
                result: 'No mapped tool found',
            }),
        ]);
        strict_1.default.equal(stages.length, 1);
        strict_1.default.equal(stages[0].key, 'eda');
    }
    {
        const outcome = (0, inferOutcome_1.inferOutcome)({
            key: 'evaluation',
            toolEvents: [
                (0, stage_1.createExecutionToolEvent)({
                    toolName: 'evaluation.score',
                    status: 'completed',
                    outputPreview: 'accuracy 0.89, f1 0.84',
                }),
            ],
        });
        strict_1.default.equal(outcome?.summary, 'Captured 1 evaluation signal(s).');
    }
    // Backend tool registry coverage: every @tool() name must either map to a
    // pipeline stage OR be flagged as agent-control (out-of-pipeline).
    {
        const unmapped = [];
        for (const tool of BACKEND_TOOL_NAMES) {
            const stage = (0, stageMapper_1.mapToolToStage)(tool);
            const isControl = (0, stageMapper_1.isAgentControlTool)(tool);
            if (stage === undefined && !isControl) {
                unmapped.push(tool);
            }
        }
        strict_1.default.equal(unmapped.length, 0, `Backend tools missing stage mapping or agent-control classification: ${unmapped.join(', ')}`);
        strict_1.default.ok(BACKEND_TOOL_NAMES.length >= 87, 'Expected at least 87 backend tools (registry size as of 2026-04-19).');
    }
    // Agent-control tools must be filtered out of the stage timeline entirely.
    {
        const stages = (0, aggregateStages_1.aggregateStages)([
            makeActivity('ask_user'),
            makeActivity('memory_search'),
            makeActivity('skill_list'),
            makeActivity('read_file', { startedAt: 100 }),
        ]);
        strict_1.default.equal(stages.length, 1, 'Only read_file should produce a stage');
        strict_1.default.equal(stages[0].key, 'data_loading');
    }
    console.log('[contract] PASS execution timeline stages (16 cases)');
}
run();
