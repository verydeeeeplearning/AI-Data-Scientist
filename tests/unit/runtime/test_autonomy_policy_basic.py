from datetime import UTC, datetime

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.autonomy_policy import AutonomyPolicy


class TestAutonomyPolicyBasic:
    class _CertificationStore:
        def __init__(self, certified: bool) -> None:
            self._certified = certified

        def is_certified(
            self,
            mission_name: str,
            level: AuthorityMode | str,
            *,
            mission_version: int | None = None,
        ) -> bool:
            return self._certified

    @staticmethod
    def _mission_pack(**overrides) -> MissionPack:
        payload = {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "boundary": {
                "allowed_data_domains": ["growth", "sales", "marketing"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["jira_create", "artifact_draft"],
            },
            "required_checks": ["schema_drift"],
            "required_artifacts": ["exec_brief"],
            "success_criteria": ["issue_classified"],
            "action_policy_overrides": {"jira_create": {"delegate": "auto"}},
            "certification": {
                "current_level": "delegate",
                "next_target": "autopilot",
                "autopilot_requirements": {
                    "shadow_runs_passed": 10,
                    "critical_violations": 0,
                    "verifier_avg_score": 0.85,
                    "rollback_rehearsal": "passed",
                    "owner_approvals": 2,
                },
            },
        }
        payload.update(overrides)
        return MissionPack.model_validate(payload)

    @staticmethod
    def _review_verdict(**overrides) -> ReviewVerdict:
        payload = {
            "verdict_id": "RV-20260421001",
            "task_id": "TC-2026-001",
            "result": "warn",
            "summary": "Verifier needs operator follow-up.",
            "created_at": datetime(2026, 4, 21, tzinfo=UTC),
        }
        payload.update(overrides)
        return ReviewVerdict.model_validate(payload)

    def test_auto_legacy_mode_maps_to_delegate_and_peer_ds(self):
        decision = AutonomyPolicy().evaluate(action_is_safe=False, legacy_mode="auto")

        assert decision.context.authority == AuthorityMode.DELEGATE
        assert decision.context.audience == AudiencePersona.PEER_DS
        assert decision.requires_approval is False
        assert decision.blocked is False

    def test_supervised_legacy_requires_approval_for_non_safe_action(self):
        decision = AutonomyPolicy().evaluate(action_is_safe=False, legacy_mode="supervised")

        assert decision.context.authority == AuthorityMode.SUPERVISED
        assert decision.context.audience == AudiencePersona.PEER_DS
        assert decision.requires_approval is True
        assert decision.reason == "supervised_requires_approval_for_non_safe_actions"

    def test_step_by_step_legacy_requires_approval_even_for_safe_action(self):
        decision = AutonomyPolicy().evaluate(action_is_safe=True, legacy_mode="step_by_step")

        assert decision.context.authority == AuthorityMode.SUPERVISED
        assert decision.context.audience == AudiencePersona.JUNIOR_MENTOR
        assert decision.requires_approval is True
        assert decision.reason == "legacy_step_by_step_requires_approval"

    def test_shadow_blocks_non_safe_actions(self):
        decision = AutonomyPolicy().evaluate(action_is_safe=False, authority="shadow")

        assert decision.context.authority == AuthorityMode.SHADOW
        assert decision.blocked is True
        assert decision.requires_approval is False

    def test_explicit_axis_override_wins_over_legacy_mapping(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            legacy_mode="auto",
            authority="supervised",
            audience="auditor",
        )

        assert decision.context.authority == AuthorityMode.SUPERVISED
        assert decision.context.audience == AudiencePersona.AUDITOR
        assert decision.requires_approval is True

    def test_action_matrix_verdict_can_require_dual_style_approval(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="delegate",
            action_class="prod_deploy",
        )

        assert decision.context.authority == AuthorityMode.DELEGATE
        assert decision.requires_approval is True
        assert decision.reason == "action_matrix_dual"

    def test_action_matrix_skip_blocks_action(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="freeze",
            action_class="jira_create",
        )

        assert decision.blocked is True
        assert decision.reason == "action_matrix_skip"

    def test_freeze_overlay_blocks_local_writes_even_when_matrix_allows(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="freeze",
            action_class="artifact_draft",
        )

        assert decision.blocked is True
        assert decision.reason == "freeze_mode_blocks_writes"

    def test_mission_override_can_auto_allow_delegate_jira(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            legacy_mode="auto",
            action_class="jira_create",
            mission_pack=self._mission_pack(),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.context.authority == AuthorityMode.DELEGATE
        assert decision.requires_approval is False
        assert decision.reason == "mission_override_auto"

    def test_out_of_boundary_action_requires_approval(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            legacy_mode="auto",
            action_class="prod_deploy",
            mission_pack=self._mission_pack(),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.requires_approval is True
        assert decision.blocked is False
        assert decision.reason == "mission_boundary_out_of_scope"

    def test_mission_default_authority_and_audience_fill_missing_axes(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            action_class="jira_create",
            mission_pack=self._mission_pack(
                authority_default="supervised",
                audience_default="executive",
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["jira_create"],
                },
            ),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.context.authority == AuthorityMode.SUPERVISED
        assert decision.context.audience == AudiencePersona.EXECUTIVE
        assert decision.requires_approval is True

    def test_autopilot_requires_certification_before_auto_execution(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=True,
            authority="autopilot",
            action_class="artifact_draft",
            mission_pack=self._mission_pack(),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.context.authority == AuthorityMode.AUTOPILOT
        assert decision.requires_approval is True
        assert decision.reason == "missing_certification"

    def test_autopilot_allows_action_when_store_confirms_certification(self):
        decision = AutonomyPolicy(
            certification_store=self._CertificationStore(certified=True)
        ).evaluate(
            action_is_safe=True,
            authority="autopilot",
            action_class="artifact_draft",
            mission_pack=self._mission_pack(),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.context.authority == AuthorityMode.AUTOPILOT
        assert decision.requires_approval is False
        assert decision.reason == "action_matrix_auto"

    def test_incident_keeps_irreversible_email_send_on_approval_path(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="incident",
            action_class="email_send",
        )

        assert decision.context.authority == AuthorityMode.INCIDENT
        assert decision.requires_approval is True
        assert decision.reason == "incident_still_requires_approval_for_irreversible"

    def test_direct_mission_auto_escalation_signal_requires_approval_for_write_action(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="delegate",
            action_class="artifact_draft",
            mission_pack=self._mission_pack(
                auto_escalate_when=["confidence_low"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["artifact_draft"],
                },
            ),
            action_arguments={
                "data_domain": "growth",
                "mission_auto_escalation_signals": ["confidence_low"],
            },
        )

        assert decision.requires_approval is True
        assert decision.reason == "mission_auto_escalation_triggered"
        assert decision.escalation_signals == ("confidence_low",)

    def test_low_confidence_verdict_triggers_mission_auto_escalation(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="delegate",
            action_class="artifact_draft",
            mission_pack=self._mission_pack(
                auto_escalate_when=["confidence_low"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["artifact_draft"],
                },
            ),
            action_arguments={"data_domain": "growth"},
            latest_review_verdict=self._review_verdict(
                confidence={
                    "score": 0.2,
                    "grade": "low",
                    "rationale": "Confidence dropped below the mission threshold.",
                }
            ),
        )

        assert decision.requires_approval is True
        assert decision.reason == "mission_auto_escalation_triggered"
        assert decision.escalation_signals == ("confidence_low",)

    def test_failed_required_check_maps_to_baseline_not_beaten_signal(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="delegate",
            action_class="artifact_draft",
            mission_pack=self._mission_pack(
                auto_escalate_when=["baseline_not_beaten"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["artifact_draft"],
                },
            ),
            action_arguments={"data_domain": "growth"},
            latest_review_verdict=self._review_verdict(
                metadata={"mission_required_check_failures": ["baseline_compare"]}
            ),
        )

        assert decision.requires_approval is True
        assert decision.reason == "mission_auto_escalation_triggered"
        assert decision.escalation_signals == ("baseline_not_beaten",)

    def test_deployment_actions_map_to_deployment_requested_signal(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=False,
            authority="delegate",
            action_class="prod_deploy",
            mission_pack=self._mission_pack(
                auto_escalate_when=["deployment_requested"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["prod_deploy"],
                },
            ),
            action_arguments={"data_domain": "growth"},
        )

        assert decision.requires_approval is True
        assert decision.reason == "mission_auto_escalation_triggered"
        assert decision.escalation_signals == ("deployment_requested",)

    def test_safe_read_only_coordination_stays_open_during_auto_escalation(self):
        decision = AutonomyPolicy().evaluate(
            action_is_safe=True,
            authority="delegate",
            action_class="read_sql_gold",
            mission_pack=self._mission_pack(
                auto_escalate_when=["confidence_low"],
                action_policy_overrides={},
                boundary={
                    "allowed_data_domains": ["growth"],
                    "required_semantic_metrics": [],
                    "allowed_action_classes": ["read_sql_gold"],
                },
            ),
            action_arguments={
                "data_domain": "growth",
                "mission_auto_escalation_signals": ["confidence_low"],
            },
        )

        assert decision.requires_approval is False
        assert decision.blocked is False
        assert decision.reason == "action_matrix_auto"
