import pytest

from ds_agent.runtime.action_classifier import ActionCandidate, ActionClassifier


class TestActionClassifier:
    @pytest.mark.parametrize(
        ("tool_name", "arguments", "expected"),
        [
            ("read_file", {"file_path": "notes.md"}, "read_sql_gold"),
            ("write_file", {"file_path": "notes.md", "content": "hello"}, "artifact_draft"),
            ("list_files", {"directory": "."}, "read_sql_gold"),
            ("data_loader", {"file_path": "train.csv"}, "read_sql_gold"),
            ("data_profiler", {"file_path": "train.csv"}, "read_sql_gold"),
            ("run_eda", {"code": "print('eda')", "data_path": "train.csv"}, "artifact_draft"),
            (
                "feature_engineer",
                {"code": "X = pd.get_dummies(X)", "input_path": "x.csv", "output_path": "y.csv"},
                "feature_engineering",
            ),
            ("train_model", {"code": "model.fit(X, y)"}, "model_training"),
            (
                "evaluate_model",
                {
                    "code": "print(metrics)",
                    "model_path": "m.pkl",
                    "test_data_path": "t.csv",
                    "target_column": "y",
                },
                "artifact_draft",
            ),
            (
                "generate_report",
                {"code": "print('report')", "project_dir": ".", "output_path": "report.md"},
                "artifact_draft",
            ),
            ("generate_deployment", {"environment": "production"}, "prod_deploy"),
            (
                "notebook_generate",
                {"code_blocks": ["print(1)"], "output_path": "a.ipynb"},
                "artifact_draft",
            ),
            ("slide_generate", {"sections": [{"title": "Summary"}]}, "artifact_draft"),
            ("dashboard_spec", {"metrics": [{"name": "revenue"}]}, "artifact_draft"),
            ("schema_inspect", {"action": "describe", "table": "orders"}, "read_sql_gold"),
            (
                "sql_query",
                {"sql": "SELECT * FROM users", "table_tier": "bronze"},
                "read_sql_bronze",
            ),
            ("semantic_query", {"question": "What is churn?"}, "read_sql_gold"),
            ("lookup_term", {"query": "GMV"}, "read_sql_gold"),
            ("describe_table_trust", {"fqtns": ["prod.sales.orders"]}, "read_sql_gold"),
            ("load_semantic_pack", {"skill_name": "growth", "dry_run": True}, "read_sql_gold"),
            ("standing_order", {"action": "list"}, "read_sql_gold"),
            ("web_search", {"query": "causal inference"}, "read_sql_gold"),
            ("ask_user", {"question": "Proceed?"}, "read_sql_gold"),
            ("policy_check", {"action": "sql_query"}, "read_sql_gold"),
            ("lineage_capture", {"action": "trace", "record_id": "lin-1"}, "read_sql_gold"),
            ("create_work_object", {"task_contract_id": "TC-1", "title": "t"}, "artifact_draft"),
            ("list_work_objects", {}, "read_sql_gold"),
            ("get_work_object", {"work_object_id": "WO-2026-001"}, "read_sql_gold"),
            ("link_external_resource", {"work_object_id": "WO-2026-001"}, "artifact_draft"),
            ("advance_work_object_phase", {"work_object_id": "WO-2026-001"}, "artifact_draft"),
            ("close_work_object", {"work_object_id": "WO-2026-001"}, "artifact_draft"),
            ("get_work_object_timeline", {"work_object_id": "WO-2026-001"}, "read_sql_gold"),
            ("post_to_slack", {"work_object_id": "WO-2026-001", "message": "hello"}, "slack_post"),
            ("send_to_slack", {"message": "hello"}, "slack_post"),
            (
                "publish_confluence_page",
                {"work_object_id": "WO-2026-001", "title": "Weekly brief"},
                "jira_create",
            ),
            (
                "publish_notion_page",
                {"work_object_id": "WO-2026-001", "title": "Weekly brief"},
                "jira_create",
            ),
            (
                "create_jira_ticket",
                {"summary": "s", "description": "d", "project": "DS"},
                "jira_create",
            ),
            (
                "open_git_pr",
                {"work_object_id": "WO-2026-001", "title": "PR", "repo": "org/repo"},
                "jira_create",
            ),
            ("create_git_pr", {"title": "PR", "body": "body", "head": "branch"}, "jira_create"),
            ("memory_search", {"query": "churn"}, "read_sql_gold"),
            ("memory_store", {"content": "note", "memory_type": "project"}, "artifact_draft"),
            ("skill_list", {}, "read_sql_gold"),
            ("skill_view", {"name": "eda"}, "read_sql_gold"),
            ("skill_search", {"query": "eda"}, "read_sql_gold"),
            (
                "render_stakeholder_artifact",
                {"artifact": {"artifact_id": "a1"}, "analysis": {}, "output_dir": "out"},
                "artifact_draft",
            ),
            ("search_sessions", {"query": "*"}, "read_sql_gold"),
        ],
    )
    def test_tool_catalog_classifies_known_tools(self, tool_name, arguments, expected):
        action_class = ActionClassifier().classify(ActionCandidate(tool_name, arguments))

        assert action_class.name == expected

    def test_sql_with_pii_sensitivity_maps_to_pii_read(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "sql_query",
                {"data_sensitivity": "pii", "sql": "SELECT email FROM users"},
            )
        )

        assert action_class.name == "read_pii_table"

    def test_sql_write_statement_maps_to_delete_table(self):
        action_class = ActionClassifier().classify(
            ActionCandidate("sql_query", {"sql": "DROP TABLE analytics.users"})
        )

        assert action_class.name == "delete_table"

    def test_load_semantic_pack_apply_maps_to_conservative_mutation(self):
        action_class = ActionClassifier().classify(
            ActionCandidate("load_semantic_pack", {"skill_name": "growth", "dry_run": False})
        )

        assert action_class.name == "jira_create"

    def test_policy_check_with_record_approval_maps_to_conservative_mutation(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "policy_check",
                {"action": "generate_deployment", "record_approval": True},
            )
        )

        assert action_class.name == "jira_create"

    def test_standing_order_create_maps_to_conservative_mutation(self):
        action_class = ActionClassifier().classify(
            ActionCandidate("standing_order", {"action": "create"})
        )

        assert action_class.name == "jira_create"

    def test_execute_code_training_heuristic_maps_to_model_training(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "execute_code",
                {
                    "code": (
                        "from sklearn.ensemble import RandomForestClassifier\n"
                        "model = RandomForestClassifier()\n"
                        "model.fit(X, y)\n"
                    )
                },
            )
        )

        assert action_class.name == "model_training"

    def test_execute_code_feature_heuristic_maps_to_feature_engineering(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "execute_code",
                {
                    "code": (
                        "from sklearn.preprocessing import StandardScaler\n"
                        "X = StandardScaler().fit_transform(X)\n"
                    )
                },
            )
        )

        assert action_class.name == "feature_engineering"

    def test_execute_code_artifact_heuristic_maps_to_artifact_draft(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "execute_code",
                {"code": "import matplotlib.pyplot as plt\nplt.savefig('plot.png')\n"},
            )
        )

        assert action_class.name == "artifact_draft"

    def test_execute_code_delete_heuristic_maps_to_delete_table(self):
        action_class = ActionClassifier().classify(
            ActionCandidate("execute_code", {"code": "import os\nos.remove('scratch.csv')\n"})
        )

        assert action_class.name == "delete_table"

    def test_distributed_exec_training_heuristic_maps_to_model_training(self):
        action_class = ActionClassifier().classify(
            ActionCandidate(
                "distributed_exec",
                {
                    "backend": "ray",
                    "data_path": "train.parquet",
                    "code": (
                        "from lightgbm import LGBMClassifier\n"
                        "model = LGBMClassifier()\n"
                        "model.fit(X, y)\n"
                    ),
                },
            )
        )

        assert action_class.name == "model_training"

    def test_unknown_tool_falls_back_to_unknown(self):
        action_class = ActionClassifier().classify(ActionCandidate("mystery_tool", {}))

        assert action_class.name == "unknown"
