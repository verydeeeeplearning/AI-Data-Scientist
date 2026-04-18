"""DSAgent — the main agent loop. The heart of the system."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import structlog

from ds_agent.agent.budget_tracker import IterationBudget
from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.agent.context_manager import ContextManager
from ds_agent.agent.hooks import EmitFn, HookAction, HookContext, HookRegistry
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.interfaces.learning import PostLearningPort
from ds_agent.domain.interfaces.llm_provider import AgentCallbacks, LLMProvider
from ds_agent.domain.interfaces.session_state import (
    CheckpointStore,
    GoalStore,
    TranscriptStore,
    WorkingMemoryStore,
)
from ds_agent.domain.interfaces.tool_registry import ToolRegistry
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.runtime.tool_runtime_context import (
    ToolRuntimeContext,
    reset_tool_runtime_context,
    set_tool_runtime_context,
)
from ds_agent.runtime.verifier_shadow_runtime import (
    record_shadow_runtime_event,
    record_shadow_runtime_tool,
    reset_shadow_runtime_log,
)

# REL-04: Default timeout for LLM calls
_LLM_TIMEOUT_SECONDS = 120
_MAX_MEMORY_SUMMARY_CHARS = 240

logger = structlog.get_logger()


class DSAgent:
    """Autonomous DS Agent — single while loop, LLM is the orchestrator."""

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        budget_policy: BudgetPolicy | None = None,
        callbacks: AgentCallbacks | None = None,
        prompt_builder: PromptBuilder | None = None,
        hook_registry: HookRegistry | None = None,
        post_learner: PostLearningPort | None = None,
        mode: str = "auto",
        authority_mode: str | None = None,
        session_id: str | None = None,
        transcript_store: TranscriptStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        goal_store: GoalStore | None = None,
        working_memory_store: WorkingMemoryStore | None = None,
        approval_store: object | None = None,
        skill_hub: object | None = None,
    ) -> None:
        self._provider = provider
        self._tools = tool_registry
        policy = budget_policy or BudgetPolicy()
        self._default_budget_policy = replace(policy)
        self._budget = IterationBudget(policy=replace(policy))
        self._callbacks = callbacks or NullCallbacks()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._hooks = hook_registry or HookRegistry()
        self._post_learner = post_learner
        self._context_manager = ContextManager(provider=provider)
        self._transcript_store = transcript_store
        self._checkpoint_store = checkpoint_store
        self._goal_store = goal_store
        self._working_memory_store = working_memory_store
        self._approval_store = approval_store
        self._skill_hub = skill_hub
        self._step = 0
        self._mode = mode
        self._authority_mode = authority_mode
        self._session_id = session_id
        active_goal = (
            None
            if session_id is None or goal_store is None
            else goal_store.get_active_goal(session_id)
        )
        self._active_goal_id = None if active_goal is None else active_goal.goal_id
        self._active_goal_summary = None if active_goal is None else active_goal.summary
        self._current_run_id: str | None = None
        self._surface = "unknown"
        self._execution_mode = "interactive"
        self._turn_started_at: float | None = None
        self._history: list[ChatMessage] = self._load_initial_history()
        # Bridge sync emit for hooks → async WebSocket send
        self._emit: EmitFn = self._emit_via_callbacks

    def set_callbacks(self, callbacks: AgentCallbacks) -> None:
        """Replace callbacks for a reused session without losing sync hook emissions."""
        self._callbacks = callbacks

    def set_runtime_context(self, run_id: str | None = None, surface: str | None = None) -> None:
        """Bind runtime metadata for the next turn."""
        self._current_run_id = run_id
        if surface is not None:
            self._surface = surface

    def _emit_via_callbacks(self, event: str, payload: dict) -> None:
        emit_fn = getattr(self._callbacks, "emit_event", None)
        if callable(emit_fn):
            emit_fn(event, payload)

    async def run(
        self,
        user_message: str,
        *,
        execution_mode: str = "interactive",
        budget_policy: BudgetPolicy | None = None,
        resume_from_checkpoint: SessionCheckpoint | None = None,
    ) -> str:
        """Main agent loop — this is everything.

        LLM → tool_calls → execute → loop until done or budget exhausted.
        """
        self._start_turn(
            execution_mode=execution_mode,
            budget_policy=budget_policy,
        )
        self._restore_checkpoint(resume_from_checkpoint)
        self._emit(
            "task.started",
            {
                **self._task_event_payload(),
                "message": user_message,
                "resumedFromCheckpoint": resume_from_checkpoint is not None,
            },
        )
        self._prepare_session_state(user_message)
        messages = self._prompt_builder.build(user_message, history=self._history)
        tool_defs = self._tools.get_definitions()
        self._save_checkpoint(messages[1:])

        # --- WIRE-02: Run session init hooks (inject DS methodology rules) ---
        hook_ctx = self._build_hook_context()
        hook_ctx.user_message = user_message
        injections = await self._hooks.run_session_init(hook_ctx)
        if injections and messages:
            injection_text = "\n\n".join(injections)
            messages[0] = ChatMessage(
                role=Role.SYSTEM,
                content=(messages[0].content or "") + "\n\n" + injection_text,
            )

        while not self._budget.is_exhausted:
            self._step += 1
            self._emit(
                "task.progress",
                {
                    **self._task_event_payload(),
                    "step": self._step,
                    "maxIterations": self._budget.policy.max_iterations,
                    "costUsd": self._budget.state.total_cost_usd,
                    "maxCostUsd": self._budget.policy.max_cost_usd,
                },
            )
            await self._callbacks.on_step(self._step, f"Step {self._step}")
            await self._callbacks.on_status("thinking", f"Step {self._step}: LLM 응답 생성 중…")

            # 1. Call LLM (REL-04: with timeout; 4.2: stream deltas when supported)
            try:
                response = await asyncio.wait_for(
                    self._provider.chat(
                        messages=messages,
                        tools=tool_defs if tool_defs else None,
                        on_delta=self._callbacks.on_stream_delta,
                    ),
                    timeout=_LLM_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.error("llm_timeout", timeout=_LLM_TIMEOUT_SECONDS)
                self._emit_task_failed(
                    reason="llm_timeout",
                    detail=f"LLM call timed out after {_LLM_TIMEOUT_SECONDS}s.",
                )
                return await self._finalize_turn(
                    messages,
                    "LLM 호출이 타임아웃되었습니다. 다시 시도해주세요.",
                )
            except Exception as e:
                logger.error("llm_call_failed", error=str(e))
                self._emit_task_failed(reason="llm_error", detail=str(e))
                return await self._finalize_turn(messages, f"LLM 호출 중 오류가 발생했습니다: {e}")

            # 2. Track budget
            events = self._budget.consume(response.usage, model=response.model)
            for event in events:
                await self._callbacks.on_budget_warning(event)

            # Emit budget.detail for frontend BudgetBar (2.4 fix: correct key names)
            budget_summary = self._budget.get_summary()
            self._emit(
                "budget.detail",
                {
                    "tokensUsed": budget_summary.get("total_tokens_used", 0),
                    "tokensMax": budget_summary.get("max_total_tokens", 0),
                    "costUsd": budget_summary.get("total_cost_usd", 0.0),
                    "costMax": budget_summary.get("max_cost_usd", 0.0),
                    "iterationsUsed": budget_summary.get("iterations_used", 0),
                    "iterationsMax": budget_summary.get("max_iterations", 0),
                },
            )

            # 3. Handle thinking
            if response.thinking:
                await self._callbacks.on_thinking(response.thinking)

            # 4. If tool calls → execute and loop
            if response.tool_calls:
                # Add assistant message with tool calls
                messages.append(
                    ChatMessage(
                        role=Role.ASSISTANT,
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                tool_names = ", ".join(tc.name for tc in response.tool_calls)
                await self._callbacks.on_status("tool_executing", f"도구 실행: {tool_names}")

                hook_ctx = self._build_hook_context()

                for tc in response.tool_calls:
                    # REL-01: Each tool dispatch is isolated — one failure doesn't block others
                    try:
                        result = await self._dispatch_single_tool(tc, hook_ctx, messages)
                    except Exception as e:
                        logger.error("tool_dispatch_failed", tool=tc.name, error=str(e))
                        result = json.dumps({"error": f"Tool execution failed: {e}"})

                    messages.append(
                        ChatMessage(
                            role=Role.TOOL,
                            content=str(result),
                            tool_call_id=tc.id,
                            name=tc.name,
                        )
                    )

                # Check context compression
                token_count = await self._provider.count_tokens(messages)
                compressed = False
                if self._context_manager.should_compress(messages, current_tokens=token_count):
                    messages = await self._context_manager.compress(messages)
                    compressed = True

                # Emit context.status for frontend StatusBar/BudgetBar
                model_info = self._provider.get_model_info()
                max_ctx = getattr(model_info, "max_context_tokens", 0)
                used_pct = round((token_count / max_ctx) * 100, 1) if max_ctx else 0
                self._emit(
                    "context.status",
                    {
                        "usedPct": used_pct,
                        "currentTokens": token_count,
                        "maxTokens": max_ctx,
                        "compressed": compressed,
                    },
                )
                self._save_checkpoint(messages[1:])

                continue  # Back to LLM

            # 5. No tool calls → agent is done
            final = response.content or ""
            await self._callbacks.on_status("done", "응답 완료")
            return await self._finalize_turn(messages, final)

        # Budget exhausted
        return await self._handle_budget_exhausted(messages)

    async def _dispatch_single_tool(
        self, tc: ToolCall, hook_ctx: HookContext, messages: list[ChatMessage]
    ) -> str:
        """Execute a single tool call with pre/post hooks. Returns result string."""
        record_shadow_runtime_tool(
            self._session_id,
            self._current_run_id,
            tool_name=tc.name,
        )
        # --- PreToolUse Hook ---
        pre_result = await self._hooks.run_pre_hooks(tc.name, tc.arguments, hook_ctx)
        if pre_result.action == HookAction.DENY:
            result = f"[DENIED] {pre_result.deny_reason}"
            await self._callbacks.on_tool_end(tc.name, result, True)
            return result

        # Apply modified arguments if hook changed them
        arguments = pre_result.modified_arguments or tc.arguments

        # --- Execute Tool ---
        await self._callbacks.on_tool_start(tc.name, arguments)
        token = set_tool_runtime_context(
            ToolRuntimeContext(
                session_id=self._session_id,
                run_id=self._current_run_id,
                surface=self._surface,
                emit_event=self._emit,
                approval_store=self._approval_store,
                skill_hub=self._skill_hub,
            )
        )
        try:
            result = await self._tools.dispatch(tc.name, arguments)
        finally:
            reset_tool_runtime_context(token)
        is_error = self._is_tool_error(str(result))

        # --- PostToolUse Hook ---
        post_result = await self._hooks.run_post_hooks(
            tc.name,
            arguments,
            str(result),
            is_error,
            hook_ctx,
        )
        if post_result.modified_result is not None:
            result = post_result.modified_result

        # --- WIRE-03: Trigger learning on successful model training ---
        if post_result.trigger_learning:
            await self._trigger_post_learning(tc.name, arguments, str(result))

        await self._callbacks.on_tool_end(tc.name, str(result), is_error)

        # GAP-02: Emit file.created for tools that produce files
        if not is_error:
            self._emit_file_created_if_applicable(tc.name, arguments, str(result))

        return str(result)

    @staticmethod
    def _is_tool_error(result: str) -> bool:
        """Determine if a tool result indicates failure."""
        # 1) JSON with "error" key (standard error format)
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and "error" in parsed:
                return True
        except (json.JSONDecodeError, TypeError):
            pass
        # 2) Sandbox / permission denials
        if result.startswith("Security check failed:"):
            return True
        return result.startswith("[DENIED]")

    # Tools where we can extract exact file paths from args/result for
    # precise ``file.created`` events.
    _FILE_PRODUCING_TOOLS = frozenset(
        {
            "write_file",
            "generate_report",
            "generate_deployment",
            "notebook_generate",
            "slide_generate",
            "dashboard_spec",
        }
    )

    # Tools that may create files as a side effect (plots, trained models,
    # report assets, etc.) but don't return the path directly. We emit a
    # ``workspace.changed`` event so the frontend refreshes its file list,
    # which catches any new artifacts via a follow-up ``files.list`` RPC.
    _WORKSPACE_MUTATING_TOOLS = frozenset(
        {
            "execute_code",
            "run_eda",
            "data_loader",
            "data_profiler",
            "feature_engineer",
            "train_model",
            "evaluate_model",
        }
    )

    def _emit_file_created_if_applicable(
        self, tool_name: str, arguments: dict, result: str
    ) -> None:
        """Emit artifact-related events for tools that modify the workspace."""
        is_file_producer = tool_name in self._FILE_PRODUCING_TOOLS
        is_workspace_mutator = tool_name in self._WORKSPACE_MUTATING_TOOLS

        if not (is_file_producer or is_workspace_mutator):
            return

        self._emit("workspace.changed", {"tool": tool_name})

        if not is_file_producer:
            # The frontend will pick up new files via the refresh triggered
            # by workspace.changed; we cannot reliably parse paths from a
            # free-form sandbox result.
            return

        candidate_paths: list[str] = []
        if tool_name == "write_file":
            data = self._try_parse_json(result)
            if data.get("success") and isinstance(data.get("path"), str):
                candidate_paths.append(data["path"])
            elif isinstance(arguments.get("file_path"), str):
                candidate_paths.append(arguments["file_path"])
        elif tool_name in {
            "generate_report",
            "notebook_generate",
            "slide_generate",
            "dashboard_spec",
        } and isinstance(arguments.get("output_path"), str):
            candidate_paths.append(arguments["output_path"])

        seen: set[str] = set()
        for candidate in candidate_paths:
            normalized = candidate.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                self._emit_file_created(normalized)

    @staticmethod
    def _try_parse_json(result: str) -> dict:
        try:
            parsed = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _emit_file_created(self, file_path: str) -> None:
        try:
            path = Path(file_path).expanduser().resolve()
            if not path.exists() or not path.is_file():
                return
            self._emit(
                "file.created",
                {
                    "path": self._to_emitted_path(path),
                    "type": path.suffix.lstrip("."),
                    "size": path.stat().st_size,
                },
            )
        except OSError:
            logger.debug("file_event_detection_skipped", path=file_path)

    @staticmethod
    def _to_emitted_path(path: Path) -> str:
        from ds_agent.tools.path_utils import get_active_workspace, is_within_workspace

        workspace = get_active_workspace()
        if workspace is not None and is_within_workspace(path, workspace):
            return path.relative_to(workspace).as_posix()
        return path.as_posix()

    def _build_hook_context(self) -> HookContext:
        summary = self._budget.get_summary()
        last_user_message = None
        if self._history and self._history[-1].role == Role.USER:
            last_user_message = self._history[-1].content

        def _emit_hook_event(event: str, payload: dict[str, Any]) -> None:
            self._emit(event, payload)
            record_shadow_runtime_event(
                self._session_id,
                self._current_run_id,
                event=event,
                payload=payload,
            )

        return HookContext(
            mode=self._mode,
            authority_mode=self._authority_mode,
            session_id=self._session_id,
            run_id=self._current_run_id,
            user_message=last_user_message,
            iteration=summary["iterations_used"],
            total_cost_usd=summary["total_cost_usd"],
            environment="dev",
            approval_store=self._approval_store,
            emit=_emit_hook_event,
        )

    async def _trigger_post_learning(self, tool_name: str, arguments: dict, result: str) -> None:
        """WIRE-03 + GAP-03: Trigger post-project learning via injected PostLearningPort.

        Note: experiment.log event is emitted by ExperimentTrackerHook (post_tool_use),
        not here, to avoid duplicate emission.
        """
        try:
            if self._post_learner is not None:
                self._post_learner.learn_from_tool_result(
                    session_id=self._session_id or "unknown",
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                )
        except Exception as e:
            logger.warning("trigger_learning_failed", error=str(e))

    def _load_initial_history(self) -> list[ChatMessage]:
        if not self._session_id:
            return []

        if self._checkpoint_store is not None:
            checkpoint = self._checkpoint_store.load(self._session_id)
            if checkpoint is not None:
                self._step = max(self._step, checkpoint.step)
                return list(checkpoint.messages)

        if self._transcript_store is not None:
            return self._transcript_store.load_messages(self._session_id)

        return []

    def _save_checkpoint(self, messages: list[ChatMessage]) -> None:
        if self._checkpoint_store is None or not self._session_id:
            return

        self._checkpoint_store.save(
            SessionCheckpoint(
                session_id=self._session_id,
                step=self._step,
                messages=list(messages),
                updated_at=time.time(),
            )
        )

    def _clear_checkpoint(self) -> None:
        if self._checkpoint_store is not None and self._session_id:
            self._checkpoint_store.clear(self._session_id)

    def get_history(self, limit: int | None = None) -> list[ChatMessage]:
        """Return in-memory history for the current session."""
        if limit is None:
            return list(self._history)
        return self._history[-limit:]

    def _restore_checkpoint(self, checkpoint: SessionCheckpoint | None) -> None:
        if checkpoint is None:
            return
        if self._session_id is not None and checkpoint.session_id != self._session_id:
            raise ValueError(
                "resume_from_checkpoint session does not match the bound agent session"
            )
        self._session_id = self._session_id or checkpoint.session_id
        self._history = list(checkpoint.messages)
        self._step = max(self._step, checkpoint.step)

    def _task_event_payload(self) -> dict[str, object]:
        return {
            "sessionId": self._session_id,
            "runId": self._current_run_id,
            "surface": self._surface,
            "executionMode": self._execution_mode,
        }

    def _emit_task_failed(self, *, reason: str, detail: str) -> None:
        self._emit(
            "task.failed",
            {
                **self._task_event_payload(),
                "reason": reason,
                "detail": detail,
                "costUsd": self._budget.state.total_cost_usd,
                "iterations": self._budget.state.iterations_used,
                "maxCostUsd": self._budget.policy.max_cost_usd,
            },
        )

    async def _finalize_turn(self, messages: list[ChatMessage], final: str) -> str:
        hook_ctx = self._build_hook_context()
        final_result = await self._hooks.run_final_response_hooks(final, hook_ctx)
        if final_result.modified_response is not None:
            final = final_result.modified_response
        self._history = list(messages[1:])  # Keep history minus system prompt
        self._history.append(ChatMessage(role=Role.ASSISTANT, content=final))
        if self._transcript_store is not None and self._session_id:
            self._transcript_store.replace_messages(self._session_id, self._history)
        self._record_session_outcome(final)
        self._emit(
            "task.completed",
            {
                "sessionId": self._session_id,
                "runId": self._current_run_id,
                "surface": self._surface,
                "executionMode": self._execution_mode,
                "status": _classify_goal_status(final).value,
                "costUsd": self._budget.state.total_cost_usd,
                "iterations": self._budget.state.iterations_used,
                "maxCostUsd": self._budget.policy.max_cost_usd,
            },
        )
        self._clear_checkpoint()
        self._current_run_id = None
        return final

    async def _handle_budget_exhausted(self, messages: list[ChatMessage]) -> str:
        summary = self._budget.get_summary()
        final = (
            f"Budget exhausted after {summary['iterations_used']} iterations. "
            f"Total cost: ${summary['total_cost_usd']:.4f}"
        )
        self._emit_task_failed(reason="budget_exhausted", detail=final)
        return await self._finalize_turn(messages, final)

    def _prepare_session_state(self, user_message: str) -> None:
        self._turn_started_at = time.time()
        if not self._session_id or self._goal_store is None:
            return

        goal = self._goal_store.ensure_from_message(
            self._session_id,
            user_message,
            run_id=self._current_run_id,
        )
        self._active_goal_id = goal.goal_id
        self._active_goal_summary = goal.summary
        self._goal_store.mark_status(
            self._session_id,
            goal.goal_id,
            GoalStatus.IN_PROGRESS,
            run_id=self._current_run_id,
            note=_summarize_text(user_message),
        )

        if self._working_memory_store is None:
            return
        previous_memory = self._working_memory_store.load(self._session_id)

        self._working_memory_store.save(
            SessionWorkingMemory(
                session_id=self._session_id,
                active_goal_id=goal.goal_id,
                last_run_id=self._current_run_id,
                last_user_message=user_message,
                current_summary=f"Working on goal: {goal.summary}",
                next_step="Determine the next concrete analysis action for the active goal.",
                pending_questions=[],
                last_reflection=(
                    "" if previous_memory is None else previous_memory.last_reflection
                ),
                recovery_note=None,
                updated_at=time.time(),
            )
        )

    def _record_session_outcome(self, final: str) -> None:
        if not self._session_id:
            return

        summary = _summarize_text(final, limit=_MAX_MEMORY_SUMMARY_CHARS)
        status = _classify_goal_status(final)
        pending_questions = _extract_pending_questions(final)
        next_step = _next_step_for_status(status)
        reflection = _build_reflection(status, summary, pending_questions, next_step)
        blocked_reason = pending_questions[0] if pending_questions else None

        if self._goal_store is not None and self._active_goal_id is not None:
            self._goal_store.mark_status(
                self._session_id,
                self._active_goal_id,
                status,
                run_id=self._current_run_id,
                note=summary,
                blocked_reason=blocked_reason,
            )
            if status in {GoalStatus.COMPLETED, GoalStatus.CANCELLED}:
                self._active_goal_id = None

        if self._working_memory_store is None:
            return

        last_user_message = None
        for message in reversed(self._history):
            if message.role == Role.USER:
                last_user_message = message.content
                break

        self._working_memory_store.save(
            SessionWorkingMemory(
                session_id=self._session_id,
                active_goal_id=self._active_goal_id,
                last_run_id=self._current_run_id,
                last_user_message=last_user_message,
                current_summary=summary,
                next_step=next_step,
                pending_questions=pending_questions,
                last_reflection=reflection,
                recovery_note=None,
                updated_at=time.time(),
            )
        )

        if self._post_learner is not None:
            budget_summary = self._budget.get_summary()
            duration_seconds = 0.0
            if self._turn_started_at is not None:
                duration_seconds = max(time.time() - self._turn_started_at, 0.0)
            model_name = ""
            try:
                model_name = self._provider.get_model_info().model_id
            except Exception:
                model_name = "unknown"
            self._post_learner.learn_from_session_outcome(
                self._session_id,
                {
                    "final_output": final,
                    "goal_summary": self._active_goal_summary,
                    "goal_status": status.value,
                    "blocked_reason": blocked_reason,
                    "pending_questions": pending_questions,
                    "current_summary": summary,
                    "next_step": next_step,
                    "reflection": reflection,
                    "model_name": model_name,
                    "total_cost_usd": budget_summary.get("total_cost_usd", 0.0),
                    "duration_seconds": duration_seconds,
                    "iterations": budget_summary.get("iterations_used", 0),
                },
            )

    def _start_turn(
        self,
        *,
        execution_mode: str,
        budget_policy: BudgetPolicy | None,
    ) -> None:
        self._execution_mode = execution_mode
        reset_shadow_runtime_log(self._session_id, self._current_run_id)
        effective_policy = (
            replace(budget_policy)
            if budget_policy is not None
            else replace(self._default_budget_policy)
        )
        state = self._budget.state
        has_preloaded_budget = state.iterations_used == 0 and (
            state.total_tokens_used > 0 or state.total_cost_usd > 0 or state.wall_time_elapsed > 0
        )
        if has_preloaded_budget:
            # Preserve externally seeded carry-over budget on the first run.
            # Completed runs still reset normally because iterations_used > 0.
            self._budget.policy = effective_policy
            return
        self._budget.reset(policy=effective_policy)


def _summarize_text(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _classify_goal_status(final: str) -> GoalStatus:
    normalized = final.lower()
    blocked_tokens = (
        "please provide",
        "need more information",
        "need user input",
        "which option",
        "confirm",
        "clarify",
        "choose",
        "awaiting input",
        "budget exhausted",
        "internal server error",
        "error:",
    )
    completed_tokens = (
        "analysis complete",
        "completed",
        "done.",
        "report saved",
        "finished",
        "successfully",
    )

    if "?" in final or any(token in normalized for token in blocked_tokens):
        return GoalStatus.BLOCKED
    if any(token in normalized for token in completed_tokens):
        return GoalStatus.COMPLETED
    return GoalStatus.IN_PROGRESS


def _extract_pending_questions(final: str) -> list[str]:
    pending_questions: list[str] = []
    for match in re.findall(r"[^.!?\n]*\?+", final):
        question = " ".join(match.split()).strip()
        if question:
            pending_questions.append(question)
    return pending_questions[:3]


def _next_step_for_status(status: GoalStatus) -> str:
    if status == GoalStatus.BLOCKED:
        return "Wait for user input or approval to unblock the current goal."
    if status == GoalStatus.COMPLETED:
        return "Start a follow-up goal only if the user asks for the next deliverable."
    if status == GoalStatus.CANCELLED:
        return "Hold position until the user restarts or replaces the goal."
    return "Continue the active goal using the latest intermediate result."


def _build_reflection(
    status: GoalStatus,
    summary: str,
    pending_questions: list[str],
    next_step: str,
) -> str:
    if status == GoalStatus.COMPLETED:
        return f"Completed the current goal. {summary}"
    if status == GoalStatus.BLOCKED:
        question = pending_questions[0] if pending_questions else "User input is required."
        return f"Blocked pending clarification. {question}"
    if status == GoalStatus.CANCELLED:
        return "Stopped the current goal and waiting for a replacement objective."
    return f"Still in progress. {next_step}"
