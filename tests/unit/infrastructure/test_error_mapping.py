"""Unit tests for user-facing RPC error mapping."""

from ds_agent.api.error_mapping import present_invalid_params_error, present_rpc_exception


def test_invalid_params_preserves_detail_with_stable_dsa_code() -> None:
    presentation = present_invalid_params_error("Connector name is required")

    assert presentation.catalog_code == "DSA-SYS-002"
    assert presentation.message == "Connector name is required [DSA-SYS-002]"
    assert presentation.technical_message == "Connector name is required"
    assert presentation.warnings == ["Review the field values and try again."]


def test_connector_auth_failure_maps_to_auth_catalog() -> None:
    presentation = present_rpc_exception(
        "connector.test",
        PermissionError("password authentication failed for user readonly_user"),
    )

    assert presentation.catalog_code == "DSA-AUTH-002"
    assert "[DSA-AUTH-002]" in presentation.message
    assert presentation.warnings == [
        "Reconnect the account or update the saved secret, then retry."
    ]


def test_chat_timeout_maps_to_llm_timeout_catalog() -> None:
    presentation = present_rpc_exception("chat.send", TimeoutError("request timed out"))

    assert presentation.catalog_code == "DSA-LLM-001"
    assert "[DSA-LLM-001]" in presentation.message
    assert presentation.technical_message == "request timed out"


def test_file_export_failure_maps_to_export_catalog() -> None:
    presentation = present_rpc_exception("files.export.report", OSError("permission denied"))

    assert presentation.catalog_code == "DSA-FILE-002"
    assert "[DSA-FILE-002]" in presentation.message
