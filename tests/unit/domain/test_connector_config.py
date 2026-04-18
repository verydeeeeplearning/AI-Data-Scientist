"""ConnectorConfig and SQL Validator tests."""

import pytest

from ds_agent.domain.value_objects.connector import (
    ConnectorConfig,
    ConnectorType,
    CostEstimate,
    QuerySpec,
    SqlValidationResult,
    validate_sql_safety,
)


class TestConnectorConfig:
    def test_valid_config(self):
        cfg = ConnectorConfig(
            type=ConnectorType.SNOWFLAKE,
            host="account.snowflakecomputing.com",
            database="analytics",
        )
        assert cfg.type == ConnectorType.SNOWFLAKE
        assert cfg.read_only is True
        assert cfg.timeout_seconds == 30

    def test_missing_database_raises(self):
        with pytest.raises(ValueError, match="database"):
            ConnectorConfig(type=ConnectorType.POSTGRES, host="localhost")

    def test_frozen(self):
        cfg = ConnectorConfig(type=ConnectorType.BIGQUERY, database="myproject")
        with pytest.raises(AttributeError):
            cfg.database = "other"  # type: ignore[misc]


class TestQuerySpec:
    def test_defaults(self):
        q = QuerySpec(sql="SELECT 1")
        assert q.connector_name == "default"
        assert q.effective_timeout == 30

    def test_timeout_override(self):
        q = QuerySpec(sql="SELECT 1", timeout_override=60)
        assert q.effective_timeout == 60


class TestCostEstimate:
    def test_within_limit(self):
        c = CostEstimate(estimated_cost_usd=2.0, is_within_limit=True)
        assert c.is_within_limit is True


class TestSqlValidator:
    def test_safe_select(self):
        result = validate_sql_safety("SELECT * FROM users WHERE id = 1")
        assert result.is_safe is True

    def test_safe_cte(self):
        sql = """
        WITH active AS (
            SELECT * FROM users WHERE status = 'active'
        )
        SELECT count(*) FROM active
        """
        result = validate_sql_safety(sql)
        assert result.is_safe is True

    def test_safe_explain(self):
        result = validate_sql_safety("EXPLAIN SELECT * FROM users")
        assert result.is_safe is True

    def test_blocks_drop(self):
        result = validate_sql_safety("DROP TABLE users")
        assert result.is_safe is False

    def test_blocks_insert(self):
        result = validate_sql_safety("INSERT INTO users (name) VALUES ('test')")
        assert result.is_safe is False

    def test_blocks_update(self):
        result = validate_sql_safety("UPDATE users SET name = 'x' WHERE id = 1")
        assert result.is_safe is False

    def test_blocks_delete(self):
        result = validate_sql_safety("DELETE FROM users WHERE id = 1")
        assert result.is_safe is False

    def test_blocks_create(self):
        result = validate_sql_safety("CREATE TABLE new_table (id INT)")
        assert result.is_safe is False

    def test_blocks_truncate(self):
        result = validate_sql_safety("TRUNCATE TABLE users")
        assert result.is_safe is False

    def test_blocks_grant(self):
        result = validate_sql_safety("GRANT SELECT ON users TO role")
        assert result.is_safe is False

    def test_empty_query(self):
        result = validate_sql_safety("")
        assert result.is_safe is False

    def test_comment_only_query(self):
        result = validate_sql_safety("-- just a comment")
        assert result.is_safe is False

    def test_blocks_alter(self):
        result = validate_sql_safety("ALTER TABLE users ADD COLUMN age INT")
        assert result.is_safe is False

    def test_blocks_merge(self):
        result = validate_sql_safety(
            "MERGE INTO target USING source ON target.id = source.id"
        )
        assert result.is_safe is False
