"""Secret storage adapters for API keys and OAuth tokens."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger()


def _redact_error(exc: BaseException) -> str:
    """Return a log-safe descriptor for a backend exception.

    Why: backend libraries (OS keyring, DBus) sometimes echo the caller-provided
    value in their exception messages. Logging ``str(exc)`` therefore risks
    leaking the secret plaintext. We log only the exception type name, which is
    sufficient for triage without ever exposing secret material.
    """
    return type(exc).__name__


class SecretStorageError(RuntimeError):
    """Raised when the secure storage backend is unavailable."""


@runtime_checkable
class SecretStoragePort(Protocol):
    """Minimal credential storage contract."""

    backend_name: str
    persistent: bool

    def store(self, key: str, value: str) -> None:
        """Persist a secret value under a stable key."""

    def retrieve(self, key: str) -> str | None:
        """Load a previously stored secret value."""

    def delete(self, key: str) -> bool:
        """Delete a secret value. Returns True when one existed."""

    def exists(self, key: str) -> bool:
        """Return True when a secret exists."""


class InMemorySecretStorage:
    """Process-local fallback storage used in tests and degraded mode."""

    backend_name = "in_memory"
    persistent = False

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self._store[key] = value

    def retrieve(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        return key in self._store


class KeyringSecretStorage:
    """OS-backed secret storage via the optional ``keyring`` package.

    Transparently chunks large payloads. Windows Credential Manager caps a
    single credential blob at 2560 bytes (UTF-16LE encoded), so OAuth tokens
    larger than ~1200 chars (e.g. Codex CLI's chatgpt JWT bundle) must be
    split across multiple credential entries to avoid CredWrite error 1783.
    """

    backend_name = "keyring"
    persistent = True

    # Conservative per-chunk char count. UTF-16LE doubles bytes, so 1024
    # chars = 2048 bytes, leaving headroom under the 2560-byte Windows cap.
    _CHUNK_SIZE = 1024
    _CHUNK_HEADER = "__ds_chunked__:"
    _CHUNK_KEY_FMT = "{key}__part{idx}"

    def __init__(self, service: str = "ds-agent") -> None:
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise SecretStorageError("Python package 'keyring' is not installed.") from exc

        if not self.is_supported():
            raise SecretStorageError("No supported OS keyring backend is available.")

        self._service = service
        self._keyring = keyring

    @staticmethod
    def is_supported() -> bool:
        """Return True when ``keyring`` is importable and has a usable backend."""
        try:
            import keyring
            from keyring.backends import fail
        except ImportError:
            return False
        except Exception:
            return True

        try:
            backend = keyring.get_keyring()
        except Exception:
            return False
        return not isinstance(backend, fail.Keyring)

    def _delete_existing_chunks(self, key: str) -> None:
        """Remove leftover chunk parts from a previous larger value."""
        try:
            existing = self._keyring.get_password(self._service, key)
        except Exception:
            return
        if not existing or not existing.startswith(self._CHUNK_HEADER):
            return
        try:
            count = int(existing[len(self._CHUNK_HEADER):])
        except ValueError:
            return
        errors = getattr(self._keyring, "errors", None)
        delete_error = getattr(errors, "PasswordDeleteError", Exception)
        for idx in range(count):
            chunk_key = self._CHUNK_KEY_FMT.format(key=key, idx=idx)
            try:
                self._keyring.delete_password(self._service, chunk_key)
            except delete_error:
                pass
            except Exception:
                pass

    def store(self, key: str, value: str) -> None:
        try:
            self._delete_existing_chunks(key)
            if len(value) <= self._CHUNK_SIZE:
                self._keyring.set_password(self._service, key, value)
                return

            chunks = [
                value[i : i + self._CHUNK_SIZE]
                for i in range(0, len(value), self._CHUNK_SIZE)
            ]
            written: list[str] = []
            try:
                for idx, chunk in enumerate(chunks):
                    chunk_key = self._CHUNK_KEY_FMT.format(key=key, idx=idx)
                    self._keyring.set_password(self._service, chunk_key, chunk)
                    written.append(chunk_key)
                # Write header LAST so a crash mid-write leaves the prior
                # value (or nothing) addressable, never a partial chunk set.
                header = f"{self._CHUNK_HEADER}{len(chunks)}"
                self._keyring.set_password(self._service, key, header)
            except Exception:
                errors = getattr(self._keyring, "errors", None)
                delete_error = getattr(errors, "PasswordDeleteError", Exception)
                for chunk_key in written:
                    try:
                        self._keyring.delete_password(self._service, chunk_key)
                    except delete_error:
                        pass
                    except Exception:
                        pass
                raise
        except Exception as exc:  # pragma: no cover - backend-specific
            raise SecretStorageError(f"Failed to store secret '{key}'.") from exc

    def retrieve(self, key: str) -> str | None:
        try:
            value = self._keyring.get_password(self._service, key)
        except Exception as exc:
            logger.warning(
                "secret_storage_read_failed",
                backend=self.backend_name,
                key=key,
                error_type=_redact_error(exc),
            )
            return None
        if value is None or not value.startswith(self._CHUNK_HEADER):
            return value
        try:
            count = int(value[len(self._CHUNK_HEADER):])
        except ValueError:
            logger.warning(
                "secret_storage_chunk_header_invalid",
                backend=self.backend_name,
                key=key,
            )
            return None
        parts: list[str] = []
        for idx in range(count):
            chunk_key = self._CHUNK_KEY_FMT.format(key=key, idx=idx)
            try:
                part = self._keyring.get_password(self._service, chunk_key)
            except Exception as exc:
                logger.warning(
                    "secret_storage_chunk_read_failed",
                    backend=self.backend_name,
                    key=key,
                    chunk=idx,
                    error_type=_redact_error(exc),
                )
                return None
            if part is None:
                logger.warning(
                    "secret_storage_chunk_missing",
                    backend=self.backend_name,
                    key=key,
                    chunk=idx,
                )
                return None
            parts.append(part)
        return "".join(parts)

    def delete(self, key: str) -> bool:
        errors = getattr(self._keyring, "errors", None)
        delete_error = getattr(errors, "PasswordDeleteError", Exception)
        existed = False
        try:
            existing = self._keyring.get_password(self._service, key)
        except Exception:
            existing = None
        if existing is not None:
            existed = True
            if existing.startswith(self._CHUNK_HEADER):
                try:
                    count = int(existing[len(self._CHUNK_HEADER):])
                except ValueError:
                    count = 0
                for idx in range(count):
                    chunk_key = self._CHUNK_KEY_FMT.format(key=key, idx=idx)
                    try:
                        self._keyring.delete_password(self._service, chunk_key)
                    except delete_error:
                        pass
                    except Exception as exc:
                        logger.warning(
                            "secret_storage_chunk_delete_failed",
                            backend=self.backend_name,
                            key=key,
                            chunk=idx,
                            error_type=_redact_error(exc),
                        )
        try:
            self._keyring.delete_password(self._service, key)
            return True
        except delete_error:
            return existed
        except Exception as exc:
            logger.warning(
                "secret_storage_delete_failed",
                backend=self.backend_name,
                key=key,
                error_type=_redact_error(exc),
            )
            return False

    def exists(self, key: str) -> bool:
        return self.retrieve(key) is not None


_SHARED_SECRET_STORAGE: SecretStoragePort | None = None


def build_default_secret_storage(service: str = "ds-agent") -> SecretStoragePort:
    """Build the process-wide default secret storage backend."""
    try:
        return KeyringSecretStorage(service=service)
    except SecretStorageError as exc:
        logger.warning(
            "secret_storage_fallback_enabled",
            backend="in_memory",
            persistent=False,
            reason_type=_redact_error(exc),
        )
        return InMemorySecretStorage()


def get_shared_secret_storage() -> SecretStoragePort:
    """Return the shared secret storage instance for the current process."""
    global _SHARED_SECRET_STORAGE
    if _SHARED_SECRET_STORAGE is None:
        _SHARED_SECRET_STORAGE = build_default_secret_storage()
    return _SHARED_SECRET_STORAGE


def set_shared_secret_storage(storage: SecretStoragePort | None) -> None:
    """Override or clear the shared secret storage instance."""
    global _SHARED_SECRET_STORAGE
    _SHARED_SECRET_STORAGE = storage


_DEGRADED_MESSAGE = (
    "Secrets are kept in process memory only — the OS keyring backend is "
    "unavailable. API keys and tokens will be lost when the process exits. "
    "Install/enable a keyring backend (Windows Credential Manager, macOS "
    "Keychain, or Secret Service on Linux) to persist credentials securely."
)
_PERSISTENT_MESSAGE = "Secrets are stored in the OS secure storage backend."


def describe_secret_storage() -> dict[str, object]:
    """Return an operator-facing snapshot of the active secret storage backend.

    Used by CLI startup, support bundles, and any UI that needs to surface
    whether credentials will persist across process restarts.
    """
    storage = get_shared_secret_storage()
    persistent = bool(getattr(storage, "persistent", False))
    backend = str(getattr(storage, "backend_name", "unknown"))
    return {
        "backend": backend,
        "persistent": persistent,
        "degraded": not persistent,
        "message": _PERSISTENT_MESSAGE if persistent else _DEGRADED_MESSAGE,
    }
