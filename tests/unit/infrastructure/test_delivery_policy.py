"""Tests for ds_agent.runtime.delivery_policy_store."""

from __future__ import annotations

from ds_agent.runtime.delivery_policy_store import (
    DeliveryPolicy,
    JsonDeliveryPolicyStore,
)


class TestDeliveryPolicyDefaults:
    def test_default_values(self) -> None:
        policy = DeliveryPolicy()
        assert policy.live_push_enabled is True
        assert policy.artifact_auto_delivery_enabled is True
        assert policy.escalation_enabled is True
        assert ".png" in policy.auto_send_extensions
        assert ".pkl" in policy.blocked_extensions


class TestJsonDeliveryPolicyStore:
    def test_get_creates_default(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        policy = store.get()
        assert policy.live_push_enabled is True

    def test_update_persists(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        policy = store.get()
        policy.digest_enabled = True
        policy.digest_interval_seconds = 600.0
        store.update(policy)

        store2 = JsonDeliveryPolicyStore(tmp_path)
        reloaded = store2.get()
        assert reloaded.digest_enabled is True
        assert reloaded.digest_interval_seconds == 600.0

    def test_should_auto_send_png(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        assert store.should_auto_send_file("report.png", 1024)

    def test_should_not_auto_send_pkl(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        assert not store.should_auto_send_file("model.pkl", 1024)

    def test_should_not_auto_send_large_file(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        assert not store.should_auto_send_file("report.png", 100 * 1024 * 1024)

    def test_should_not_auto_send_when_disabled(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        policy = store.get()
        policy.artifact_auto_delivery_enabled = False
        store.update(policy)
        assert not store.should_auto_send_file("report.png", 1024)

    def test_platform_defaults_survive_roundtrip(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        policy = store.get()
        assert policy.platform_defaults.max_auto_send_file_size_bytes == 50 * 1024 * 1024

        store2 = JsonDeliveryPolicyStore(tmp_path)
        reloaded = store2.get()
        assert reloaded.platform_defaults.max_auto_send_file_size_bytes == 50 * 1024 * 1024

    def test_resolve_prefers_tenant_override_over_default(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        policy = store.get()
        policy.artifact_auto_delivery_enabled = True
        store.update(policy)
        store.update_tenant_override(
            "tenant-alpha",
            {"artifact_auto_delivery_enabled": False},
        )

        resolved = store.resolve(tenant="tenant-alpha")

        assert resolved.artifact_auto_delivery_enabled is False
        assert store.get().artifact_auto_delivery_enabled is True

    def test_resolve_prefers_project_override_over_tenant_override(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        store.update_tenant_override(
            "tenant-alpha",
            {"artifact_auto_delivery_enabled": False},
        )
        store.update_project_override(
            "project-zeta",
            {"artifact_auto_delivery_enabled": True},
        )

        resolved = store.resolve(tenant="tenant-alpha", project="project-zeta")

        assert resolved.artifact_auto_delivery_enabled is True
