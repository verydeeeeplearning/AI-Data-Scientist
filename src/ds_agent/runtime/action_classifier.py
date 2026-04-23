"""Strategy-based tool-to-action classification for autonomy decisions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from ds_agent.domain.value_objects.action_class import ActionClass, get_action_class

_READ_ONLY_TOOLS = {
    "ask_user": "read_sql_gold",
    "data_loader": "read_sql_gold",
    "data_profiler": "read_sql_gold",
    "describe_table_trust": "read_sql_gold",
    "get_work_object": "read_sql_gold",
    "get_work_object_timeline": "read_sql_gold",
    "list_files": "read_sql_gold",
    "list_work_objects": "read_sql_gold",
    "lookup_term": "read_sql_gold",
    "memory_search": "read_sql_gold",
    "read_file": "read_sql_gold",
    "schema_inspect": "read_sql_gold",
    "search_sessions": "read_sql_gold",
    "semantic_query": "read_sql_gold",
    "skill_list": "read_sql_gold",
    "skill_search": "read_sql_gold",
    "skill_view": "read_sql_gold",
    "web_search": "read_sql_gold",
}
_ARTIFACT_TOOLS = {
    "advance_work_object_phase": "artifact_draft",
    "close_work_object": "artifact_draft",
    "create_work_object": "artifact_draft",
    "dashboard_spec": "artifact_draft",
    "evaluate_model": "artifact_draft",
    "generate_report": "artifact_draft",
    "link_external_resource": "artifact_draft",
    "memory_store": "artifact_draft",
    "notebook_generate": "artifact_draft",
    "render_stakeholder_artifact": "artifact_draft",
    "run_eda": "artifact_draft",
    "slide_generate": "artifact_draft",
    "write_file": "artifact_draft",
}
_FIXED_TOOL_MAP = {
    **_READ_ONLY_TOOLS,
    **_ARTIFACT_TOOLS,
    "create_git_pr": "jira_create",
    "create_jira_ticket": "jira_create",
    "feature_engineer": "feature_engineering",
    "open_git_pr": "jira_create",
    "create_calendar_event": "email_send",
    "post_to_slack": "slack_post",
    "publish_confluence_page": "jira_create",
    "publish_notion_page": "jira_create",
    "send_email": "email_send",
    "send_to_slack": "slack_post",
    "train_model": "model_training",
    "list_my_portfolio": "read_sql_gold",
    "pause_task": "jira_create",
    "resume_task": "jira_create",
    "set_sla": "jira_create",
    "request_monitoring": "jira_create",
    "list_learning_inbox": "read_sql_gold",
    "review_learning_item": "jira_create",
    "get_learning_item": "read_sql_gold",
    "list_promotions": "read_sql_gold",
    "list_deprecations": "read_sql_gold",
    "rollback_promotion": "jira_create",
}
_DELETE_PATTERN = re.compile(
    r"\b("
    r"delete\s+from|drop\s+table|truncate\s+table|insert\s+into|update\s+\w+|"
    r"merge\s+into|alter\s+table|create\s+table|replace\s+table|copy\s+into|"
    r"os\.remove|os\.unlink|Path\([^)]*\)\.unlink|\.unlink\(|shutil\.rmtree|rmtree\("
    r")\b",
    re.IGNORECASE,
)
_MODEL_TOKENS = (
    "gridsearchcv",
    "randomizedsearchcv",
    "cross_val_score",
    "randomforestclassifier",
    "randomforestregressor",
    "logisticregression",
    "linearregression",
    "lgbmclassifier",
    "lgbmregressor",
    "xgbclassifier",
    "xgbregressor",
    "catboost",
    "predict_proba(",
    "classification_report(",
    "roc_auc_score(",
    "model.fit(",
    "clf.fit(",
    "regressor.fit(",
    "estimator.fit(",
)
_FEATURE_TOKENS = (
    "standardscaler",
    "minmaxscaler",
    "onehotencoder",
    "ordinalencoder",
    "simpleimputer",
    "columntransformer",
    "featureunion",
    "polynomialfeatures",
    "fit_transform(",
    "get_dummies(",
    "labelencoder",
    "kbinsdiscretizer",
)
_ARTIFACT_TOKENS = (
    "plt.savefig(",
    ".savefig(",
    ".to_csv(",
    ".to_parquet(",
    ".to_excel(",
    ".write_text(",
    ".write_bytes(",
    "json.dump(",
    "yaml.dump(",
    "nbformat",
    "markdown",
)


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    """One prospective action to classify."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


class ActionClassificationStrategy(Protocol):
    """One classifier strategy in the action-class resolution chain."""

    def classify(self, candidate: ActionCandidate) -> ActionClass | None: ...


