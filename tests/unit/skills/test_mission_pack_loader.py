from ds_agent.skills.mission_pack_loader import MissionPackLoader


class TestMissionPackLoader:
    def test_loads_bundled_weekly_kpi_triage(self):
        loader = MissionPackLoader()

        pack = loader.load("weekly-kpi-triage")

        assert pack.name == "weekly-kpi-triage"
        assert pack.version == 1
        assert "schema_drift" in pack.required_checks
        assert "jira_create" in pack.boundary.allowed_action_classes
        assert pack.certification is not None
        assert pack.certification.next_target is not None
        assert pack.certification.next_target.value == "autopilot"

    def test_rejects_invalid_name(self):
        loader = MissionPackLoader()

        try:
            loader.load("../secrets")
        except ValueError as exc:
            assert "Invalid mission pack name" in str(exc)
        else:
            raise AssertionError("Expected invalid mission pack name to be rejected")

    def test_invalid_yaml_raises_value_error(self, tmp_path):
        (tmp_path / "broken.yaml").write_text("[]\n", encoding="utf-8")
        loader = MissionPackLoader(tmp_path)

        try:
            loader.load("broken")
        except ValueError as exc:
            assert "must contain a mapping" in str(exc)
        else:
            raise AssertionError("Expected invalid mission YAML to fail")
