"""Verify all registered tools are available and have valid schemas."""

import importlib

from ds_agent.tools.registry import ToolRegistry

_TOOL_MODULES = [
    "ds_agent.tools.code_execution",
    "ds_agent.tools.data_loader",
    "ds_agent.tools.data_profiler",
    "ds_agent.tools.deployment",
    "ds_agent.tools.eda",
    "ds_agent.tools.evaluation",
    "ds_agent.tools.feature_eng",
    "ds_agent.tools.file_ops",
    "ds_agent.tools.artifact_tools",
    "ds_agent.tools.governance_tools",
    "ds_agent.tools.integration_tools",
    "ds_agent.tools.lookup_term",
    "ds_agent.tools.load_semantic_pack",
    "ds_agent.tools.memory_tools",
    "ds_agent.tools.modeling",
    "ds_agent.tools.reporting",
    "ds_agent.tools.describe_table_trust",
    "ds_agent.tools.schema_tools",
    "ds_agent.tools.semantic_query",
    "ds_agent.tools.sql_tools",
    "ds_agent.tools.standing_order_tools",
    "ds_agent.tools.skill_tools",
    "ds_agent.tools.user_interaction",
    "ds_agent.tools.web_search",
]

for module_name in _TOOL_MODULES:
    importlib.import_module(module_name)

EXPECTED_TOOLS = [
    "advance_work_object_phase",
    "close_work_object",
    "create_work_object",
    "execute_code",
    "get_work_object",
    "get_work_object_timeline",
    "read_file",
    "write_file",
    "link_external_resource",
    "list_work_objects",
    "list_files",
    "data_loader",
    "data_profiler",
    "run_eda",
    "feature_engineer",
    "train_model",
    "evaluate_model",
    "generate_report",
    "generate_deployment",
    "notebook_generate",
    "slide_generate",
    "dashboard_spec",
    "schema_inspect",
    "sql_query",
    "semantic_query",
    "lookup_term",
    "describe_table_trust",
    "load_semantic_pack",
    "standing_order",
    "web_search",
    "ask_user",
    "policy_check",
    "lineage_capture",
    "post_to_slack",
    "publish_confluence_page",
    "publish_notion_page",
    "send_to_slack",
    "create_jira_ticket",
    "open_git_pr",
    "create_git_pr",
    "memory_search",
    "memory_store",
    "skill_list",
    "skill_view",
    "skill_search",
]


class TestAllToolsRegistered:
    def test_all_expected_tools_present(self):
        registered = ToolRegistry.list_tools()
        for tool_name in EXPECTED_TOOLS:
            assert tool_name in registered, f"Missing tool: {tool_name}"

    def test_total_tool_count(self):
        registered = ToolRegistry.list_tools()
        assert len(registered) >= len(EXPECTED_TOOLS)

    def test_all_schemas_valid(self):
        defs = ToolRegistry.get_definitions()
        for d in defs:
            assert d["type"] == "function", f"Bad type for {d}"
            func = d["function"]
            assert "name" in func
            assert "description" in func
            assert len(func["description"]) > 10, f"Description too short: {func['name']}"
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_ds_analysis_tools(self):
        ds_tools = ToolRegistry.list_tools(category="ds_analysis")
        assert "data_loader" in ds_tools
        assert "data_profiler" in ds_tools
        assert "run_eda" in ds_tools
        assert "feature_engineer" in ds_tools
        assert "schema_inspect" in ds_tools
        assert "sql_query" in ds_tools
        assert "semantic_query" in ds_tools
        assert "lookup_term" in ds_tools
        assert "describe_table_trust" in ds_tools
        assert "standing_order" in ds_tools
        assert "notebook_generate" in ds_tools
        assert "dashboard_spec" in ds_tools

    def test_ds_modeling_tools(self):
        ml_tools = ToolRegistry.list_tools(category="ds_modeling")
        assert "train_model" in ml_tools
        assert "evaluate_model" in ml_tools

    def test_utility_tools(self):
        util_tools = ToolRegistry.list_tools(category="utility")
        assert "execute_code" in util_tools
        assert "read_file" in util_tools
        assert "web_search" in util_tools
        assert "ask_user" in util_tools
        assert "policy_check" in util_tools
