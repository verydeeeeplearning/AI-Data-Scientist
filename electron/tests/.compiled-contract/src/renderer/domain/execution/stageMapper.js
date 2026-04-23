"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isAgentControlTool = isAgentControlTool;
exports.listMappedToolNames = listMappedToolNames;
exports.listAgentControlToolNames = listAgentControlToolNames;
exports.mapToolToStage = mapToolToStage;
exports.inferToolCategory = inferToolCategory;
const TOOL_TO_STAGE = Object.freeze({
    // ── Data loading (canonical backend tools + legacy aliases)
    'data_loader': 'data_loading',
    'read_file': 'data_loading',
    'list_files': 'data_loading',
    'write_file': 'data_loading',
    'load_semantic_pack': 'data_loading',
    'read_csv': 'data_loading',
    'read_parquet': 'data_loading',
    'read_excel': 'data_loading',
    'read_json': 'data_loading',
    'read_jsonl': 'data_loading',
    'data_loader.load': 'data_loading',
    'file_ops.read_file': 'data_loading',
    'files.preview': 'data_loading',
    'files.upload': 'data_loading',
    // ── Schema diagnosis
    'data_profiler': 'schema_diagnosis',
    'schema_inspect': 'schema_diagnosis',
    'describe_table_trust': 'schema_diagnosis',
    'lookup_term': 'schema_diagnosis',
    'drift_monitor': 'schema_diagnosis',
    'data_profiler.scan': 'schema_diagnosis',
    'schema_validator.check': 'schema_diagnosis',
    'schema_tools.validate': 'schema_diagnosis',
    'missing_value_detector': 'schema_diagnosis',
    'deduplicate_rows': 'schema_diagnosis',
    'drift_tools.profile': 'schema_diagnosis',
    // ── Exploratory analysis
    'run_eda': 'eda',
    'profile_data': 'eda',
    'semantic_query': 'eda',
    'sql_query': 'eda',
    'eda.summary_statistics': 'eda',
    'eda.correlation': 'eda',
    'eda.distribution': 'eda',
    'eda.profile': 'eda',
    'eda.plot': 'eda',
    'data_profiler.describe': 'eda',
    // ── Feature engineering
    'feature_engineer': 'feature_engineering',
    'register_feature': 'feature_engineering',
    'feature_engineering.encode': 'feature_engineering',
    'feature_engineering.scale': 'feature_engineering',
    'feature_engineering.impute': 'feature_engineering',
    'feature_eng.generate': 'feature_engineering',
    'feature_eng.select': 'feature_engineering',
    // ── Baseline modeling
    'train_model': 'baseline_modeling',
    'modeling.train_baseline': 'baseline_modeling',
    'modeling.baseline': 'baseline_modeling',
    'modeling.train': 'baseline_modeling',
    // ── Model comparison
    'compare_runs': 'model_comparison',
    'ab_test': 'model_comparison',
    'modeling.compare': 'model_comparison',
    'ab_test_tools.compare_models': 'model_comparison',
    // ── Evaluation
    'evaluate_model': 'evaluation',
    'run_verifier': 'evaluation',
    'get_review_verdict': 'evaluation',
    'get_verifier_shadow_comparison': 'evaluation',
    'list_verifier_shadow_comparisons': 'evaluation',
    'verify_assumption': 'evaluation',
    'add_assumption': 'evaluation',
    'modeling.evaluate': 'evaluation',
    'evaluation.score': 'evaluation',
    'evaluation.classification': 'evaluation',
    'evaluation.regression': 'evaluation',
    // ── Reporting
    'generate_report': 'reporting',
    'dashboard_spec': 'reporting',
    'slide_generate': 'reporting',
    'render_stakeholder_artifact': 'reporting',
    'render_delivery_artifact': 'reporting',
    'reporting.generate_report': 'reporting',
    'reporting.write_summary': 'reporting',
    'plot_results': 'reporting',
    'artifact_tools.publish': 'reporting',
    // ── Verification & governance
    'policy_check': 'verification_certification',
    'lineage_capture': 'verification_certification',
    'get_review_artifacts': 'verification_certification',
    'record_review_artifact': 'verification_certification',
    'record_review_verdict': 'verification_certification',
    'get_post_deploy_status': 'verification_certification',
    'request_promotion': 'verification_certification',
    'list_promotions': 'verification_certification',
    'list_deprecations': 'verification_certification',
    'rollback_promotion': 'verification_certification',
    'request_monitoring': 'verification_certification',
    'verifier.statistical': 'verification_certification',
    'verifier.calibration': 'verification_certification',
    'certification.issue': 'verification_certification',
    'governance_tools.review': 'verification_certification',
    // ── Export & delivery (artifact handoff to outside systems)
    'notebook_generate': 'export',
    'generate_deployment': 'export',
    'build_delivery_pack': 'export',
    'dispatch_delivery': 'export',
    'list_delivery_log': 'export',
    'record_delivery_pack': 'export',
    'send_email': 'export',
    'send_to_slack': 'export',
    'post_to_slack': 'export',
    'publish_confluence_page': 'export',
    'publish_notion_page': 'export',
    'create_jira_ticket': 'export',
    'open_git_pr': 'export',
    'create_git_pr': 'export',
    'create_calendar_event': 'export',
    'create_work_object': 'export',
    'get_work_object': 'export',
    'list_work_objects': 'export',
    'link_external_resource': 'export',
    'advance_work_object_phase': 'export',
    'close_work_object': 'export',
    'get_work_object_timeline': 'export',
    'exporter.to_pdf': 'export',
    'exporter.to_notebook': 'export',
    'exporter.to_docx': 'export',
    'export_report': 'export',
    'artifact_tools.export': 'export',
});
const AGENT_CONTROL_TOOLS = Object.freeze(new Set([
    // Conversational / interaction
    'ask_user',
    'execute_code',
    'web_search',
    // Memory / learning surface
    'memory_search',
    'memory_store',
    'search_sessions',
    'list_learning_inbox',
    'review_learning_item',
    'get_learning_item',
    // Skills
    'skill_list',
    'skill_view',
    'skill_search',
    // Task contracts
    'create_task_contract',
    'update_task_contract',
    'get_task_contract',
    'list_my_contracts',
    'close_task_contract',
    // Portfolio / SLA
    'list_my_portfolio',
    'pause_task',
    'resume_task',
    'set_sla',
    // Standing orders
    'standing_order',
    // Scaling
    'distributed_exec',
]));
/**
 * Classifier for tools that participate in agent control/UX rather than the
 * 10-stage DS execution pipeline. Aggregator routes these out of the stage
 * timeline (caller decides whether to surface as an "agent control" rail or
 * suppress entirely).
 */
