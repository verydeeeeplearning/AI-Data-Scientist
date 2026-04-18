from ds_agent.domain.value_objects.audience_persona import AudiencePersona


class TestAudiencePersona:
    def test_legacy_mode_defaults_match_phase_zero_mapping(self):
        assert AudiencePersona.from_legacy_agent_mode("auto") == AudiencePersona.PEER_DS
        assert AudiencePersona.from_legacy_agent_mode("supervised") == AudiencePersona.PEER_DS
        assert (
            AudiencePersona.from_legacy_agent_mode("step_by_step")
            == AudiencePersona.JUNIOR_MENTOR
        )

    def test_executive_profile_defaults_to_exec_brief_outputs(self):
        spec = AudiencePersona.EXECUTIVE.spec()

        assert spec.tone == "business-first and brief"
        assert spec.default_artifacts == ("exec_brief", "action_card")
        assert spec.uncertainty_style == "risk_tokens"

    def test_auditor_profile_carries_lineage_and_policy_language(self):
        spec = AudiencePersona.AUDITOR.spec()

        assert "lineage_report" in spec.default_artifacts
        assert "approval_history" in spec.default_artifacts
        assert spec.uncertainty_style == "quantified_with_policy_refs"
