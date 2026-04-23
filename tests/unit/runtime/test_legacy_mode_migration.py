from ds_agent.runtime.legacy_mode_migration import build_legacy_mode_migration_preview


class TestLegacyModeMigrationPreview:
    def test_auto_maps_cleanly_to_delegate_and_peer_ds(self):
        preview = build_legacy_mode_migration_preview("auto")

        assert preview.legacy_mode == "auto"
        assert preview.authority.value == "delegate"
        assert preview.audience.value == "peer_ds"
        assert preview.exact_match is True
        assert any("mission pack" in note.lower() for note in preview.notes)

    def test_step_by_step_is_marked_as_approximate(self):
        preview = build_legacy_mode_migration_preview("step-by-step")

        assert preview.legacy_mode == "step-by-step"
        assert preview.authority.value == "supervised"
        assert preview.audience.value == "junior_mentor"
        assert preview.exact_match is False
        assert any("no exact authority-axis equivalent" in note.lower() for note in preview.notes)

    def test_none_defaults_to_auto_preview(self):
        preview = build_legacy_mode_migration_preview(None)

        assert preview.legacy_mode == "auto"
        assert preview.authority.value == "delegate"
        assert preview.audience.value == "peer_ds"
