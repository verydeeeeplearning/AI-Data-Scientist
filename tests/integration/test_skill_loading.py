"""Integration test: loading skills from markdown files."""

from ds_agent.skills.hub import SkillHub
from ds_agent.skills.parser import parse_skill_file

SKILL_CONTENT = """\
---
name: test-skill
description: A test skill for unit testing
category: custom
tags: [test, example]
version: "1.0.0"
author: test
token_estimate: 100
---

# Test Skill

## When to Use
- When testing

## Procedure
1. Write test
2. Run test
3. Pass test
"""

MINIMAL_SKILL = """\
---
name: minimal
description: Minimal skill
category: custom
tags: [minimal]
---

Just content.
"""


class TestSkillParser:
    def test_parse_valid_skill(self, tmp_path):
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text(SKILL_CONTENT, encoding="utf-8")

        entry = parse_skill_file(skill_file)
        assert entry.name == "test-skill"
        assert entry.description == "A test skill for unit testing"
        assert entry.category == "custom"
        assert "test" in entry.tags
        assert "# Test Skill" in entry.content
        assert entry.token_estimate == 100

    def test_parse_minimal_skill(self, tmp_path):
        skill_file = tmp_path / "minimal.md"
        skill_file.write_text(MINIMAL_SKILL, encoding="utf-8")

        entry = parse_skill_file(skill_file)
        assert entry.name == "minimal"
        assert "Just content" in entry.content

    def test_parse_no_frontmatter(self, tmp_path):
        skill_file = tmp_path / "bad.md"
        skill_file.write_text("# No frontmatter\n\nJust text.", encoding="utf-8")

        entry = parse_skill_file(skill_file)
        assert entry is None

    def test_parse_missing_required_field(self, tmp_path):
        skill_file = tmp_path / "bad2.md"
        skill_file.write_text("---\nname: foo\n---\nContent", encoding="utf-8")

        entry = parse_skill_file(skill_file)
        # Missing description, category, tags — should return None or minimal
        assert entry is None


class TestSkillHubFromDirectory:
    def test_load_from_directory(self, tmp_path):
        # Create skill files
        (tmp_path / "skill-a.md").write_text(SKILL_CONTENT, encoding="utf-8")
        (tmp_path / "skill-b.md").write_text(MINIMAL_SKILL, encoding="utf-8")

        hub = SkillHub.from_directories([tmp_path])
        skills = hub.list_skills()
        assert len(skills) == 2

    def test_load_recursive(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.md").write_text(MINIMAL_SKILL, encoding="utf-8")

        hub = SkillHub.from_directories([tmp_path])
        skills = hub.list_skills()
        assert len(skills) == 1

    def test_empty_directory(self, tmp_path):
        hub = SkillHub.from_directories([tmp_path])
        skills = hub.list_skills()
        assert len(skills) == 0
