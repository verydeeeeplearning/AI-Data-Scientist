"""Tests for secret storage primitives."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import structlog

from ds_agent.infrastructure.secrets.api_key_manager import ApiKeyManager
from ds_agent.infrastructure.secrets.config_secret_manager import (
    ConfigSecretManager,
    strip_persisted_config_secrets,
)
from ds_agent.infrastructure.secrets.connector_secret_manager import ConnectorSecretManager
from ds_agent.infrastructure.secrets.secret_storage import (
    InMemorySecretStorage,
    KeyringSecretStorage,
    SecretStorageError,
    build_default_secret_storage,
)

_SENTINEL_SECRET = "sk-ant-ULTRA-SECRET-PLAINTEXT-VALUE-9x8y7z"


def _log_contains_secret(captured: list[dict], secret: str) -> bool:
    """Return True when any captured log record's serialized form contains the secret."""
    return any(secret in json.dumps(record, default=str) for record in captured)


class TestInMemorySecretStorage:
    def test_store_and_retrieve(self):
        storage = InMemorySecretStorage()
        storage.store("api_key:anthropic", "sk-ant-test123")

        assert storage.retrieve("api_key:anthropic") == "sk-ant-test123"

    def test_retrieve_missing_returns_none(self):
        storage = InMemorySecretStorage()

        assert storage.retrieve("missing") is None

    def test_delete_removes_secret(self):
        storage = InMemorySecretStorage()
        storage.store("key", "value")

        assert storage.delete("key") is True
        assert storage.retrieve("key") is None


class TestApiKeyManager:
    def test_masked_values_do_not_expose_plaintext(self):
        manager = ApiKeyManager(InMemorySecretStorage())
        manager.set("anthropic", "sk-ant-secret-12345678")

        masked = manager.masked(["anthropic"])

        assert masked["anthropic"] == "sk-a...5678"


class TestConfigSecretManager:
    def test_migrates_plaintext_secret_fields_from_raw_data(self):
        manager = ConfigSecretManager(InMemorySecretStorage())
        data = {
            "oauth": {"gemini_client_id": "client-id", "gemini_client_secret": "super-secret"},
            "channels": {"telegram": {"enabled": True, "bot_token": "12345:bot-token"}},
        }

        migrated = manager.migrate_from_data(data)

        assert migrated is True
        assert manager.get("oauth.gemini_client_secret") == "super-secret"
        assert manager.get("channels.telegram.bot_token") == "12345:bot-token"
        assert "gemini_client_secret" not in data["oauth"]
        assert "bot_token" not in data["channels"]["telegram"]

    def test_strip_persisted_config_secrets_removes_nested_values(self):
        data = {
            "oauth": {"gemini_client_id": "client-id", "gemini_client_secret": "super-secret"},
            "channels": {"telegram": {"enabled": True, "bot_token": "12345:bot-token"}},
        }

        sanitized = strip_persisted_config_secrets(data)

        assert sanitized["oauth"] == {"gemini_client_id": "client-id"}
        assert sanitized["channels"]["telegram"] == {"enabled": True}
        assert data["oauth"]["gemini_client_secret"] == "super-secret"
        assert data["channels"]["telegram"]["bot_token"] == "12345:bot-token"


class TestConnectorSecretManager:
    def test_store_load_and_delete_secret_payload(self):
        manager = ConnectorSecretManager(InMemorySecretStorage())

        credential_ref = manager.store(
            "analytics_prod",
            {"kind": "password", "password": "super-secret"},
        )

        assert credential_ref == "connector/analytics_prod/credentials"
        assert manager.has_secret(credential_ref) is True
        assert manager.load(credential_ref) == {
            "kind": "password",
            "password": "super-secret",
        }
        assert manager.delete(credential_ref) is True
        assert manager.load(credential_ref) is None


class TestSecretStorageFallback:
    def test_build_default_secret_storage_falls_back_to_in_memory_and_logs_warning(self):
        with (
            patch(
                "ds_agent.infrastructure.secrets.secret_storage.KeyringSecretStorage",
                side_effect=SecretStorageError("no keyring backend"),
            ),
            structlog.testing.capture_logs() as captured,
        ):
            storage = build_default_secret_storage()

        assert isinstance(storage, InMemorySecretStorage)
        assert any(event.get("event") == "secret_storage_fallback_enabled" for event in captured)


