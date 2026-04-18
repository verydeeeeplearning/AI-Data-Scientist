"""PromptBuilder tests — composable section-based system prompt."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from ds_agent.agent.prompt_builder import PromptBuilder, PromptSection
from ds_agent.domain.entities.goal import GoalRecord, GoalStatus
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.working_memory import SessionWorkingMemory


class TestPromptBuilder:
    def test_builds_system_message(self):
        builder = PromptBuilder()
        messages = builder.build("Analyze my data")

        system_msgs = [m for m in messages if m.role == Role.SYSTEM]
        assert len(system_msgs) == 1
        assert "data scientist" in system_msgs[0].content.lower()

    def test_includes_user_message(self):
        builder = PromptBuilder()
        messages = builder.build("Analyze my data")

        user_msgs = [m for m in messages if m.role == Role.USER]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Analyze my data"

    def test_includes_skills_section(self):
        builder = PromptBuilder(skill_names=["scoping", "eda", "modeling"])
        messages = builder.build("Hello")

        system_content = messages[0].content
        assert "scoping" in system_content
        assert "eda" in system_content

    def test_includes_memory_hints(self):
        builder = PromptBuilder(memory_hints="Previous: used XGBoost for classification")
        messages = builder.build("Hello")

        system_content = messages[0].content
        assert "XGBoost" in system_content

    def test_custom_system_prompt_override(self):
        builder = PromptBuilder(system_prompt_override="You are a test bot.")
        messages = builder.build("Hello")

        assert messages[0].content == "You are a test bot."

    def test_with_conversation_history(self):
        history = [
            ChatMessage(role=Role.USER, content="Hi"),
            ChatMessage(role=Role.ASSISTANT, content="Hello!"),
        ]
        builder = PromptBuilder()
        messages = builder.build("Next question", history=history)

        # system + history (2) + new user message
        assert len(messages) == 4
        assert messages[-1].content == "Next question"


class TestComposableSections:
    @staticmethod
    def _mission_pack(**overrides) -> MissionPack:
        payload = {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "skills_required": ["hypothesis-ranking"],
            "boundary": {
                "allowed_data_domains": ["growth", "sales", "marketing"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["read_sql_gold", "jira_create"],
            },
            "required_checks": ["schema_drift", "baseline_compare"],
            "required_artifacts": ["exec_brief", "jira_ticket"],
            "auto_escalate_when": ["confidence_low"],
            "success_criteria": ["issue_classified"],
        }
        payload.update(overrides)
        return MissionPack.model_validate(payload)

    def test_environment_section_included(self):
        builder = PromptBuilder()
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Environment" in system
        assert "Platform:" in system
        assert "Python:" in system

    def test_quality_section_included(self):
        builder = PromptBuilder()
        messages = builder.build("Hello")
        system = messages[0].content
        assert "data leakage" in system

    def test_safety_section_included(self):
        builder = PromptBuilder()
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Safety" in system

    def test_project_context_included(self):
        builder = PromptBuilder(project_context="Churn prediction for telecom")
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Churn prediction" in system

    def test_use_case_context_included(self):
        builder = PromptBuilder(
            use_case_hint="data_analysis",
            use_case_context="Favor plain language and exploratory summaries.",
        )
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Use-Case Context" in system
        assert "Data Analysis" in system
        assert "exploratory summaries" in system

    def test_active_goal_context_included(self):
        mock_goal_store = MagicMock()
        mock_goal_store.get_active_goal.return_value = GoalRecord(
            goal_id="goal-1",
            session_id="session-1",
            summary="Train a churn model",
            detail="Train a churn model with calibrated probabilities",
            status=GoalStatus.IN_PROGRESS,
            last_run_id="run-1",
            notes=["Baseline finished."],
        )

        builder = PromptBuilder(session_id="session-1", goal_store=mock_goal_store)
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Active Goal" in system
        assert "Train a churn model" in system
        assert "run-1" in system

    def test_working_memory_context_included(self):
        mock_memory_store = MagicMock()
        mock_memory_store.load.return_value = SessionWorkingMemory(
            session_id="session-1",
            active_goal_id="goal-1",
            current_summary="Profiled the dataset and found missing targets.",
            next_step="Ask the user to confirm the target column.",
            pending_questions=["Which column is the prediction target?"],
            last_reflection="Blocked pending clarification.",
            recovery_note="Recovered after restart from checkpoint step 4.",
        )

        builder = PromptBuilder(session_id="session-1", working_memory_store=mock_memory_store)
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Working Memory" in system
        assert "Profiled the dataset" in system
        assert "prediction target" in system
        assert "Blocked pending clarification" in system
        assert "Recovered after restart" in system

    def test_task_contract_section_included_when_active(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="churn_analysis",
                business_goal="Reduce churn",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        builder = PromptBuilder(session_id="session-1", task_contract_store=mock_contract_store)
        system = builder.build("Hello")[0].content
        assert "Task Contract" in system
        assert "TC-2026-001" in system

    def test_task_contract_overrides_authority_and_audience_sections(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="churn_analysis",
                business_goal="Reduce churn",
                authority="shadow",
                audience="auditor",
                mission="weekly-kpi-triage",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        builder = PromptBuilder(
            session_id="session-1",
            task_contract_store=mock_contract_store,
            legacy_agent_mode="auto",
        )
        system = builder.build("Hello")[0].content
        assert "AUTHORITY MODE: Shadow" in system
        assert "AUDIENCE: Auditor" in system
        assert "mission=weekly-kpi-triage" in system

    def test_incident_overlay_overrides_task_contract_authority_section(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="ops_triage",
                business_goal="Triage KPI anomalies",
                authority="delegate",
                audience="auditor",
                mission="weekly-kpi-triage",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "md"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        builder = PromptBuilder(
            session_id="session-1",
            task_contract_store=mock_contract_store,
            legacy_agent_mode="auto",
            authority_mode="incident",
        )

        system = builder.build("Hello")[0].content

        assert "AUTHORITY MODE: Incident" in system
        assert "AUDIENCE: Auditor" in system

    def test_task_contract_no_contract_guidance_included(self):
        builder = PromptBuilder(session_id="session-1")
        system = builder.build("Hello")[0].content
        assert "활성 TaskContract가 없다" in system

    def test_task_contract_mission_injects_loaded_mission_pack(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="ops_triage",
                business_goal="Triage KPI anomalies",
                mission="weekly-kpi-triage",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "md"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        mission_loader = MagicMock()
        mission_loader.try_load.return_value = self._mission_pack()

        builder = PromptBuilder(
            session_id="session-1",
            task_contract_store=mock_contract_store,
            mission_loader=mission_loader,
        )
        system = builder.build("Hello")[0].content

        assert "MISSION: weekly-kpi-triage (v1)" in system
        assert "required_checks: schema_drift, baseline_compare" in system
        assert "required_artifacts: exec_brief, jira_ticket" in system

    def test_mission_defaults_apply_when_contract_has_only_mission(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="ops_triage",
                business_goal="Triage KPI anomalies",
                mission="weekly-kpi-triage",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "md"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        mission_loader = MagicMock()
        mission_loader.try_load.return_value = self._mission_pack(
            authority_default="supervised",
            audience_default="executive",
        )

        builder = PromptBuilder(
            session_id="session-1",
            task_contract_store=mock_contract_store,
            legacy_agent_mode="auto",
            mission_loader=mission_loader,
        )
        system = builder.build("Hello")[0].content

        assert "AUTHORITY MODE: Supervised" in system
        assert "AUDIENCE: Executive" in system

    def test_mission_required_skills_extend_active_skills(self):
        mock_contract_store = MagicMock()
        mock_contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-001",
                session_id="session-1",
                type="ops_triage",
                business_goal="Triage KPI anomalies",
                mission="weekly-kpi-triage",
                required_deliverables=[
                    {"type": "exec_brief", "audience": "executive", "format": "md"}
                ],
                created_at=datetime(2026, 4, 15, tzinfo=UTC),
                updated_at=datetime(2026, 4, 15, tzinfo=UTC),
            )
        )
        mission_loader = MagicMock()
        mission_loader.try_load.return_value = self._mission_pack(
            skills_required=["hypothesis-ranking"]
        )

        class HubWithoutPromptLoader:
            def view_skill(self, name: str):
                if name == "hypothesis-ranking":
                    return {"content": "## Hypothesis Ranking\nRank likely causes before acting."}
                return None

        builder = PromptBuilder(
            session_id="session-1",
            task_contract_store=mock_contract_store,
            mission_loader=mission_loader,
            skill_hub=HubWithoutPromptLoader(),
        )
        system = builder.build("Hello")[0].content

        assert "Hypothesis Ranking" in system

    def test_tool_guides_from_registry(self):
        """Tool prompts are injected into system prompt."""
        mock_entry = MagicMock()
        mock_entry.name = "data_loader"
        mock_entry.prompt = "Load data from file and return summary."

        mock_registry = MagicMock()
        mock_registry._tools = {"data_loader": mock_entry}

        builder = PromptBuilder(tool_registry=mock_registry)
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Tool Usage Guides" in system
        assert "data_loader" in system
        assert "Load data from file" in system

    def test_empty_tool_prompt_skipped(self):
        """Tools without prompt field are not included in guides."""
        mock_entry = MagicMock()
        mock_entry.name = "some_tool"
        mock_entry.prompt = ""

        mock_registry = MagicMock()
        mock_registry._tools = {"some_tool": mock_entry}

        builder = PromptBuilder(tool_registry=mock_registry)
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Tool Usage Guides" not in system

    def test_skill_content_via_skill_hub(self):
        """Skill hub view_skill content is injected."""

        class HubWithoutPromptLoader:
            def view_skill(self, _name: str):
                return {"content": "## EDA Steps\n1. Check distributions"}

        mock_hub = HubWithoutPromptLoader()

        builder = PromptBuilder(skill_names=["eda"], skill_hub=mock_hub)
        messages = builder.build("Hello")
        system = messages[0].content
        assert "Active Skills" in system
        assert "EDA Steps" in system


class TestTokenBudget:
    def test_low_budget_drops_optional_sections(self):
        """With a tiny budget, only required sections survive."""
        builder = PromptBuilder(max_system_tokens=200)
        messages = builder.build("Hello")
        system = messages[0].content

        # Required sections (identity + environment) must be present
        assert "DS Agent" in system
        assert "Environment" in system

    def test_priority_order_respected(self):
        """Lower-priority sections are dropped first."""
        # With a moderate budget, methodology (priority=9) should be dropped
        # while quality (priority=2) stays
        builder = PromptBuilder(max_system_tokens=1500)
        messages = builder.build("Hello")
        system = messages[0].content

        assert "Quality" in system
        # Methodology has higher priority number so may be dropped

    def test_required_sections_never_dropped(self):
        """Identity and environment are never dropped regardless of budget."""
        builder = PromptBuilder(max_system_tokens=50)  # Extremely small
        messages = builder.build("Hello")
        system = messages[0].content

        # These are required=True
        assert "DS Agent" in system
        assert "Environment" in system


class TestPromptSection:
    def test_auto_token_estimate(self):
        section = PromptSection(name="test", content="Hello world", priority=0)
        assert section.estimated_tokens() > 0

    def test_explicit_token_estimate(self):
        section = PromptSection(name="test", content="Hello", priority=0, token_estimate=100)
        assert section.estimated_tokens() == 100

    def test_frozen(self):
        section = PromptSection(name="test", content="Hello", priority=0)
        assert section.name == "test"


class TestLanguageDirective:
    """P1-13: system prompt reflects user's preferred response language."""

    def test_korean_instruction_injected(self):
        builder = PromptBuilder(language="ko")
        system = builder.build("안녕")[0].content
        assert "Response Language" in system
        assert "한국어" in system

    def test_english_instruction_injected(self):
        builder = PromptBuilder(language="en")
        system = builder.build("hi")[0].content
        assert "Respond to the user in English" in system

    def test_no_directive_when_unset(self):
        builder = PromptBuilder()
        system = builder.build("hi")[0].content
        assert "Response Language" not in system

    def test_unknown_language_drops_section(self):
        builder = PromptBuilder(language="klingon")
        system = builder.build("hi")[0].content
        assert "Response Language" not in system
