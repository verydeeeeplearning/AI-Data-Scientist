"""Integration test: verify all 8 built-in DS skills load correctly."""

from pathlib import Path

from ds_agent.skills.hub import SkillHub

BUILTIN_DIR = Path(__file__).parent.parent.parent / "src" / "ds_agent" / "skills" / "builtin"

EXPECTED_SKILLS = [
    "scoping",
    "data-profiling",
    "eda",
    "feature-engineering",
    "modeling",
    "evaluation",
    "reporting",
    "deployment",
]


class TestBuiltinSkills:
    def setup_method(self):
        self.hub = SkillHub.from_directories([BUILTIN_DIR])

    def test_all_8_skills_loaded(self):
        names = self.hub.get_skill_names()
        for expected in EXPECTED_SKILLS:
            assert expected in names, f"Missing skill: {expected}"

    def test_each_skill_has_content(self):
        for name in EXPECTED_SKILLS:
            skill = self.hub.view_skill(name)
            assert skill is not None, f"Cannot view: {name}"
            assert len(skill["content"]) > 200, f"Skill {name} content too short"

    def test_each_skill_has_metadata(self):
        for summary in self.hub.list_skills():
            assert summary["name"]
            assert summary["description"]
            assert summary["category"] == "ds_methodology"
            assert len(summary["tags"]) >= 1
            assert summary["token_estimate"] > 0

    def test_search_by_methodology(self):
        results = self.hub.search_skills("", category="ds_methodology")
        assert len(results) == 8

    def test_search_eda_keyword(self):
        results = self.hub.search_skills("visualization")
        names = [r["name"] for r in results]
        assert "eda" in names

    def test_search_modeling_keyword(self):
        results = self.hub.search_skills("cross-validation")
        names = [r["name"] for r in results]
        assert "modeling" in names
