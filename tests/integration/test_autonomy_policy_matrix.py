"""Integration coverage for classifier + matrix + permission policy."""

from ds_agent.agent.permissions import PermissionMode, PermissionPolicy
from ds_agent.runtime.action_classifier import ActionCandidate, ActionClassifier
from ds_agent.runtime.autonomy_policy import AutonomyPolicy


def test_delegate_auto_mode_blocks_pii_sql_without_approval() -> None:
    classifier = ActionClassifier()
    candidate = ActionCandidate("sql_query", {"data_sensitivity": "pii"})
    action_class = classifier.classify(candidate)

    decision = AutonomyPolicy().evaluate(
        action_is_safe=True,
        legacy_mode="auto",
        action_class=action_class,
    )

    assert action_class.name == "read_pii_table"
    assert decision.context.authority.value == "delegate"
    assert decision.requires_approval is True
    assert decision.reason == "action_matrix_approve"


def test_delegate_auto_mode_allows_gold_sql_read() -> None:
    classifier = ActionClassifier()
    candidate = ActionCandidate("sql_query", {"table_tier": "gold"})
    action_class = classifier.classify(candidate)

    decision = AutonomyPolicy().evaluate(
        action_is_safe=True,
        legacy_mode="auto",
        action_class=action_class,
    )

    assert action_class.name == "read_sql_gold"
    assert decision.requires_approval is False
    assert decision.blocked is False


def test_permission_policy_uses_arguments_for_prod_deploy() -> None:
    policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")

    allowed, reason = policy.check("generate_deployment", {"environment": "production"})

    assert allowed is False
    assert "Delegate mode" in reason
    assert "requires approval" in reason


def test_permission_policy_uses_arguments_for_bronze_sql_in_delegate() -> None:
    policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")

    allowed, reason = policy.check("sql_query", {"table_tier": "bronze"})

    assert allowed is False
    assert "Delegate mode" in reason
    assert "requires approval" in reason


def test_permission_policy_uses_action_classifier_for_git_pr() -> None:
    policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")

    allowed, reason = policy.check(
        "create_git_pr",
        {"title": "PR", "body": "body", "head": "feature-branch"},
    )

    assert allowed is False
    assert "Delegate mode" in reason
    assert "requires approval" in reason


def test_permission_policy_uses_unknown_row_for_generic_execute_code() -> None:
    policy = PermissionPolicy(mode=PermissionMode.FULL_ACCESS, agent_mode="auto")

    allowed, reason = policy.check("execute_code", {"code": "print('hello')"})

    assert allowed is False
    assert "Delegate mode" in reason
    assert "requires approval" in reason
