"""Tests for AuthProfileStore — OpenClaw auth-profiles pattern."""

from __future__ import annotations

import json
import time

import pytest

from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.auth.token_store import STORE_VERSION, AuthProfileStore


@pytest.fixture
def store(tmp_path):
    """Create a store with a temp file."""
    return AuthProfileStore(tmp_path / "auth_profiles.json")


@pytest.fixture
def sample_oauth_profile():
    return AuthProfile(
        type="oauth",
        provider="gemini",
        oauth=OAuthTokenSet(
            access="ya29.test-access",
            refresh="1//test-refresh",
            expires=time.time() * 1000 + 3600_000,
            provider="gemini",
            email="user@example.com",
            project_id="my-project",
        ),
        email="user@example.com",
    )


@pytest.fixture
def sample_api_key_profile():
    return AuthProfile(
        type="api_key",
        provider="anthropic",
        key="sk-ant-test-key",
    )


# -- CRUD round-trip --------------------------------------------------------


class TestSaveAndLoad:
    def test_save_and_load_oauth(self, store, sample_oauth_profile):
        store.save("google:default", sample_oauth_profile)
        loaded = store.load("google:default")

        assert loaded is not None
        assert loaded.type == "oauth"
        assert loaded.provider == "gemini"
        assert loaded.oauth is not None
        assert loaded.oauth.access == "ya29.test-access"
        assert loaded.oauth.refresh == "1//test-refresh"
        assert loaded.oauth.email == "user@example.com"

    def test_save_and_load_api_key(self, store, sample_api_key_profile):
        store.save("anthropic:default", sample_api_key_profile)
        loaded = store.load("anthropic:default")

        assert loaded is not None
        assert loaded.type == "api_key"
        assert loaded.key == "sk-ant-test-key"

    def test_load_nonexistent_returns_none(self, store):
        assert store.load("nonexistent:profile") is None

    def test_overwrite_existing(self, store, sample_oauth_profile):
        store.save("google:default", sample_oauth_profile)

        updated = AuthProfile(
            type="oauth",
            provider="gemini",
            oauth=OAuthTokenSet(
                access="ya29.new-access",
                refresh="1//new-refresh",
                expires=time.time() * 1000 + 7200_000,
                provider="gemini",
            ),
        )
        store.save("google:default", updated)
        loaded = store.load("google:default")

        assert loaded is not None
        assert loaded.oauth.access == "ya29.new-access"

    def test_save_does_not_write_plaintext_oauth_to_disk(self, store, sample_oauth_profile):
        store.save("google:default", sample_oauth_profile)

        content = store._path.read_text(encoding="utf-8")

        assert "ya29.test-access" not in content
        assert "1//test-refresh" not in content
        assert "secret_ref" in content

    def test_save_does_not_write_plaintext_api_key_to_disk(self, store, sample_api_key_profile):
        store.save("anthropic:default", sample_api_key_profile)

        content = store._path.read_text(encoding="utf-8")

        assert "sk-ant-test-key" not in content
        assert "secret_ref" in content


class TestDelete:
    def test_delete_existing(self, store, sample_oauth_profile):
        store.save("google:default", sample_oauth_profile)
        assert store.delete("google:default") is True
        assert store.load("google:default") is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete("nonexistent") is False

    def test_delete_by_provider(self, store):
        store.save("google:work", AuthProfile(type="api_key", provider="gemini", key="k1"))
        store.save("google:personal", AuthProfile(type="api_key", provider="gemini", key="k2"))
        store.save("anthropic:default", AuthProfile(type="api_key", provider="anthropic", key="k3"))

        count = store.delete_by_provider("gemini")
        assert count == 2
        assert store.load("google:work") is None
        assert store.load("google:personal") is None
        assert store.load("anthropic:default") is not None