class TestKeyringChunking:
    """Large secrets must be split across multiple keyring entries.

    Why: Windows Credential Manager caps a single credential blob at 2560
    bytes (UTF-16LE). Codex CLI's chatgpt OAuth bundle is ~4KB, which
    triggers CredWrite error 1783 if stored as one entry. Chunking is
    transparent — store/retrieve round-trip the original payload, and a
    later smaller value cleans up stale chunks.
    """

    def _make_storage(self) -> tuple[KeyringSecretStorage, MagicMock]:
        storage = KeyringSecretStorage.__new__(KeyringSecretStorage)
        storage._service = "ds-agent-test"
        fake = MagicMock()
        store: dict[tuple[str, str], str] = {}

        def set_password(service, key, value):
            store[(service, key)] = value

        def get_password(service, key):
            return store.get((service, key))

        class _PasswordDeleteError(Exception):
            pass

        def delete_password(service, key):
            if (service, key) not in store:
                raise _PasswordDeleteError()
            del store[(service, key)]

        fake.set_password.side_effect = set_password
        fake.get_password.side_effect = get_password
        fake.delete_password.side_effect = delete_password
        fake.errors.PasswordDeleteError = _PasswordDeleteError
        storage._keyring = fake
        return storage, fake

    def test_small_value_stored_inline(self):
        storage, fake = self._make_storage()
        storage.store("api_key:anthropic", "sk-ant-short")

        assert storage.retrieve("api_key:anthropic") == "sk-ant-short"
        # Small payloads must not create chunk parts.
        assert all("__part" not in call.args[1] for call in fake.set_password.call_args_list)

    def test_large_value_round_trips(self):
        storage, _ = self._make_storage()
        # Simulate Codex chatgpt OAuth bundle (~4KB JSON).
        large = "A" * 4500
        storage.store("oauth:openai-codex:codex-cli", large)

        assert storage.retrieve("oauth:openai-codex:codex-cli") == large

    def test_large_value_creates_chunks_and_header(self):
        storage, fake = self._make_storage()
        large = "x" * 3500  # > 1024 chunk size, < 5 chunks
        storage.store("oauth:test", large)

        keys_written = [call.args[1] for call in fake.set_password.call_args_list]
        assert "oauth:test__part0" in keys_written
        assert "oauth:test__part1" in keys_written
        assert "oauth:test__part2" in keys_written
        assert "oauth:test__part3" in keys_written
        # Header at the canonical key, written last.
        assert keys_written[-1] == "oauth:test"
        header = fake.set_password.call_args_list[-1].args[2]
        assert header.startswith("__ds_chunked__:4")

    def test_overwrite_with_smaller_value_clears_old_chunks(self):
        storage, fake = self._make_storage()
        storage.store("oauth:test", "x" * 3000)
        storage.store("oauth:test", "small-value")

        assert storage.retrieve("oauth:test") == "small-value"
        # Old chunk parts must be gone.
        delete_calls = [call.args[1] for call in fake.delete_password.call_args_list]
        assert "oauth:test__part0" in delete_calls

    def test_delete_removes_chunks_and_header(self):
        storage, _fake = self._make_storage()
        storage.store("oauth:test", "y" * 3000)
        assert storage.delete("oauth:test") is True
        assert storage.retrieve("oauth:test") is None

    def test_partial_chunk_write_failure_rolls_back(self):
        storage, fake = self._make_storage()
        # Fail on the third set_password call (second chunk write).
        original = fake.set_password.side_effect
        call_count = {"n": 0}

        def flaky(service, key, value):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise RuntimeError("simulated keyring failure")
            return original(service, key, value)

        fake.set_password.side_effect = flaky

        with pytest.raises(SecretStorageError):
            storage.store("oauth:test", "z" * 3000)

        # No header written, no orphan chunks readable.
        assert storage.retrieve("oauth:test") is None


class TestSecretStorageStatus:
    """`describe_secret_storage` — operator-facing status of the active backend."""

    def setup_method(self):
        from ds_agent.infrastructure.secrets.secret_storage import set_shared_secret_storage

        set_shared_secret_storage(None)

    def teardown_method(self):
        from ds_agent.infrastructure.secrets.secret_storage import set_shared_secret_storage

        set_shared_secret_storage(None)

    def test_persistent_backend_reports_not_degraded(self):
        from ds_agent.infrastructure.secrets.secret_storage import (
            describe_secret_storage,
            set_shared_secret_storage,
        )

        class _FakePersistent:
            backend_name = "keyring"
            persistent = True

            def store(self, k, v): pass
            def retrieve(self, k): return None
            def delete(self, k): return False
            def exists(self, k): return False

        set_shared_secret_storage(_FakePersistent())
        status = describe_secret_storage()

        assert status["backend"] == "keyring"
        assert status["persistent"] is True
        assert status["degraded"] is False
        assert "message" in status

    def test_in_memory_backend_reports_degraded_with_actionable_message(self):
        from ds_agent.infrastructure.secrets.secret_storage import (
            describe_secret_storage,
            set_shared_secret_storage,
        )

        set_shared_secret_storage(InMemorySecretStorage())
        status = describe_secret_storage()

        assert status["backend"] == "in_memory"
        assert status["persistent"] is False
        assert status["degraded"] is True
        # Operators must be told what to do, not just that something is wrong.
        assert "keyring" in status["message"].lower() or "secret" in status["message"].lower()