@dataclass(frozen=True, slots=True)
class ToolMapClassificationStrategy:
    """Map fixed tool names directly to action classes."""

    tool_map: Mapping[str, str]

    def classify(self, candidate: ActionCandidate) -> ActionClass | None:
        action_name = self.tool_map.get(candidate.tool_name)
        if action_name is None:
            return None
        return get_action_class(action_name)


class SqlActionClassificationStrategy:
    """Inspect SQL-like requests for sensitivity, tier, and destructive intent."""

    def classify(self, candidate: ActionCandidate) -> ActionClass | None:
        if candidate.tool_name != "sql_query":
            return None

        arguments = dict(candidate.arguments)
        statement = str(
            arguments.get("statement") or arguments.get("sql") or arguments.get("query") or ""
        ).strip()
        if statement and _DELETE_PATTERN.search(statement):
            return get_action_class("delete_table")

        sensitivity = str(arguments.get("data_sensitivity", "")).strip().lower()
        if sensitivity in {"pii", "personal"}:
            return get_action_class("read_pii_table")
        if sensitivity in {"restricted", "sensitive"}:
            return get_action_class("read_sensitive_table")

        tier = (
            str(
                arguments.get("source_tier")
                or arguments.get("table_tier")
                or arguments.get("dataset_tier")
                or arguments.get("domain_tier")
                or ""
            )
            .strip()
            .lower()
        )
        if tier == "bronze":
            return get_action_class("read_sql_bronze")
        return get_action_class("read_sql_gold")


class DeploymentActionClassificationStrategy:
    """Classify deployment tools by target environment."""

    def classify(self, candidate: ActionCandidate) -> ActionClass | None:
        if candidate.tool_name != "generate_deployment":
            return None

        arguments = dict(candidate.arguments)
        target = (
            str(
                arguments.get("environment")
                or arguments.get("target_environment")
                or arguments.get("stage")
                or ""
            )
            .strip()
            .lower()
        )
        if target in {"prod", "production"}:
            return get_action_class("prod_deploy")
        return get_action_class("staging_deploy")


class GovernanceActionClassificationStrategy:
    """Classify governance and autonomy-control mutations conservatively."""

    def classify(self, candidate: ActionCandidate) -> ActionClass | None:
        arguments = dict(candidate.arguments)

        if candidate.tool_name == "policy_check":
            if bool(arguments.get("record_approval", False)):
                return get_action_class("jira_create")
            return get_action_class("read_sql_gold")

        if candidate.tool_name == "lineage_capture":
            action = str(arguments.get("action", "")).strip().lower()
            if action == "trace":
                return get_action_class("read_sql_gold")
            return get_action_class("artifact_draft")

        if candidate.tool_name == "load_semantic_pack":
            if bool(arguments.get("dry_run", True)):
                return get_action_class("read_sql_gold")
            return get_action_class("jira_create")

        if candidate.tool_name == "standing_order":
            action = str(arguments.get("action", "")).strip().lower()
            if action in {"list", "view_history"}:
                return get_action_class("read_sql_gold")
            if action in {"create", "update", "delete", "run_now"}:
                return get_action_class("jira_create")
            return get_action_class("unknown")

        return None


class PythonExecutionActionClassificationStrategy:
    """Inspect generic Python execution tools for DS intent or destructive writes."""

    def classify(self, candidate: ActionCandidate) -> ActionClass | None:
        if candidate.tool_name not in {"execute_code", "distributed_exec"}:
            return None

        code = str(candidate.arguments.get("code", "") or "").strip().lower()
        if not code:
            return get_action_class("unknown")

        if _DELETE_PATTERN.search(code):
            return get_action_class("delete_table")
        if any(token in code for token in _MODEL_TOKENS):
            return get_action_class("model_training")
        if any(token in code for token in _FEATURE_TOKENS):
            return get_action_class("feature_engineering")
        if any(token in code for token in _ARTIFACT_TOKENS):
            return get_action_class("artifact_draft")
        return get_action_class("unknown")


_DEFAULT_STRATEGIES: tuple[ActionClassificationStrategy, ...] = (
    SqlActionClassificationStrategy(),
    DeploymentActionClassificationStrategy(),
    GovernanceActionClassificationStrategy(),
    PythonExecutionActionClassificationStrategy(),
    ToolMapClassificationStrategy(_FIXED_TOOL_MAP),
)


class ActionClassifier:
    """Classify tools into action classes with ordered, inspectable strategies."""

    def __init__(
        self,
        strategies: Sequence[ActionClassificationStrategy] | None = None,
    ) -> None:
        self._strategies = tuple(strategies or _DEFAULT_STRATEGIES)

    def classify(self, candidate: ActionCandidate) -> ActionClass:
        for strategy in self._strategies:
            resolved = strategy.classify(candidate)
            if resolved is not None:
                return resolved
        return get_action_class("unknown")
