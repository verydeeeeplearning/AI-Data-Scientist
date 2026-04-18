from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.agent.prompt_sections import build_audience_section, build_authority_section
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class TestPromptSections:
    def test_build_authority_section_for_delegate(self):
        section = build_authority_section(AuthorityMode.DELEGATE)

        assert "AUTHORITY MODE: Delegate" in section
        assert "low-risk, repeatable actions" in section
        assert "external communications" in section

    def test_build_audience_section_for_executive(self):
        section = build_audience_section(AudiencePersona.EXECUTIVE)

        assert "AUDIENCE: Executive" in section
        assert "one-page brief" in section
        assert "SAFE / REVIEW / DANGER" in section

    def test_prompt_builder_injects_authority_and_audience_from_legacy_mode(self):
        builder = PromptBuilder(legacy_agent_mode="step_by_step")
        system = builder.build("hello")[0].content

        assert "AUTHORITY MODE: Supervised" in system
        assert "AUDIENCE: Junior Mentor" in system
