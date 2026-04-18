"""SkillHub tests: list, view, search skills."""

from ds_agent.skills.hub import SkillEntry, SkillHub


def _make_test_skills() -> dict[str, SkillEntry]:
    return {
        "scoping": SkillEntry(
            name="scoping",
            description="Define ML problem scope and success criteria",
            category="ds_methodology",
            tags=["problem-definition", "requirements", "scope"],
            content="# Scoping\n\nFull content here...",
            token_estimate=500,
        ),
        "eda": SkillEntry(
            name="eda",
            description="Exploratory data analysis procedures and best practices",
            category="ds_methodology",
            tags=["eda", "visualization", "statistics"],
            content="# EDA\n\nFull content here...",
            token_estimate=800,
        ),
        "classification": SkillEntry(
            name="classification",
            description="Classification task type guide",
            category="task_type",
            tags=["classification", "binary", "multiclass"],
            content="# Classification\n\nGuide...",
            token_estimate=600,
        ),
    }


class TestSkillHub:
    def test_list_skills_returns_summaries(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.list_skills()
        assert len(result) == 3
        names = [s["name"] for s in result]
        assert "scoping" in names
        assert "eda" in names

    def test_list_skills_excludes_content(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.list_skills()
        for skill in result:
            assert "content" not in skill

    def test_list_skills_by_category(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.list_skills(category="ds_methodology")
        assert len(result) == 2
        names = [s["name"] for s in result]
        assert "classification" not in names

    def test_view_skill_returns_full_content(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.view_skill("scoping")
        assert result is not None
        assert "Full content here" in result["content"]
        assert result["name"] == "scoping"

    def test_view_skill_not_found(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.view_skill("nonexistent")
        assert result is None

    def test_search_skills_by_keyword(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.search_skills("eda")
        assert len(result) >= 1
        names = [s["name"] for s in result]
        assert "eda" in names

    def test_search_skills_by_tag(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.search_skills("visualization")
        assert len(result) >= 1
        names = [s["name"] for s in result]
        assert "eda" in names

    def test_search_empty_query_returns_all(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.search_skills("")
        assert len(result) == 3

    def test_search_no_match(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.search_skills("xyznonexistent")
        assert len(result) == 0

    def test_search_with_category_filter(self):
        hub = SkillHub(skills=_make_test_skills())
        result = hub.search_skills("", category="task_type")
        assert len(result) == 1
        assert result[0]["name"] == "classification"
