"""C13 Interface Parity Harness

Invokes ``ds_agent.agent.factory.create_agent`` with the exact parameter
shape used by each of the three channel entrypoints and captures the
resulting DSAgent wiring signature.

Channels modelled (from live source as of 2026-04-17):

- CLI      — ``ds_agent.cli.main._run_agent_turn``
- Telegram — ``ds_agent.gateway.telegram_runner.TelegramRunner._create_agent``
- Electron — ``ds_agent.api.agent_session_registry.AgentSessionRegistry._create_agent``

A stub LLM provider and stub callbacks are used so no external network
traffic is produced. No source file is mutated.

Output: ``channel_signatures.json`` and ``parity_diff_raw.json`` in the
harness output directory passed on the command line.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# Repo root
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

# ---- Stub collaborators -----------------------------------------------------

class StubProvider:
    """Minimal LLMProvider stand-in — no real chat call will be issued."""

    def __init__(self, model: str = "stub/claude-sonnet-test") -> None:
        self._model = model

    async def chat(self, messages, tools=None, temperature=0.0, max_tokens=None, on_delta=None, **kw):  # noqa: D401,E501
        raise RuntimeError("StubProvider.chat should never be called in parity harness")

    async def count_tokens(self, messages):
        return 0

    def get_model_info(self):
        from ds_agent.domain.entities.provider_models import ModelInfo
        try:
            return ModelInfo(
                name=self._model,
                family="stub",
                context_window=200_000,
                max_output_tokens=4096,
                input_cost_per_million=0.0,
                output_cost_per_million=0.0,
            )
        except Exception:
            # Fallback if the ModelInfo schema differs
            return ModelInfo(name=self._model)  # type: ignore[call-arg]


class StubCallbacks:
    async def on_tool_start(self, tool_name, arguments): pass
    async def on_tool_end(self, tool_name, result, is_error): pass
    async def on_thinking(self, thinking_text): pass
    async def on_stream_delta(self, delta): pass
    async def on_step(self, step_num, message): pass
    async def on_status(self, status, detail): pass
    async def on_budget_warning(self, event): pass


# ---- Signature capture ------------------------------------------------------

def _agent_signature(agent, tool_registry_cls) -> dict[str, Any]:
    """Extract structural fingerprint from a constructed DSAgent.

    Captures what matters for 3-tier parity: the hooks registered, the
    tool registry identity (shared classvar), the prompt builder's skill
    list, the budget policy, the mode / authority_mode, and whether
    transcript / checkpoint / goal / approval stores are wired.
    """
    hooks = sorted([type(h).__name__ for h in agent._hooks.hooks])
    skill_names = list(getattr(agent._prompt_builder, "_skill_names", [])) \
        or list(getattr(agent._prompt_builder, "skill_names", []))
    tool_list = sorted(tool_registry_cls.list_tools())
    budget = agent._default_budget_policy
    return {
        "hooks": hooks,
        "hook_count": len(hooks),
        "skill_names": skill_names,
        "tool_count": len(tool_list),
        "tools_hash": hashlib.sha256("|".join(tool_list).encode()).hexdigest(),
        "budget": {
            "max_iterations": budget.max_iterations,
            "max_cost_usd": budget.max_cost_usd,
        },
        "mode": agent._mode,
        "authority_mode": agent._authority_mode,
        "session_id": agent._session_id,
        "transcript_store_wired": agent._transcript_store is not None,
        "checkpoint_store_wired": agent._checkpoint_store is not None,
        "goal_store_wired": agent._goal_store is not None,
        "working_memory_store_wired": agent._working_memory_store is not None,
        "approval_store_wired": agent._approval_store is not None,
        "skill_hub_wired": agent._skill_hub is not None,
        "post_learner_wired": agent._post_learner is not None,
        "tool_registry_class": f"{tool_registry_cls.__module__}.{tool_registry_cls.__name__}",
    }


# ---- Channel-shaped factory invocations ------------------------------------

def _build_cli(workspace: str, session_id: str):
    """Mirror CLI main._run_agent_turn call-shape (lines 106-119)."""
    from ds_agent.agent.factory import create_agent
    return create_agent(
        provider=StubProvider(),
        callbacks=StubCallbacks(),
        max_iterations=100,
        max_cost_usd=10.0,
        mode="auto",
        authority_mode=None,  # CLI: _current_authority_overlay → None when no overlay set
        model_name="stub/claude-sonnet-test",
        workspace_dir=workspace,
        session_id=session_id,
        transcript_store=None,
        checkpoint_store=None,
        sandbox_config=None,
    )


def _build_telegram(workspace: str, session_id: str):
    """Mirror gateway.telegram_runner.TelegramRunner._create_agent (lines 3343-3357)."""
    from ds_agent.agent.factory import create_agent
    return create_agent(
        provider=StubProvider(),
        callbacks=StubCallbacks(),
        max_iterations=100,
        max_cost_usd=10.0,
        mode="auto",
        authority_mode=None,
        model_name="stub/claude-sonnet-test",
        workspace_dir=workspace,
        session_id=session_id,
        transcript_store=None,
        checkpoint_store=None,
        approval_store=None,
        sandbox_config=None,
    )


def _build_electron(workspace: str, session_id: str):
    """Mirror api.agent_session_registry.AgentSessionRegistry._create_agent
    (lines 170-192). Electron hits the WS handler, which routes through
    AgentSessionRegistry.get_or_create → _create_agent → create_agent.
    """
    from ds_agent.agent.factory import create_agent
    return create_agent(
        provider=StubProvider(),
        callbacks=StubCallbacks(),
        max_iterations=100,
        max_cost_usd=10.0,
        mode="auto",
        model_name="stub/claude-sonnet-test",
        workspace_dir=workspace,
        session_id=session_id,
        use_case_hint=None,
        use_case_context=None,
        transcript_store=None,
        checkpoint_store=None,
        approval_store=None,
        authority_mode=None,
        connector_configs={},
        skill_hub=None,
        org_policy_supplier=None,
        sandbox_config=None,
        language=None,
    )


def _run_one(name: str, builder, workspace: str, session_id: str) -> dict[str, Any]:
    # NOTE: ToolRegistry is a process-global classvar — the first channel
    # build populates it via import_all_tools(); subsequent channels see the
    # identical registry. That is the real production behavior and exactly
    # what parity requires. We do NOT reset between runs.
    try:
        from ds_agent.tools.registry import ToolRegistry
        agent = builder(workspace, session_id)
        sig = _agent_signature(agent, ToolRegistry)
        sig["channel"] = name
        sig["session_id"] = session_id
        sig["status"] = "ok"
        return sig
    except Exception as e:  # pragma: no cover
        return {
            "channel": name,
            "session_id": session_id,
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc(),
        }


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Each scenario uses a distinct workspace + session to represent the
    # three plan scenarios. Wiring parity is scenario-agnostic (factory is
    # pure w.r.t. scenario semantics), so we still verify 3×3 = 9 runs.
    scenarios = [
        ("P-01_basic_report", "tmp_parity_p01"),
        ("P-02_authority_switch", "tmp_parity_p02"),
        ("P-03_learning_governance", "tmp_parity_p03"),
    ]
    channels = [
        ("CLI", _build_cli),
        ("Telegram", _build_telegram),
        ("Electron", _build_electron),
    ]

    all_sigs: list[dict[str, Any]] = []
    tmp_base = Path(tempfile.mkdtemp(prefix="c13_parity_"))
    for scen_id, scen_ws in scenarios:
        ws = tmp_base / scen_ws
        ws.mkdir(parents=True, exist_ok=True)
        for ch_name, ch_builder in channels:
            sid = f"{scen_id}__{ch_name}"
            sig = _run_one(ch_name, ch_builder, str(ws), sid)
            sig["scenario"] = scen_id
            all_sigs.append(sig)

    (out_dir / "channel_signatures.json").write_text(
        json.dumps(all_sigs, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Per-scenario parity diff
    diff_report: dict[str, Any] = {"scenarios": {}, "overall_parity_match": True}
    equivalence_fields = [
        "hooks", "hook_count", "skill_names", "tool_count", "tools_hash",
        "budget", "mode", "authority_mode",
        "transcript_store_wired", "checkpoint_store_wired",
        "goal_store_wired", "working_memory_store_wired",
        "approval_store_wired", "skill_hub_wired", "post_learner_wired",
        "tool_registry_class",
    ]
    for scen_id, _ in scenarios:
        scen_sigs = [s for s in all_sigs if s.get("scenario") == scen_id]
        if any(s.get("status") != "ok" for s in scen_sigs):
            diff_report["scenarios"][scen_id] = {
                "match": False,
                "reason": "one or more channel builds failed",
                "sigs": scen_sigs,
            }
            diff_report["overall_parity_match"] = False
            continue
        base = scen_sigs[0]
        scen_diff: dict[str, Any] = {"match": True, "field_mismatches": []}
        for other in scen_sigs[1:]:
            for field in equivalence_fields:
                if base.get(field) != other.get(field):
                    scen_diff["match"] = False
                    scen_diff["field_mismatches"].append({
                        "field": field,
                        base["channel"]: base.get(field),
                        other["channel"]: other.get(field),
                    })
        if not scen_diff["match"]:
            diff_report["overall_parity_match"] = False
        diff_report["scenarios"][scen_id] = scen_diff

    (out_dir / "parity_diff_raw.json").write_text(
        json.dumps(diff_report, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(json.dumps({
        "runs_completed": sum(1 for s in all_sigs if s.get("status") == "ok"),
        "runs_total": len(all_sigs),
        "parity_match": diff_report["overall_parity_match"],
        "out_dir": str(out_dir),
    }, indent=2))


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".tmp/qa_C13")
    main(out.resolve())