class TestListAndQuery:
    def test_list_profiles(self, store, sample_oauth_profile, sample_api_key_profile):
        store.save("google:default", sample_oauth_profile)
        store.save("anthropic:default", sample_api_key_profile)

        profiles = store.list_profiles()
        assert len(profiles) == 2
        assert "google:default" in profiles
        assert "anthropic:default" in profiles

    def test_list_empty(self, store):
        assert store.list_profiles() == {}

    def test_load_by_provider(self, store, sample_oauth_profile):
        store.save("google:default", sample_oauth_profile)
        loaded = store.load_by_provider("gemini")
        assert loaded is not None
        assert loaded.provider == "gemini"

    def test_load_by_provider_not_found(self, store):
        assert store.load_by_provider("nonexistent") is None

    def test_has_provider(self, store, sample_oauth_profile):
        assert store.has_provider("gemini") is False
        store.save("google:default", sample_oauth_profile)
        assert store.has_provider("gemini") is True


# -- Edge cases --------------------------------------------------------------


class TestEdgeCases:
    def test_empty_store_file(self, tmp_path):
        path = tmp_path / "auth_profiles.json"
        path.write_text("", encoding="utf-8")
        store = AuthProfileStore(path)
        assert store.list_profiles() == {}

    def test_corrupted_json(self, tmp_path):
        path = tmp_path / "auth_profiles.json"
        path.write_text("{invalid json", encoding="utf-8")
        store = AuthProfileStore(path)
        assert store.list_profiles() == {}

    def test_missing_profiles_key(self, tmp_path):
        path = tmp_path / "auth_profiles.json"
        path.write_text('{"version": 1}', encoding="utf-8")
        store = AuthProfileStore(path)
        assert store.list_profiles() == {}

    def test_store_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "auth_profiles.json"
        store = AuthProfileStore(path)
        store.save("test:default", AuthProfile(type="api_key", provider="test", key="k"))
        assert path.exists()

    def test_store_version_persisted(self, store, sample_api_key_profile):
        store.save("test:default", sample_api_key_profile)
        raw = json.loads(store._path.read_text(encoding="utf-8"))
        assert raw["version"] == STORE_VERSION

    def test_legacy_plaintext_store_is_migrated(self, tmp_path):
        path = tmp_path / "auth_profiles.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": {
                        "google:default": {
                            "type": "oauth",
                            "provider": "gemini",
                            "oauth": {
                                "access": "ya29.SECRET",
                                "refresh": "1//SECRET",
                                "expires": 123456.0,
                                "provider": "gemini",
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        store = AuthProfileStore(path)

        loaded = store.load("google:default")
        migrated = path.read_text(encoding="utf-8")

        assert loaded is not None
        assert loaded.oauth is not None
        assert loaded.oauth.access == "ya29.SECRET"
        assert "ya29.SECRET" not in migrated
        assert "1//SECRET" not in migrated
        assert '"version": 2' in migrated


# -- OAuthTokenSet entity tests -----------------------------------------------


class TestOAuthTokenSet:
    def test_is_expired_false(self):
        token = OAuthTokenSet(
            access="a",
            refresh="r",
            expires=time.time() * 1000 + 3600_000,
            provider="gemini",
        )
        assert token.is_expired() is False

    def test_is_expired_true(self):
        token = OAuthTokenSet(
            access="a",
            refresh="r",
            expires=time.time() * 1000 - 1000,
            provider="gemini",
        )
        assert token.is_expired() is True

    def test_round_trip_dict(self):
        token = OAuthTokenSet(
            access="a",
            refresh="r",
            expires=123456.0,
            provider="gemini",
            email="u@test.com",
        )
        d = token.to_dict()
        restored = OAuthTokenSet.from_dict(d)
        assert restored.access == "a"
        assert restored.email == "u@test.com"

    def test_from_dict_ignores_unknown_keys(self):
        data = {"access": "a", "refresh": "r", "expires": 0, "provider": "x", "extra": True}
        token = OAuthTokenSet.from_dict(data)
        assert token.access == "a"


class TestAuthProfile:
    def test_round_trip_oauth(self, sample_oauth_profile):
        d = sample_oauth_profile.to_dict()
        restored = AuthProfile.from_dict(d)
        assert restored.type == "oauth"
        assert restored.oauth.access == "ya29.test-access"

    def test_round_trip_api_key(self, sample_api_key_profile):
        d = sample_api_key_profile.to_dict()
        restored = AuthProfile.from_dict(d)
        assert restored.type == "api_key"
        assert restored.key == "sk-ant-test-key"
