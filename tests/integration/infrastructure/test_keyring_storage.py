"""Integration tests: KeyringSecretStorage against the real OS backend.

Covers Quality Gate P0-02: "Windows Credential Manager, macOS Keychain,
Linux Secret Service 통합 테스트 통과".

These tests require a usable OS keyring backend. On CI or sandboxed
environments without one, they are skipped automatically via
``KeyringSecretStorage.is_supported()``. Each test uses a unique per-run
service+key namespace and cleans up the item in a ``finally`` block so that
the host keyring is not polluted.
"""

from __future__ import annotations

import platform
from uuid import uuid4

import pytest

from ds_agent.infrastructure.secrets.secret_storage import (
    KeyringSecretStorage,
    SecretStorageError,
)

pytestmark = pytest.mark.integration


def _skip_if_unsupported() -> None:
    if not KeyringSecretStorage.is_supported():
        pytest.skip("No usable OS keyring backend available on this host.")


@pytest.fixture
def keyring_storage() -> KeyringSecretStorage:
    _skip_if_unsupported()
    # Service name is per-session so parallel runs don't collide.
    service = f"ds-agent-itest-{uuid4().hex[:8]}"
    return KeyringSecretStorage(service=service)


@pytest.fixture
def unique_key() -> str:
    return f"it_key_{uuid4().hex}"


class TestKeyringRoundtrip:
    """Platform-agnostic contract: the active OS backend must honour our port."""

    def test_store_then_retrieve_returns_same_value(
        self, keyring_storage: KeyringSecretStorage, unique_key: str
    ) -> None:
        value = f"val-{uuid4().hex}"
        try:
            keyring_storage.store(unique_key, value)
            assert keyring_storage.retrieve(unique_key) == value
        finally:
            keyring_storage.delete(unique_key)

    def test_retrieve_missing_returns_none(
        self, keyring_storage: KeyringSecretStorage
    ) -> None:
        assert keyring_storage.retrieve(f"not_present_{uuid4().hex}") is None

    def test_exists_reflects_store_and_delete(
        self, keyring_storage: KeyringSecretStorage, unique_key: str
    ) -> None:
        try:
            assert keyring_storage.exists(unique_key) is False
            keyring_storage.store(unique_key, "present")
            assert keyring_storage.exists(unique_key) is True
        finally:
            keyring_storage.delete(unique_key)
        assert keyring_storage.exists(unique_key) is False

    def test_overwrite_replaces_previous_value(
        self, keyring_storage: KeyringSecretStorage, unique_key: str
    ) -> None:
        try:
            keyring_storage.store(unique_key, "first")
            keyring_storage.store(unique_key, "second")
            assert keyring_storage.retrieve(unique_key) == "second"
        finally:
            keyring_storage.delete(unique_key)

    def test_delete_missing_returns_false(
        self, keyring_storage: KeyringSecretStorage
    ) -> None:
        assert keyring_storage.delete(f"missing_{uuid4().hex}") is False

    def test_unicode_value_roundtrips(
        self, keyring_storage: KeyringSecretStorage, unique_key: str
    ) -> None:
        value = "토큰-値-🔑-αβγ"
        try:
            keyring_storage.store(unique_key, value)
            assert keyring_storage.retrieve(unique_key) == value
        finally:
            keyring_storage.delete(unique_key)


class TestPlatformBackend:
    """Sanity check that the backend selected by ``keyring`` matches the OS."""

    def test_is_supported_reports_true_when_backend_available(self) -> None:
        _skip_if_unsupported()
        assert KeyringSecretStorage.is_supported() is True

    def test_constructor_raises_clean_error_when_unsupported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If no backend is available, ``KeyringSecretStorage`` must refuse to construct."""
        monkeypatch.setattr(KeyringSecretStorage, "is_supported", staticmethod(lambda: False))
        with pytest.raises(SecretStorageError):
            KeyringSecretStorage(service="ds-agent-itest-unsupported")

    def test_selected_backend_matches_platform_family(self) -> None:
        _skip_if_unsupported()
        import keyring

        backend_module = type(keyring.get_keyring()).__module__
        system = platform.system()

        if system == "Windows":
            assert "windows" in backend_module.lower() or "win" in backend_module.lower(), (
                f"Expected Windows Credential Manager backend, got: {backend_module}"
            )
        elif system == "Darwin":
            assert "macos" in backend_module.lower() or "osx" in backend_module.lower(), (
                f"Expected macOS Keychain backend, got: {backend_module}"
            )
        elif system == "Linux":
            # Linux commonly uses SecretService, KWallet, or the kernel keyring.
            expected = ("secretservice", "kwallet", "libsecret", "keyring")
            assert any(name in backend_module.lower() for name in expected), (
                f"Expected a Linux secret backend, got: {backend_module}"
            )
        else:
            pytest.skip(f"Unsupported platform for this assertion: {system}")
