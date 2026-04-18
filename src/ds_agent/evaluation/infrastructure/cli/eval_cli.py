"""CLI helpers for evaluation harness commands."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console

from ds_agent.evaluation.application.dtos.eval_request_dto import EvalBatchRequest
from ds_agent.evaluation.application.use_cases.build_regression_board import (
    BuildRegressionBoard,
    FreezeRegressionBaseline,
)
from ds_agent.evaluation.application.use_cases.dispatch_regression_alerts import (
    DispatchRegressionAlerts,
)
from ds_agent.evaluation.application.use_cases.ingest_human_rubric import (
    IngestHumanRubric,
)
from ds_agent.evaluation.application.use_cases.ingest_production_trace import (
    IngestProductionTrace,
)
from ds_agent.evaluation.application.use_cases.run_eval_batch import RunEvalBatch
from ds_agent.evaluation.application.use_cases.run_shadow_comparison import (
    RunShadowComparison,
)
from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric
from ds_agent.evaluation.domain.ports.eval_orchestrator import EvalOrchestrator
from ds_agent.evaluation.infrastructure.adapters.production_task_adapter import (
    ProductionTaskAdapter,
)
from ds_agent.evaluation.infrastructure.alerting_adapter import (
    build_configured_regression_alert_notifiers,
)
from ds_agent.evaluation.infrastructure.gold_tasks.loader import GoldTaskLoader
from ds_agent.evaluation.infrastructure.ingestion.session_trace_reader import SessionTraceReader
from ds_agent.evaluation.infrastructure.orchestrator.agent_eval_orchestrator import (
    AgentEvalOrchestrator,
)
from ds_agent.evaluation.infrastructure.orchestrator.directory_eval_orchestrator import (
    DirectoryEvalOrchestrator,
)
from ds_agent.evaluation.infrastructure.persistence.json_regression_baseline_store import (
    JsonRegressionBaselineStore,
)
from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
    JsonlEvalDatasetStore,
)
from ds_agent.evaluation.infrastructure.persistence.jsonl_human_rubric_store import (
    JsonlHumanRubricStore,
)
from ds_agent.evaluation.infrastructure.persistence.jsonl_shadow_comparison_store import (
    JsonlShadowComparisonStore,
)
from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers
from ds_agent.evaluation.presentation.electron_bridge.regression_payload import (
    build_regression_board_payload,
)
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore
from ds_agent.self_improve.promotion_gate import (
    CandidateTaggedEvalOrchestrator,
    SelfImprovePromotionGate,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ds_agent.domain.interfaces.llm_provider import LLMProvider


def run_eval_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
    provider_factory: Callable[[str], LLMProvider] | None = None,
    default_model: str = "anthropic/claude-sonnet-4-6",
) -> int:
    """Run `ds-agent eval ...`."""

    parser = _build_parser(default_model)
    args = parser.parse_args(list(argv) or ["validate-suite"])
    loader = GoldTaskLoader()

    if args.command == "validate-suite":
        tasks = loader.load_suite(args.tasks_dir, domain=args.domain)
        console.print(f"Loaded {len(tasks)} gold task(s) from {Path(args.tasks_dir).resolve()}")
        return 0

    if args.command == "board":
        eval_store = _resolve_eval_store(dataset_path=args.dataset, workspace_dir=workspace_dir)
        if eval_store is None:
            console.print("workspace_dir or --dataset is required for regression board commands.")
            return 1
        baseline_store = _resolve_baseline_store(
            baseline_path=args.baseline,
            workspace_dir=workspace_dir,
        )
        if args.board_command == "freeze-baseline":
            try:
                baseline = FreezeRegressionBaseline(
                    eval_store=eval_store,
                    baseline_store=baseline_store,
                ).execute(
                    commit_sha=args.commit,
                    axis=args.axis,
                    task_catalog=loader.load_suite(args.tasks_dir),
                    mode=args.mode,
                    domain=args.domain,
                    task_id=args.task_id,
                    window_days=args.window_days,
                )
            except ValueError as exc:
                console.print(str(exc))
                return 1
            if args.output == "json":
                console.print_json(json.dumps(baseline.model_dump(mode="json"), ensure_ascii=False))
            else:
                _print_regression_baseline(console, baseline, baseline_store.path)
            return 0

        board_builder = BuildRegressionBoard(
            eval_store=eval_store,
            baseline_store=baseline_store,
        )
        tasks = loader.load_suite(args.tasks_dir)
        if args.board_command == "send-alerts":
            notifiers = build_configured_regression_alert_notifiers()
            if args.channel:
                wanted = {channel.lower() for channel in args.channel}
                notifiers = tuple(notifier for notifier in notifiers if notifier.channel in wanted)
            if not notifiers:
                console.print(
                    "No configured regression alert webhook matched the "
                    "requested channel(s)."
                )
                return 1
            dispatch_report = DispatchRegressionAlerts(
                board_builder=board_builder,
                notifiers=notifiers,
            ).execute(
                channels=args.channel,
                axis=args.axis,
                task_catalog=tasks,
                mode=args.mode,
                domain=args.domain,
                task_id=args.task_id,
                limit=args.limit,
                recent_window=args.recent_window,
                baseline_window_days=args.baseline_window_days,
            )
            if args.output == "json":
                console.print_json(
                    json.dumps(dispatch_report.model_dump(mode="json"), ensure_ascii=False)
                )
            else:
                _print_regression_alert_dispatch(console, dispatch_report)
            return 0

        snapshot = board_builder.execute(
            axis=args.axis,
            task_catalog=tasks,
            mode=args.mode,
            domain=args.domain,
            task_id=args.task_id,
            limit=args.limit,
            recent_window=args.recent_window,
            baseline_window_days=args.baseline_window_days,
        )
        if args.output == "json":
            console.print_json(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
        else:
            _print_regression_board(console, build_regression_board_payload(snapshot))
        return 0

    scorers = build_default_scorers()
    if args.command == "score-run":
        task = loader.load_file(args.task)
        run = EvalRun.model_validate_json(Path(args.run_file).read_text(encoding="utf-8"))
        report = ScoreRun(scorers).execute(run=run, task=task)
        if args.output == "json":
            console.print_json(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
        else:
            _print_score_report(console, report)
        if args.dataset_out:
            JsonlEvalDatasetStore(args.dataset_out).append(report.to_record())
        return 0

    if args.command == "ingest-session":
        if not workspace_dir:
            console.print("workspace_dir is required for production trace ingestion.")
            return 1

        eval_store = _resolve_eval_store(dataset_path=args.dataset_out, workspace_dir=workspace_dir)
        trace_reader, task, run = _load_task_and_run_for_session(
            workspace_dir=workspace_dir,
            session_id=args.session_id,
            task_id=args.task_id,
            run_id=args.run_id,
        )
        report = IngestProductionTrace(
            trace_reader=trace_reader,
            scorers=scorers,
            eval_store=eval_store,
        ).execute(
            session_id=args.session_id,
            task=task,
            task_id=args.task_id,
            run_id=args.run_id,
            run=run,
        )
        if args.output == "json":
            console.print_json(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
        else:
            _print_score_report(console, report)
        return 0

    if args.command == "ingest-human":
        if not workspace_dir:
            console.print("workspace_dir is required for human rubric ingestion.")
            return 1

        eval_store = _resolve_eval_store(dataset_path=args.dataset_out, workspace_dir=workspace_dir)
        trace_reader, task, run = _load_task_and_run_for_session(
            workspace_dir=workspace_dir,
            session_id=args.session_id,
            task_id=args.task_id,
            run_id=args.run_id,
        )
        try:
            rubric = HumanRubric(
                reviewer_id=args.reviewer_id,
                dimensions=_parse_rubric_dimensions(args.dimension),
                comment=args.comment,
            )
        except ValueError as exc:
            console.print(f"Invalid human rubric input: {exc}")
            return 1
        use_case = IngestHumanRubric(
            trace_reader=trace_reader,
            rubric_store=JsonlHumanRubricStore.for_workspace(workspace_dir),
            scorers=scorers,
            eval_store=eval_store,
        )
        try:
            report = use_case.execute(
                session_id=args.session_id,
                task=task,
                task_id=args.task_id,
                run_id=args.run_id,
                run=run,
                rubric=rubric,
            )
        except ValueError as exc:
            console.print(f"Invalid human rubric input: {exc}")
            return 1
        if args.output == "json":
            console.print_json(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
        else:
            _print_score_report(console, report)
        return 0

    if args.command == "shadow-session":
        if not workspace_dir:
            console.print("workspace_dir is required for shadow comparisons.")
            return 1
        if provider_factory is None:
            console.print("provider_factory is required for shadow comparisons.")
            return 1

        eval_store = _resolve_eval_store(dataset_path=args.dataset_out, workspace_dir=workspace_dir)
        trace_reader, task, run = _load_task_and_run_for_session(
            workspace_dir=workspace_dir,
            session_id=args.session_id,
            task_id=args.task_id,
            run_id=args.run_id,
        )
        comparison = RunShadowComparison(
            trace_reader=trace_reader,
            shadow_orchestrator=AgentEvalOrchestrator(
                workspace_dir=workspace_dir,
                provider_factory=provider_factory,
                model_name=args.model,
                run_mode="shadow",
                budget_factor=args.shadow_factor,
            ),
            scorers=scorers,
            comparison_store=JsonlShadowComparisonStore.for_workspace(workspace_dir),
            eval_store=eval_store,
            shadow_model=args.model,
            shadow_budget_factor=args.shadow_factor,
        ).execute(
            session_id=args.session_id,
            task=task,
            task_id=args.task_id,
            run_id=args.run_id,
            baseline_run=run,
        )
        if args.output == "json":
            console.print_json(json.dumps(comparison.model_dump(mode="json"), ensure_ascii=False))
        else:
            _print_shadow_comparison(console, comparison)
        return 0

    tasks = loader.load_suite(args.tasks_dir, domain=args.domain)
    eval_store = _resolve_eval_store(dataset_path=args.dataset_out, workspace_dir=workspace_dir)
    promotion_gate: SelfImprovePromotionGate | None = None
    promotion_decision: dict[str, Any] | None = None
    baseline_snapshot = None
    batch_report: Any
    candidate_id = str(args.with_candidate).strip() if args.with_candidate else None
    if candidate_id:
        if eval_store is None:
            console.print(
                "--with-candidate requires workspace_dir or --dataset-out "
                "for baseline comparison."
            )
            return 1
        promotion_gate = SelfImprovePromotionGate(
            JsonPromotionCandidateStore.for_workspace(workspace_dir)
        )
        baseline_snapshot = BuildRegressionBoard(
            eval_store=eval_store,
            baseline_store=_resolve_baseline_store(
                baseline_path=None,
                workspace_dir=workspace_dir,
            ),
        ).execute(
            task_catalog=tasks,
            axis="commit",
            mode=args.mode,
            domain=args.domain,
        )
    if args.runner == "agent":
        if not workspace_dir:
            console.print("workspace_dir is required for agent-backed eval runs.")
            return 1
        if provider_factory is None:
            console.print("provider_factory is required for --runner agent.")
            return 1
        if candidate_id and promotion_gate is not None:
            with promotion_gate.candidate_skill_hub(
                candidate_id,
                active_custom_dir=_default_active_custom_skills_dir(),
            ) as skill_hub:
                orchestrator: EvalOrchestrator = AgentEvalOrchestrator(
                    workspace_dir=workspace_dir,
                    provider_factory=provider_factory,
                    model_name=args.model,
                    run_mode=args.mode,
                    skill_hub=skill_hub,
                )
                orchestrator = CandidateTaggedEvalOrchestrator(
                    orchestrator,
                    candidate=promotion_gate.get_candidate(candidate_id),
                )
                batch_report = RunEvalBatch(
                    orchestrator=orchestrator,
                    scorers=scorers,
                    eval_store=eval_store,
                ).execute(
                    EvalBatchRequest(
                        suite_name=args.suite_name,
                        tasks=tuple(tasks),
                        mode=args.mode,
                        scorer_filters=tuple(args.scorer) if args.scorer else (),
                    )
                )
        else:
            orchestrator = AgentEvalOrchestrator(
                workspace_dir=workspace_dir,
                provider_factory=provider_factory,
                model_name=args.model,
                run_mode=args.mode,
            )
            batch_report = RunEvalBatch(
                orchestrator=orchestrator,
                scorers=scorers,
                eval_store=eval_store,
            ).execute(
                EvalBatchRequest(
                    suite_name=args.suite_name,
                    tasks=tuple(tasks),
                    mode=args.mode,
                    scorer_filters=tuple(args.scorer) if args.scorer else (),
                )
            )
    else:
        if not args.runs_dir:
            console.print("--runs-dir is required for --runner directory.")
            return 1
        directory_orchestrator: EvalOrchestrator = DirectoryEvalOrchestrator(args.runs_dir)
        if candidate_id and promotion_gate is not None:
            directory_orchestrator = CandidateTaggedEvalOrchestrator(
                directory_orchestrator,
                candidate=promotion_gate.get_candidate(candidate_id),
            )
        batch_report = RunEvalBatch(
            orchestrator=directory_orchestrator,
            scorers=scorers,
            eval_store=eval_store,
        ).execute(
            EvalBatchRequest(
                suite_name=args.suite_name,
                tasks=tuple(tasks),
                mode=args.mode,
                scorer_filters=tuple(args.scorer) if args.scorer else (),
            )
        )
    if candidate_id and promotion_gate is not None:
        promotion_decision = promotion_gate.finalize(
            candidate_id,
            report=batch_report,
            baseline_snapshot=baseline_snapshot,
            delta_threshold=float(args.delta_threshold),
            active_custom_dir=_default_active_custom_skills_dir(),
        ).model_dump(mode="json")
    if args.output == "json":
        payload: dict[str, Any]
        if promotion_decision is None:
            payload = batch_report.model_dump(mode="json")
        else:
            payload = {
                "batch": batch_report.model_dump(mode="json"),
                "candidatePromotion": promotion_decision,
            }
        console.print_json(json.dumps(payload, ensure_ascii=False))
    else:
        console.print(
            f"Batch scored {batch_report.total} task(s): passed={batch_report.passed}, "
            f"failed={batch_report.failed}"
        )
        for task_id, score in batch_report.per_task_scores.items():
            console.print(f"  {task_id}: {score:.3f}")
        if promotion_decision is not None:
            console.print(
                "Candidate promotion: "
                f"{promotion_decision['status']} - {promotion_decision['summary']}"
            )
    return 0


def _build_parser(default_model: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent eval", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-suite", add_help=False)
    validate.add_argument(
        "--tasks-dir",
        default=_default_tasks_dir(),
    )
    validate.add_argument("--domain")

    score = subparsers.add_parser("score-run", add_help=False)
    score.add_argument("--task", required=True)
    score.add_argument("--run-file", required=True)
    score.add_argument("--dataset-out")
    score.add_argument("--output", choices=["text", "json"], default="text")

    ingest = subparsers.add_parser("ingest-session", add_help=False)
    ingest.add_argument("--session-id", required=True)
    ingest.add_argument("--task-id")
    ingest.add_argument("--run-id")
    ingest.add_argument("--dataset-out")
    ingest.add_argument("--output", choices=["text", "json"], default="text")

    ingest_human = subparsers.add_parser("ingest-human", add_help=False)
    ingest_human.add_argument("--session-id", required=True)
    ingest_human.add_argument("--reviewer-id", required=True)
    ingest_human.add_argument("--task-id")
    ingest_human.add_argument("--run-id")
    ingest_human.add_argument("--dimension", action="append", required=True)
    ingest_human.add_argument("--comment")
    ingest_human.add_argument("--dataset-out")
    ingest_human.add_argument("--output", choices=["text", "json"], default="text")

    shadow = subparsers.add_parser("shadow-session", add_help=False)
    shadow.add_argument("--session-id", required=True)
    shadow.add_argument("--task-id")
    shadow.add_argument("--run-id")
    shadow.add_argument("--model", default=default_model)
    shadow.add_argument("--shadow-factor", type=float, default=0.5)
    shadow.add_argument("--dataset-out")
    shadow.add_argument("--output", choices=["text", "json"], default="text")

    board = subparsers.add_parser("board", add_help=False)
    board_subparsers = board.add_subparsers(dest="board_command", required=True)

    board_show = board_subparsers.add_parser("show", add_help=False)
    _configure_board_show_parser(board_show)

    board_snapshot = board_subparsers.add_parser("snapshot", add_help=False)
    _configure_board_show_parser(board_snapshot)

    board_send_alerts = board_subparsers.add_parser("send-alerts", add_help=False)
    _configure_board_show_parser(board_send_alerts)
    board_send_alerts.add_argument(
        "--channel",
        action="append",
        choices=["slack", "teams"],
    )

    board_freeze = board_subparsers.add_parser("freeze-baseline", add_help=False)
    board_freeze.add_argument("--dataset")
    board_freeze.add_argument("--baseline")
    board_freeze.add_argument("--tasks-dir", default=_default_tasks_dir())
    board_freeze.add_argument("--commit", required=True)
    board_freeze.add_argument("--axis", choices=["commit", "date"], default="commit")
    board_freeze.add_argument("--mode", choices=["offline", "shadow", "online"])
    board_freeze.add_argument("--domain")
    board_freeze.add_argument("--task-id")
    board_freeze.add_argument("--window-days", type=int, default=14)
    board_freeze.add_argument("--output", choices=["text", "json"], default="text")

    run = subparsers.add_parser("run", add_help=False)
    run.add_argument("--tasks-dir", default=_default_tasks_dir())
    run.add_argument("--runs-dir")
    run.add_argument("--runner", choices=["directory", "agent"], default="directory")
    run.add_argument("--model", default=default_model)
    run.add_argument("--domain")
    run.add_argument("--mode", choices=["offline", "shadow", "online"], default="offline")
    run.add_argument("--suite-name", default="gold")
    run.add_argument("--dataset-out")
    run.add_argument("--output", choices=["text", "json"], default="text")
    run.add_argument("--scorer", action="append")
    run.add_argument("--with-candidate")
    run.add_argument("--delta-threshold", type=float, default=0.03)

    return parser


def _default_tasks_dir() -> str:
    here = Path(__file__).resolve()
    return str(here.parents[1] / "gold_tasks" / "tasks")


def _default_active_custom_skills_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "skills" / "custom"


def _configure_board_show_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset")
    parser.add_argument("--baseline")
    parser.add_argument("--tasks-dir", default=_default_tasks_dir())
    parser.add_argument("--axis", choices=["commit", "date"], default="commit")
    parser.add_argument("--mode", choices=["offline", "shadow", "online"])
    parser.add_argument("--domain")
    parser.add_argument("--task-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--recent-window", type=int, default=3)
    parser.add_argument("--baseline-window-days", type=int, default=14)
    parser.add_argument("--output", choices=["text", "json"], default="text")


def _resolve_eval_store(
    *,
    dataset_path: str | None,
    workspace_dir: str | None,
) -> JsonlEvalDatasetStore | None:
    if dataset_path:
        return JsonlEvalDatasetStore(dataset_path)
    if workspace_dir:
        return JsonlEvalDatasetStore.for_workspace(workspace_dir)
    return None


def _resolve_baseline_store(
    *,
    baseline_path: str | None,
    workspace_dir: str | None,
) -> JsonRegressionBaselineStore:
    if baseline_path:
        return JsonRegressionBaselineStore(baseline_path)
    return JsonRegressionBaselineStore.for_workspace(workspace_dir)


def _load_task_and_run_for_session(
    *,
    workspace_dir: str,
    session_id: str,
    task_id: str | None,
    run_id: str | None,
) -> tuple[SessionTraceReader, GoldTask, EvalRun]:
    trace_reader = SessionTraceReader.for_workspace(workspace_dir)
    adapter = ProductionTaskAdapter()
    task_store = SqliteTaskContractStore.for_workspace(workspace_dir)
    bundle = task_store.get_bundle(task_id) if task_id else task_store.get_active_bundle(session_id)
    run = trace_reader.read_session(
        session_id=session_id,
        task_id=task_id,
        run_id=run_id,
    )
    if bundle is None:
        task = adapter.from_session(
            session_id=session_id,
            prompt=run.user_prompt,
            task_id=task_id,
        )
    else:
        task = adapter.from_bundle(bundle)
        run = adapter.enrich_run(run, bundle)
    return trace_reader, task, run


def _parse_rubric_dimensions(values: Sequence[str]) -> dict[str, float]:
    dimensions: dict[str, float] = {}
    for raw in values:
        name, separator, value_text = raw.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Invalid --dimension value: {raw!r}. Expected name=value.")
        dimensions[name.strip()] = float(value_text)
    return dimensions


def _print_score_report(console: Console, report: Any) -> None:
    console.print(
        f"Run {report.run_id} for {report.task_id}: {report.weighted_score:.3f} "
        f"({'PASS' if report.passed else 'FAIL'})"
    )
    for name, score in sorted(report.scores.items()):
        console.print(f"  {name}: {score.value:.3f} - {score.rationale}")


def _print_shadow_comparison(console: Console, comparison: Any) -> None:
    console.print(
        f"Shadow comparison {comparison.comparison_id} for {comparison.task_id}: "
        f"baseline={comparison.baseline_weighted_score:.3f}, "
        f"shadow={comparison.shadow_weighted_score:.3f}, "
        f"delta={comparison.weighted_score_delta:+.3f}"
    )
    for item in comparison.dimension_deltas[:5]:
        console.print(
            f"  {item.name}: {item.baseline_value:.3f} -> {item.shadow_value:.3f} "
            f"({item.delta:+.3f})"
        )


def _print_regression_board(console: Console, snapshot: dict[str, Any]) -> None:
    overall = snapshot.get("overall", {}) if isinstance(snapshot, dict) else {}
    recent = overall.get("recent", {}) if isinstance(overall, dict) else {}
    baseline = overall.get("baseline", {}) if isinstance(overall, dict) else {}
    baseline_source = (
        snapshot.get("baselineSource", "rolling") if isinstance(snapshot, dict) else "rolling"
    )
    console.print(
        "Regression board: "
        f"records={snapshot.get('totalRecords', 0)}, "
        f"recent score={_format_optional_metric(recent.get('avgWeightedScore'))}, "
        f"baseline score={_format_optional_metric(baseline.get('avgWeightedScore'))}, "
        f"delta={_format_signed_metric(overall.get('deltaScore'))}"
    )
    console.print(
        "  pass rate: "
        f"recent={_format_optional_percent(recent.get('passRate'))}, "
        f"baseline={_format_optional_percent(baseline.get('passRate'))}, "
        f"delta={_format_signed_percent(overall.get('deltaPassRate'))}"
    )
    console.print(f"  baseline source: {baseline_source}")
    frozen_baseline = snapshot.get("frozenBaseline") if isinstance(snapshot, dict) else None
    if isinstance(frozen_baseline, dict) and frozen_baseline:
        console.print(
            "  frozen baseline: "
            f"commit={frozen_baseline.get('commitSha')}, "
            f"score={_format_optional_metric(frozen_baseline.get('weightedScoreMean'))}, "
            f"pass_rate={_format_optional_percent(frozen_baseline.get('passRate'))}"
        )
    alerts = snapshot.get("alerts", []) if isinstance(snapshot, dict) else []
    if isinstance(alerts, list) and alerts:
        for alert in alerts[:5]:
            if not isinstance(alert, dict):
                continue
            console.print(
                f"  [{str(alert.get('severity', 'info')).upper()}] "
                f"{alert.get('message', '')}"
            )
    else:
        console.print("  alerts: none")


def _print_regression_baseline(console: Console, baseline: Any, path: Path) -> None:
    console.print(
        f"Frozen regression baseline {baseline.baseline_id} at {path}: "
        f"commit={baseline.commit_sha}, score={baseline.weighted_score_mean:.3f}, "
        f"pass_rate={baseline.pass_rate:.1%}, records={baseline.source_point_count}"
    )


def _print_regression_alert_dispatch(console: Console, report: Any) -> None:
    payload = build_regression_board_payload(report.snapshot)
    _print_regression_board(console, payload)
    console.print(
        f"  dispatched alerts: {len(report.snapshot.alerts)} across "
        f"{len(report.deliveries)} channel(s)"
    )
    for delivery in report.deliveries:
        console.print(
            f"  - {delivery.channel}: {delivery.alert_count} alert(s) -> {delivery.target}"
        )


def _format_optional_metric(value: object) -> str:
    if not isinstance(value, (float, int)):
        return "n/a"
    return f"{float(value):.3f}"


def _format_signed_metric(value: object) -> str:
    if not isinstance(value, (float, int)):
        return "n/a"
    return f"{float(value):+.3f}"


def _format_optional_percent(value: object) -> str:
    if not isinstance(value, (float, int)):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _format_signed_percent(value: object) -> str:
    if not isinstance(value, (float, int)):
        return "n/a"
    return f"{float(value) * 100:+.1f}pp"
