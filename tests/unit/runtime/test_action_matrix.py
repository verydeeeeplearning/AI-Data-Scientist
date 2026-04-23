from pathlib import Path
from tempfile import TemporaryDirectory

from ds_agent.runtime.action_matrix import ActionMatrix, Verdict
from ds_agent.runtime.policy_store import JsonPolicyStore


class TestActionMatrix:
    def test_read_sql_gold_is_auto_in_shadow(self):
        matrix = ActionMatrix.default()

        assert matrix.lookup("read_sql_gold", "shadow") == Verdict.AUTO

    def test_jira_create_requires_ask_in_delegate(self):
        matrix = ActionMatrix.default()

        assert matrix.lookup("jira_create", "delegate") == Verdict.ASK

    def test_prod_deploy_requires_dual_in_supervised(self):
        matrix = ActionMatrix.default()

        assert matrix.lookup("prod_deploy", "supervised") == Verdict.DUAL

    def test_read_pii_table_is_skipped_in_freeze(self):
        matrix = ActionMatrix.default()

        assert matrix.lookup("read_pii_table", "freeze") == Verdict.SKIP

    def test_unknown_defaults_to_approve_in_delegate(self):
        matrix = ActionMatrix.default()

        assert matrix.lookup("totally_new_action", "delegate") == Verdict.APPROVE

    def test_with_overrides_updates_selected_cells_only(self):
        matrix = ActionMatrix.default().with_overrides(
            {
                "jira_create": {"delegate": "auto"},
                "prod_deploy": {"supervised": "approve"},
            }
        )

        assert matrix.lookup("jira_create", "delegate") == Verdict.AUTO
        assert matrix.lookup("jira_create", "supervised") == Verdict.APPROVE
        assert matrix.lookup("prod_deploy", "supervised") == Verdict.APPROVE
        assert matrix.lookup("prod_deploy", "delegate") == Verdict.DUAL

    def test_persisted_risk_tier_matrix_overrides_dispatch_verdict(self):
        with TemporaryDirectory() as tmp_dir:
            store = JsonPolicyStore(base_dir=Path(tmp_dir))

            baseline = store.build_action_matrix()
            assert baseline.lookup("prod_deploy", "supervised") == Verdict.DUAL

            store.save_risk_tier_matrix(
                {
                    "prod_deploy": {
                        "supervised": "T0",
                    }
                }
            )

            matrix = store.build_action_matrix()
            assert matrix.lookup("prod_deploy", "supervised") == Verdict.AUTO
