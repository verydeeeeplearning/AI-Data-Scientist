from ds_agent.domain.value_objects.action_class import (
    ACTION_CLASS_CATALOG,
    CostImpact,
    Reversibility,
    Sensitivity,
    WriteEffect,
    get_action_class,
)


def test_catalog_contains_expected_core_entries() -> None:
    assert "read_sql_gold" in ACTION_CLASS_CATALOG
    assert "jira_create" in ACTION_CLASS_CATALOG
    assert "prod_deploy" in ACTION_CLASS_CATALOG


def test_read_pii_table_has_pii_sensitivity_and_is_read_only() -> None:
    action_class = get_action_class("read_pii_table")

    assert action_class.data_sensitivity == Sensitivity.PII
    assert action_class.write_side_effect == WriteEffect.NONE
    assert action_class.is_read_only is True
    assert action_class.audit_required is True


def test_delete_table_is_irreversible_and_external() -> None:
    action_class = get_action_class("delete_table")

    assert action_class.write_side_effect == WriteEffect.IRREVERSIBLE
    assert action_class.reversibility == Reversibility.IRREVERSIBLE
    assert action_class.cost_impact == CostImpact.FREE


def test_unknown_action_class_falls_back_to_conservative_entry() -> None:
    action_class = get_action_class("totally_new_action")

    assert action_class.name == "unknown"
    assert action_class.audit_required is True
