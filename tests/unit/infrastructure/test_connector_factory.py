"""Connector factory tests."""

from __future__ import annotations

import json

import pytest

from ds_agent.domain.value_objects.connector import (
    ConnectorConfig,
    ConnectorType,
    CredentialMethod,
)
from ds_agent.infrastructure.persistence.bigquery_adapter import BigQueryAdapter
from ds_agent.infrastructure.persistence.connector_factory import (
    create_connector_adapter,
    create_connector_adapters,
)
from ds_agent.infrastructure.persistence.errors import ConnectorDependencyError
from ds_agent.infrastructure.persistence.postgres_adapter import PostgresAdapter
from ds_agent.infrastructure.persistence.snowflake_adapter import SnowflakeAdapter
from ds_agent.infrastructure.secrets.secret_storage import (
    InMemorySecretStorage,
    set_shared_secret_storage,
)


def _missing_dependency(module_name: str):
    raise ModuleNotFoundError(module_name)


class TestConnectorFactory:
    def setup_method(self) -> None:
        set_shared_secret_storage(InMemorySecretStorage())

    def teardown_method(self) -> None:
        set_shared_secret_storage(None)

    def test_create_snowflake_adapter(self) -> None:
        adapter = create_connector_adapter(
            ConnectorConfig(
                type=ConnectorType.SNOWFLAKE,
                host="account",
                database="analytics",
            )
        )
        assert isinstance(adapter, SnowflakeAdapter)

    def test_create_bigquery_adapter(self) -> None:
        adapter = create_connector_adapter(
            ConnectorConfig(
                type=ConnectorType.BIGQUERY,
                database="my-project",
            )
        )
        assert isinstance(adapter, BigQueryAdapter)

    def test_create_postgres_adapter(self) -> None:
        adapter = create_connector_adapter(
            ConnectorConfig(
                type=ConnectorType.POSTGRES,
                host="localhost",
                database="analytics",
            )
        )
        assert isinstance(adapter, PostgresAdapter)

    def test_create_named_adapter_mapping(self) -> None:
        adapters = create_connector_adapters(
            {
                "warehouse": ConnectorConfig(
                    type=ConnectorType.POSTGRES,
                    host="localhost",
                    database="analytics",
                )
            }
        )
        assert set(adapters) == {"warehouse"}
        assert isinstance(adapters["warehouse"], PostgresAdapter)

    def test_missing_snowflake_dependency_raises_on_use(self) -> None:
        adapter = SnowflakeAdapter(
            ConnectorConfig(
                type=ConnectorType.SNOWFLAKE,
                host="account",
                database="analytics",
            ),
            dependency_loader=_missing_dependency,
        )

        with pytest.raises(ConnectorDependencyError, match=r"snowflake\.connector"):
            adapter.get_schemas()

    def test_bigquery_adapter_builds_service_account_credentials(self) -> None:
        storage = InMemorySecretStorage()
        set_shared_secret_storage(storage)
        storage.store(
            "connector/warehouse_bq/credentials",
            json.dumps(
                {
                    "kind": "service_account_json",
                    "json": json.dumps(
                        {
                            "client_email": "bot@example.com",
                            "private_key": "secret",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }
                    ),
                }
            ),
        )

        adapter = BigQueryAdapter(
            ConnectorConfig(
                type=ConnectorType.BIGQUERY,
                database="analytics-project",
                credential_method=CredentialMethod.SECRET_MANAGER,
                credential_ref="connector/warehouse_bq/credentials",
            ),
            dependency_loader=lambda name: (
                _FakeServiceAccountModule()
                if name == "google.oauth2.service_account"
                else _missing_dependency(name)
            ),
        )

        credentials = adapter._build_credentials()

        assert credentials == {
            "serviceAccountInfo": {
                "client_email": "bot@example.com",
                "private_key": "secret",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }


class _FakeServiceAccountModule:
    class Credentials:
        @staticmethod
        def from_service_account_info(info: dict[str, str]) -> dict[str, dict[str, str]]:
            return {"serviceAccountInfo": info}
