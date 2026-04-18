"""Auth profile metadata store with secure secret payload storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.secrets.secret_storage import (
    SecretStoragePort,
    get_shared_secret_storage,
)

logger = structlog.get_logger()

STORE_VERSION = 2
DEFAULT_STORE_PATH = "~/.ds-agent/auth_profiles.json"


class AuthProfileStore:
    """File-backed auth profile store with secure secret storage."""

    def __init__(
        self,
        path: str | Path | None = None,
        secrets: SecretStoragePort | None = None,
    ) -> None:
        self._path = Path(path or DEFAULT_STORE_PATH).expanduser().resolve()
        self._secrets = secrets or get_shared_secret_storage()

    def save(self, profile_id: str, profile: AuthProfile) -> None:
        """Save or update an auth profile."""
        store = self._read_store()
        store["profiles"][profile_id] = self._serialize_profile(profile_id, profile)
        self._write_store(store)
        logger.info("auth_profile_saved", profile_id=profile_id, provider=profile.provider)

    def load(self, profile_id: str) -> AuthProfile | None:
        """Load an auth profile by ID. Returns None if not found."""
        store = self._read_store()
        data = store["profiles"].get(profile_id)
        if data is None:
            return None
        return self._hydrate_profile(profile_id, data)

    def load_by_provider(self, provider: str) -> AuthProfile | None:
        """Load the first profile matching a provider name."""
        store = self._read_store()
        for profile_id, data in store["profiles"].items():
            if data.get("provider") == provider:
                profile = self._hydrate_profile(profile_id, data)
                if profile is not None:
                    return profile
        return None

    def delete(self, profile_id: str) -> bool:
        """Delete a profile. Returns True if it existed."""
        store = self._read_store()
        record = store["profiles"].get(profile_id)
        if record is None:
            return False
        secret_ref = record.get("secret_ref")
        if isinstance(secret_ref, str):
            self._secrets.delete(secret_ref)
        del store["profiles"][profile_id]
        self._write_store(store)
        logger.info("auth_profile_deleted", profile_id=profile_id)
        return True

    def delete_by_provider(self, provider: str) -> int:
        """Delete all profiles for a provider. Returns count deleted."""
        store = self._read_store()
        to_delete = [
            pid for pid, data in store["profiles"].items() if data.get("provider") == provider
        ]
        for pid in to_delete:
            secret_ref = store["profiles"][pid].get("secret_ref")
            if isinstance(secret_ref, str):
                self._secrets.delete(secret_ref)
            del store["profiles"][pid]
        if to_delete:
            self._write_store(store)
            logger.info("auth_profiles_deleted", provider=provider, count=len(to_delete))
        return len(to_delete)

    def list_profiles(self) -> dict[str, AuthProfile]:
        """Return all profiles as {profile_id: AuthProfile}."""
        store = self._read_store()
        hydrated: dict[str, AuthProfile] = {}
        for profile_id, data in store["profiles"].items():
            profile = self._hydrate_profile(profile_id, data)
            if profile is not None:
                hydrated[profile_id] = profile
        return hydrated

    def has_provider(self, provider: str) -> bool:
        """Check if any usable profile exists for the given provider."""
        return self.load_by_provider(provider) is not None

    def _read_store(self) -> dict[str, Any]:
        """Read store from disk, returning empty store if missing/corrupted."""
        if not self._path.exists():
            return {"version": STORE_VERSION, "profiles": {}}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict) or "profiles" not in data:
                logger.warning("auth_store_invalid", path=str(self._path))
                return {"version": STORE_VERSION, "profiles": {}}
            if self._migrate_store_if_needed(data):
                self._write_store(data)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("auth_store_read_error", path=str(self._path), error=str(exc))
            return {"version": STORE_VERSION, "profiles": {}}

    def _write_store(self, store: dict[str, Any]) -> None:
        """Write store metadata to disk, creating parent directories if needed."""
        store["version"] = STORE_VERSION
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(store, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _serialize_profile(self, profile_id: str, profile: AuthProfile) -> dict[str, Any]:
        secret_ref = self._secret_ref(profile_id, profile.type)
        record: dict[str, Any] = {
            "type": profile.type,
            "provider": profile.provider,
            "secret_ref": secret_ref,
        }
        if profile.email is not None:
            record["email"] = profile.email
        if profile.display_name is not None:
            record["display_name"] = profile.display_name
        if profile.metadata:
            record["metadata"] = dict(profile.metadata)

        if profile.type == "oauth":
            if profile.oauth is None:
                raise ValueError("oauth profile requires OAuthTokenSet")
            self._secrets.store(secret_ref, json.dumps(profile.oauth.to_dict(), ensure_ascii=False))
        elif profile.type == "api_key":
            if profile.key is None:
                raise ValueError("api_key profile requires key")
            self._secrets.store(secret_ref, profile.key)
        elif profile.type == "token":
            if profile.token is None:
                raise ValueError("token profile requires token")
            token_payload: dict[str, Any] = {"token": profile.token}
            if profile.token_expires is not None:
                token_payload["token_expires"] = profile.token_expires
                record["token_expires"] = profile.token_expires
            self._secrets.store(secret_ref, json.dumps(token_payload, ensure_ascii=False))
        else:
            raise ValueError(f"Unsupported auth profile type: {profile.type}")
        return record

    def _hydrate_profile(self, profile_id: str, data: dict[str, Any]) -> AuthProfile | None:
        secret_ref = data.get("secret_ref")
        if isinstance(secret_ref, str):
            secret_value = self._secrets.retrieve(secret_ref)
            if secret_value is None:
                logger.warning(
                    "auth_profile_secret_missing",
                    profile_id=profile_id,
                    provider=data.get("provider"),
                )
                return None
            return self._hydrate_secure_profile(data, secret_value)
        return AuthProfile.from_dict(data)

    def _hydrate_secure_profile(self, data: dict[str, Any], secret_value: str) -> AuthProfile:
        profile_type = data["type"]
        provider = data["provider"]
        common_kwargs = {
            "email": data.get("email"),
            "display_name": data.get("display_name"),
            "metadata": data.get("metadata", {}),
        }

        if profile_type == "oauth":
            payload = json.loads(secret_value)
            oauth = OAuthTokenSet.from_dict(payload if isinstance(payload, dict) else {})
            if common_kwargs["email"] is None:
                common_kwargs["email"] = oauth.email
            return AuthProfile(type="oauth", provider=provider, oauth=oauth, **common_kwargs)

        if profile_type == "api_key":
            return AuthProfile(type="api_key", provider=provider, key=secret_value, **common_kwargs)

        if profile_type == "token":
            payload = json.loads(secret_value)
            token = payload.get("token") if isinstance(payload, dict) else None
            token_expires = (
                payload.get("token_expires")
                if isinstance(payload, dict)
                else data.get("token_expires")
            )
            return AuthProfile(
                type="token",
                provider=provider,
                token=token,
                token_expires=token_expires,
                **common_kwargs,
            )

        return AuthProfile.from_dict(data)

    def _migrate_store_if_needed(self, store: dict[str, Any]) -> bool:
        if int(store.get("version", 1)) >= STORE_VERSION:
            return False

        migrated = False
        profiles = store.get("profiles")
        if not isinstance(profiles, dict):
            store["profiles"] = {}
            store["version"] = STORE_VERSION
            return True

        for profile_id, record in profiles.items():
            if not isinstance(record, dict) or "secret_ref" in record:
                continue

            profile_type = str(record.get("type", ""))
            if profile_type == "oauth" and isinstance(record.get("oauth"), dict):
                secret_ref = self._secret_ref(profile_id, "oauth")
                self._secrets.store(secret_ref, json.dumps(record["oauth"], ensure_ascii=False))
                record.pop("oauth", None)
                record["secret_ref"] = secret_ref
                migrated = True
                continue

            if profile_type == "api_key" and isinstance(record.get("key"), str):
                secret_ref = self._secret_ref(profile_id, "api_key")
                self._secrets.store(secret_ref, record["key"])
                record.pop("key", None)
                record["secret_ref"] = secret_ref
                migrated = True
                continue

            if profile_type == "token" and isinstance(record.get("token"), str):
                secret_ref = self._secret_ref(profile_id, "token")
                payload: dict[str, Any] = {"token": record["token"]}
                if record.get("token_expires") is not None:
                    payload["token_expires"] = record["token_expires"]
                self._secrets.store(secret_ref, json.dumps(payload, ensure_ascii=False))
                record.pop("token", None)
                record["secret_ref"] = secret_ref
                migrated = True

        if migrated:
            logger.info(
                "auth_store_migrated_to_secure_storage",
                path=str(self._path),
                version=STORE_VERSION,
            )
        store["version"] = STORE_VERSION
        return migrated

    @staticmethod
    def _secret_ref(profile_id: str, profile_type: str) -> str:
        return f"{profile_type}:{profile_id}"
