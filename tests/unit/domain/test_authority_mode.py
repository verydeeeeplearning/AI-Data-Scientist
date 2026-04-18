from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class TestAuthorityMode:
    def test_blocks_external_writes_for_shadow_and_freeze_only(self):
        assert AuthorityMode.SHADOW.blocks_external_writes is True
        assert AuthorityMode.FREEZE.blocks_external_writes is True
        assert AuthorityMode.DELEGATE.blocks_external_writes is False
        assert AuthorityMode.AUTOPILOT.blocks_external_writes is False

    def test_legacy_modes_map_to_phase_zero_authority(self):
        assert AuthorityMode.from_legacy_agent_mode("auto") == AuthorityMode.DELEGATE
        assert AuthorityMode.from_legacy_agent_mode("supervised") == AuthorityMode.SUPERVISED
        assert AuthorityMode.from_legacy_agent_mode("step_by_step") == AuthorityMode.SUPERVISED

    def test_transition_requirement_captures_upgrade_gates(self):
        assert (
            AuthorityMode.SHADOW.transition_requirement(AuthorityMode.DELEGATE).owner_approvals
            == 1
        )
        assert (
            AuthorityMode.SUPERVISED.transition_requirement(AuthorityMode.DELEGATE).owner_approvals
            == 1
        )
        assert (
            AuthorityMode.DELEGATE.transition_requirement(AuthorityMode.AUTOPILOT)
            .certification_required
            is True
        )
        assert (
            AuthorityMode.SUPERVISED.transition_requirement(AuthorityMode.INCIDENT).manual_only
            is True
        )
        assert (
            AuthorityMode.FREEZE.transition_requirement(AuthorityMode.SUPERVISED).owner_approvals
            == 1
        )
        assert (
            AuthorityMode.AUTOPILOT.transition_requirement(AuthorityMode.SHADOW).is_free is True
        )
