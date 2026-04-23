from pathlib import Path

from ds_agent.skills.mission_pack_loader import MissionPackLoader


class TestMissionPackLoader:
    def test_loads_all_bundled_mission_packs(self):
        loader = MissionPackLoader()

        observed = {}
        for name in loader.list_packs():
            pack = loader.load(name)
            observed[name] = pack

        assert set(observed) == {
            "ab-test-analysis",
            "dashboard",
            "data_analysis",
            "general",
            "prediction",
            "reporting",
            "sql_exploration",
            "weekly-kpi-triage",
        }
        assert all(pack.authority_default is not None for pack in observed.values())
        assert all(pack.audience_default is not None for pack in observed.values())

    def test_loads_bundled_weekly_kpi_triage(self):
        loader = MissionPackLoader()

        pack = loader.load("weekly-kpi-triage")

        assert pack.name == "weekly-kpi-triage"
        assert pack.version == 1
        assert "schema_drift" in pack.required_checks
        assert "jira_create" in pack.boundary.allowed_action_classes
        assert pack.required_delivery_channels == ("jira_ticket",)
        assert pack.certification is not None
        assert pack.certification.next_target is not None
        assert pack.certification.next_target.value == "autopilot"

    def test_loads_real_onboarding_use_case_pack_names(self):
        loader = MissionPackLoader()

        assert loader.load("data_analysis").name == "data_analysis"
        assert loader.load("dashboard").name == "dashboard"
        assert loader.load("general").name == "general"
        assert loader.load("prediction").name == "prediction"
        assert loader.load("reporting").name == "reporting"
        assert loader.load("sql_exploration").name == "sql_exploration"

    def test_model_training_packs_require_a_baseline_check(self):
        loader = MissionPackLoader()

        for name in loader.list_packs():
            pack = loader.load(name)
            if not {
                "train_model",
                "model_training",
            }.intersection(pack.boundary.allowed_action_classes):
                continue
            assert any("baseline" in check.lower() for check in pack.required_checks), name

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

    def test_every_bundled_pack_has_phase4_minimum_checks(self):
        loader = MissionPackLoader()

        for name in loader.list_packs():
            pack = loader.load(name)
            assert len(pack.required_checks) >= 3, name
            assert len(pack.success_criteria) >= 3, name

    def test_reviewer_charter_docs_exist(self):
        repo_root = Path(__file__).resolve().parents[3]
        docs_root = repo_root / "Docs" / "reviewer_charters"

        assert (docs_root / "statistical_reviewer.md").is_file()
        assert (docs_root / "data_governance_reviewer.md").is_file()
        assert (docs_root / "causal_leakage_reviewer.md").is_file()
        assert (docs_root / "executive_narrative_reviewer.md").is_file()