class TestSecretRedactionInLogs:
    """Quality gate: logs must never contain secret plaintext."""

    def test_in_memory_store_retrieve_delete_does_not_log_value(self):
        storage = InMemorySecretStorage()
        with structlog.testing.capture_logs() as captured:
            storage.store("api_key:anthropic", _SENTINEL_SECRET)
            assert storage.retrieve("api_key:anthropic") == _SENTINEL_SECRET
            storage.delete("api_key:anthropic")

        assert not _log_contains_secret(captured, _SENTINEL_SECRET)

    def test_fallback_warning_does_not_leak_error_with_secret_payload(self):
        """A backend failure echoing the secret in its message must not leak through logs."""
        exc_with_secret = SecretStorageError(
            f"Windows Credential Manager rejected value={_SENTINEL_SECRET}"
        )
        with (
            patch(
                "ds_agent.infrastructure.secrets.secret_storage.KeyringSecretStorage",
                side_effect=exc_with_secret,
            ),
            structlog.testing.capture_logs() as captured,
        ):
            build_default_secret_storage()

        assert not _log_contains_secret(captured, _SENTINEL_SECRET)

    def test_keyring_retrieve_backend_error_redacts_secret_in_logs(self):
        """If the OS backend raises with the secret in the exception, it must be redacted."""
        fake_keyring = MagicMock()
        fake_keyring.get_password.side_effect = RuntimeError(
            f"DBus error while returning value={_SENTINEL_SECRET}"
        )
        storage = KeyringSecretStorage.__new__(KeyringSecretStorage)
        storage._service = "ds-agent-test"
        storage._keyring = fake_keyring

        with structlog.testing.capture_logs() as captured:
            result = storage.retrieve("api_key:anthropic")

        assert result is None
        assert not _log_contains_secret(captured, _SENTINEL_SECRET)

    def test_keyring_delete_backend_error_redacts_secret_in_logs(self):
        """Delete-path exceptions must not leak any plaintext echoed by the backend."""
        fake_keyring = MagicMock()
        fake_keyring.errors = MagicMock()
        # Only PasswordDeleteError should return False silently; other exceptions log+return False.
        fake_keyring.errors.PasswordDeleteError = type("PasswordDeleteError", (Exception,), {})
        fake_keyring.delete_password.side_effect = RuntimeError(
            f"backend crashed, value={_SENTINEL_SECRET}"
        )
        storage = KeyringSecretStorage.__new__(KeyringSecretStorage)
        storage._service = "ds-agent-test"
        storage._keyring = fake_keyring

        with structlog.testing.capture_logs() as captured:
            result = storage.delete("api_key:anthropic")

        assert result is False
        assert not _log_contains_secret(captured, _SENTINEL_SECRET)

    def test_api_key_manager_set_get_delete_does_not_log_value(self):
        manager = ApiKeyManager(InMemorySecretStorage())
        with structlog.testing.capture_logs() as captured:
            manager.set("anthropic", _SENTINEL_SECRET)
            assert manager.get("anthropic") == _SENTINEL_SECRET
            manager.delete("anthropic")

        assert not _log_contains_secret(captured, _SENTINEL_SECRET)

    def test_config_secret_manager_migrate_does_not_log_value(self):
        storage = InMemorySecretStorage()
        manager = ConfigSecretManager(storage)
        data = {
            "oauth": {"gemini_client_secret": _SENTINEL_SECRET},
            "channels": {"telegram": {"enabled": True, "bot_token": _SENTINEL_SECRET}},
        }
        with structlog.testing.capture_logs() as captured:
            manager.migrate_from_data(data)

        assert not _log_contains_secret(captured, _SENTINEL_SECRET)


@pytest.fixture
def keyring_redaction_parametrize():
    """Shared sentinel — kept for future parametrized redaction scenarios."""
    return _SENTINEL_SECRET