function isAgentControlTool(toolName) {
    return AGENT_CONTROL_TOOLS.has(normalizeToolName(toolName));
}
function listMappedToolNames() {
    return Object.freeze(Object.keys(TOOL_TO_STAGE));
}
function listAgentControlToolNames() {
    return Object.freeze(Array.from(AGENT_CONTROL_TOOLS));
}
function normalizeToolName(toolName) {
    return toolName.trim().toLowerCase();
}
function mapToolToStage(toolName) {
    const normalized = normalizeToolName(toolName);
    if (normalized in TOOL_TO_STAGE) {
        return TOOL_TO_STAGE[normalized];
    }
    if (normalized.includes('read_') || normalized.includes('load')) {
        return 'data_loading';
    }
    if (normalized.includes('schema') || normalized.includes('profile') || normalized.includes('missing')) {
        return 'schema_diagnosis';
    }
    if (normalized.includes('eda') || normalized.includes('distribution') || normalized.includes('correlation')) {
        return 'eda';
    }
    if (normalized.includes('feature')) {
        return 'feature_engineering';
    }
    if (normalized.includes('baseline') || normalized.includes('train')) {
        return 'baseline_modeling';
    }
    if (normalized.includes('compare')) {
        return 'model_comparison';
    }
    if (normalized.includes('evaluat') || normalized.includes('score')) {
        return 'evaluation';
    }
    if (normalized.includes('report') || normalized.includes('plot')) {
        return 'reporting';
    }
    if (normalized.includes('verify') || normalized.includes('cert')) {
        return 'verification_certification';
    }
    if (normalized.includes('export')) {
        return 'export';
    }
    return undefined;
}
function inferToolCategory(toolName) {
    const normalized = normalizeToolName(toolName);
    if (normalized.startsWith('memory')) {
        return 'memory';
    }
    if (normalized.startsWith('artifact') || normalized.startsWith('report') || normalized.startsWith('export')) {
        return 'artifact_learning';
    }
    if (normalized.startsWith('sql') || normalized.startsWith('integration') || normalized.startsWith('connector')) {
        return 'integration';
    }
    if (normalized.startsWith('sandbox') || normalized.startsWith('code_execution')) {
        return 'sandbox';
    }
    if (normalized.startsWith('governance') || normalized.startsWith('verifier')) {
        return 'domain';
    }
    if (normalized.startsWith('ab_test') || normalized.startsWith('drift') || normalized.startsWith('distributed')) {
        return 'advanced';
    }
    return 'core_ds';
}
