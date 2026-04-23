"""Catalog of backend approval risk patterns used for modal explanations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, TypedDict

_ALLOWED_SCOPES: Final[tuple[str, ...]] = ("network", "filesystem", "secret", "subprocess")
_SEVERITY_ORDER: Final[dict[str, int]] = {"high": 3, "medium": 2, "low": 1}


class RiskPatternDescription(TypedDict):
    """Human-readable explanation for one approval risk pattern."""

    short: str
    detail: str
    affected: list[str]
    alternative: str
    severity: str


def _entry(
    short: str,
    detail: str,
    affected: Iterable[str],
    alternative: str,
    severity: str,
) -> RiskPatternDescription:
    return {
        "short": short,
        "detail": detail,
        "affected": [scope for scope in _ALLOWED_SCOPES if scope in set(affected)],
        "alternative": alternative,
        "severity": severity,
    }


PATTERN_DESCRIPTIONS: dict[str, RiskPatternDescription] = {
    "PAT_001_SUBPROCESS_NETWORK": _entry(
        short="Subprocess can reach the network",
        detail=(
            "The requested action shells out to a process that may fetch remote content, "
            "call external executables, or bypass the normal sandboxed tool path."
        ),
        affected=("network", "subprocess"),
        alternative="Use an approved connector or the sandboxed network runner instead.",
        severity="high",
    ),
    "PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE": _entry(
        short="Write outside the workspace",
        detail=(
            "The operation can create or overwrite files outside the approved workspace root, "
            "which can leak data or modify user-owned files."
        ),
        affected=("filesystem",),
        alternative="Write through a workspace-relative artifact path only.",
        severity="high",
    ),
    "PAT_003_FILE_READ_OUTSIDE_WORKSPACE": _entry(
        short="Read outside the workspace",
        detail=(
            "The operation can read files outside the approved workspace or read-only data "
            "roots, which may expose private source material."
        ),
        affected=("filesystem",),
        alternative="Load only workspace files or approved read-only datasets.",
        severity="high",
    ),
    "PAT_004_FILE_DELETE_OUTSIDE_WORKSPACE": _entry(
        short="Delete outside the workspace",
        detail=(
            "The action can remove files or directories outside the approved workspace, "
            "which can destroy unrelated user data."
        ),
        affected=("filesystem",),
        alternative="Restrict deletion to workspace-managed artifacts.",
        severity="high",
    ),
    "PAT_005_SECRET_ENV_ACCESS": _entry(
        short="Read environment secrets",
        detail=(
            "The code accesses environment variables, which often hold API keys, tokens, "
            "or deployment credentials."
        ),
        affected=("secret",),
        alternative="Use the secret manager or keyring-backed configuration path.",
        severity="high",
    ),
    "PAT_006_SECRET_KEYRING_ACCESS": _entry(
        short="Read desktop secret vault",
        detail=(
            "The code touches the local secret vault or credential store, so the user must "
            "confirm that the workflow is allowed to inspect saved credentials."
        ),
        affected=("secret",),
        alternative="Use a scoped connector token or an approved secret lookup flow.",
        severity="high",
    ),
    "PAT_007_SECRET_FILE_ACCESS": _entry(
        short="Read secret-bearing files",
        detail=(
            "The code targets files that are likely to contain credentials, certificates, "
            "or private connection material."
        ),
        affected=("filesystem", "secret"),
        alternative="Use a redacted export or a managed secret retrieval API.",
        severity="high",
    ),
    "PAT_008_HTTP_REQUEST_UNAPPROVED": _entry(
        short="Unapproved HTTP request",
        detail=(
            "The operation sends HTTP traffic to an external endpoint that has not been "
            "pre-approved by policy."
        ),
        affected=("network",),
        alternative="Use the approved domain allowlist or a connector abstraction.",
        severity="high",
    ),
    "PAT_009_URLLIB_NETWORK_ACCESS": _entry(
        short="urllib network access",
        detail=(
            "The code reaches the network through urllib, which still needs the same policy "
            "review as requests/httpx traffic."
        ),
        affected=("network",),
        alternative="Use the sanctioned data connector or approved network helper.",
        severity="high",
    ),
    "PAT_010_RAW_SOCKET_ACCESS": _entry(
        short="Raw socket access",
        detail=(
            "The code opens a raw socket, bypassing the higher-level network guards that the "
            "approval flow is meant to control."
        ),
        affected=("network",),
        alternative="Use the managed network sandbox or connector client.",
        severity="high",
    ),
    "PAT_011_DYNAMIC_IMPORT": _entry(
        short="Dynamic import chain",
        detail=(
            "The code loads modules dynamically, which can hide dangerous behavior or bypass "
            "the static tool allowlist."
        ),
        affected=("subprocess",),
        alternative="Import only approved modules at the top of the file.",
        severity="medium",
    ),
    "PAT_012_EVAL_EXEC": _entry(
        short="eval/exec code execution",
        detail=(
            "The code evaluates or executes generated source at runtime, creating a high risk "
            "of arbitrary code execution."
        ),
        affected=("subprocess",),
        alternative="Refactor to structured parsing or a safe dispatcher.",
        severity="high",
    ),
    "PAT_013_OS_SYSTEM_CALL": _entry(
        short="os.system call",
        detail=(
            "The code uses os.system, which can spawn shell commands and hide destructive "
            "or network-facing behavior."
        ),
        affected=("subprocess",),
        alternative="Use an approved sandbox tool or a purpose-built connector.",
        severity="high",
    ),
    "PAT_014_OS_POPEN_CALL": _entry(
        short="os.popen call",
        detail=(
            "The code uses os.popen to launch shell commands and capture their output, "
            "which is not allowed in the approval-free path."
        ),
        affected=("subprocess",),
        alternative="Use a guarded tool or a vetted execution helper.",
        severity="high",
    ),
    "PAT_015_OS_EXEC_REPLACEMENT": _entry(
        short="os.exec replacement",
        detail=(
            "The code replaces the current process image with another executable, which "
            "breaks the normal sandbox lifecycle."
        ),
        affected=("subprocess",),
        alternative="Keep execution inside the managed process sandbox.",
        severity="high",
    ),
    "PAT_016_OS_SPAWN_PROCESS": _entry(
        short="os.spawn process",
        detail=(
            "The code launches a new process via os.spawn*, bypassing the usual policy checks "
            "that wrap approved tool usage."
        ),
        affected=("subprocess",),
        alternative="Invoke the checked sandbox runner instead.",
        severity="high",
    ),
    "PAT_017_SHUTIL_RMTREE": _entry(
        short="Recursive directory delete",
        detail=(
            "The code can recursively delete directories, which is destructive even when the "
            "target path looks legitimate."
        ),
        affected=("filesystem",),
        alternative="Delete only known workspace artifacts one file at a time.",
        severity="high",
    ),
    "PAT_018_SHUTIL_MOVE_OR_COPYTREE": _entry(
        short="Mass filesystem move/copy",
        detail=(
            "The code can move or copy whole directory trees, which may relocate protected "
            "files or overwrite important outputs."
        ),
        affected=("filesystem",),
        alternative="Copy only the required files into a workspace-scoped folder.",
        severity="medium",
    ),
    "PAT_019_PATH_UNLINK_DELETE": _entry(
        short="Path unlink delete",
        detail=(
            "The code deletes files through pathlib.unlink, which is risky when the target "
            "path is computed dynamically."
        ),
        affected=("filesystem",),
        alternative="Use a guarded cleanup helper with explicit workspace validation.",
        severity="high",
    ),
    "PAT_020_PATH_RMDIR_DELETE": _entry(
        short="Path directory delete",
        detail=(
            "The code deletes directories through pathlib.rmdir, which can remove user-owned "
            "folders if path validation is wrong."
        ),
        affected=("filesystem",),
        alternative="Restrict removal to managed workspace subdirectories.",
        severity="high",
    ),
    "PAT_021_PERMISSION_MANIPULATION": _entry(
        short="Permission or ownership change",
        detail=(
            "The code changes chmod or chown settings, which can weaken file security or lock "
            "the user out of their own data."
        ),
        affected=("filesystem",),
        alternative="Avoid permission changes unless the backend workflow explicitly requires it.",
        severity="medium",
    ),
    "PAT_022_PICKLE_DESERIALIZATION": _entry(
        short="Pickle deserialization",
        detail=(
            "The code loads pickle data, which may execute attacker-controlled payloads during "
            "deserialization."
        ),
        affected=("subprocess", "filesystem"),
        alternative="Use JSON, Parquet, or another safe structured format.",
        severity="high",
    ),
    "PAT_023_MARSHAL_DESERIALIZATION": _entry(
        short="Marshal deserialization",
        detail=(
            "The code loads marshal data, which is not a safe interchange format for untrusted "
            "artifacts."
        ),
        affected=("subprocess",),
        alternative="Read structured data through a safe parser instead.",
        severity="high",
    ),
    "PAT_024_MULTIPROCESSING_ACCESS": _entry(
        short="Multiprocessing escape",
        detail=(
            "The code starts worker processes, which can bypass the expected single-process "
            "sandbox boundary."
        ),
        affected=("subprocess",),
        alternative="Keep the work inside the managed execution sandbox.",
        severity="high",
    ),
    "PAT_025_SIGNAL_HANDLER_MANIPULATION": _entry(
        short="Signal handler manipulation",
        detail=(
            "The code installs signal handlers, which can interfere with timeout and shutdown "
            "controls that the runtime depends on."
        ),
        affected=("subprocess",),
        alternative="Let the sandbox manage termination and retries.",
        severity="medium",
    ),
    "PAT_026_BROWSER_OPEN": _entry(
        short="Open browser or external app",
        detail=(
            "The code tries to open a browser or desktop app, which is outside the approved "
            "backend execution scope."
        ),
        affected=("network", "subprocess"),
        alternative="Return the link or artifact path to the operator instead.",
        severity="medium",
    ),
    "PAT_027_BUILTINS_BYPASS": _entry(
        short="Builtins bypass",
        detail=(
            "The code reaches builtins such as eval, exec, or open through an indirect path, "
            "which suggests an attempt to evade direct pattern checks."
        ),
        affected=("subprocess",),
        alternative="Use direct, approved APIs with explicit path and policy checks.",
        severity="high",
    ),
    "PAT_028_GETATTR_BYPASS": _entry(
        short="Attribute lookup bypass",
        detail=(
            "The code uses getattr to retrieve dangerous callables indirectly, which hides the "
            "real operation from static review."
        ),
        affected=("subprocess",),
        alternative="Call only the approved functions directly.",
        severity="high",
    ),
    "PAT_029_COMPILE_EXEC_CHAIN": _entry(
        short="compile-to-exec chain",
        detail=(
            "The code compiles source and then executes it, creating a two-stage execution "
            "path that is hard to audit."
        ),
        affected=("subprocess",),
        alternative="Use declarative configuration or a safe parser.",
        severity="high",
    ),
    "PAT_030_GLOBALS_ACCESS": _entry(
        short="globals dictionary access",
        detail=(
            "The code reaches globals() directly, which can expose unsafe references and make "
            "sandbox bypasses easier."
        ),
        affected=("subprocess",),
        alternative="Keep data flow explicit through approved function arguments.",
        severity="medium",
    ),
    "PAT_031_MODEL_SERIALIZATION_OUTPUT": _entry(
        short="Model serialization warning",
        detail=(
            "The code writes a model or artifact file, so the approval modal should remind the "
            "operator to confirm the output path and contents."
        ),
        affected=("filesystem",),
        alternative="Write only to a workspace-managed export location.",
        severity="medium",
    ),
    "PAT_032_INFINITE_LOOP_RISK": _entry(
        short="Potential infinite loop",
        detail=(
            "The code contains an unbounded loop, which can hang the subprocess and consume the "
            "runtime budget until timeout."
        ),
        affected=("subprocess",),
        alternative="Add a termination condition or iterate over bounded data.",
        severity="low",
    ),
    "PAT_033_DATA_EXFILTRATION_RISK": _entry(
        short="Potential data exfiltration",
        detail=(
            "The pattern suggests copying sensitive data to a remote endpoint or an unknown "
            "destination without explicit policy approval."
        ),
        affected=("network", "secret"),
        alternative="Use an approved destination or redact the payload first.",
        severity="high",
    ),
}


def get_pattern_description(pattern_id: str) -> RiskPatternDescription | None:
    """Return the catalog entry for one pattern id."""

    normalized = pattern_id.strip()
    if not normalized:
        return None
    return PATTERN_DESCRIPTIONS.get(normalized)


def describe_pattern_ids(pattern_ids: Iterable[str]) -> list[tuple[str, RiskPatternDescription]]:
    """Return known catalog entries for a collection of pattern ids."""

    described: list[tuple[str, RiskPatternDescription]] = []
    for pattern_id in pattern_ids:
        description = get_pattern_description(pattern_id)
        if description is not None:
            described.append((pattern_id.strip(), description))
    return described


def select_primary_pattern_id(pattern_ids: Iterable[str]) -> str | None:
    """Pick the highest-severity pattern id from a sequence."""

    best_pattern_id: str | None = None
    best_rank = 0
    for pattern_id, description in describe_pattern_ids(pattern_ids):
        rank = _SEVERITY_ORDER.get(description["severity"], 0)
        if rank > best_rank:
            best_rank = rank
            best_pattern_id = pattern_id
    return best_pattern_id


def merge_affected_scopes(pattern_ids: Iterable[str]) -> list[str]:
    """Merge affected scopes across known patterns, preserving a stable order."""

    scopes: set[str] = set()
    for _pattern_id, description in describe_pattern_ids(pattern_ids):
        scopes.update(description["affected"])
    return [scope for scope in _ALLOWED_SCOPES if scope in scopes]


def recommended_alternative(pattern_ids: Iterable[str]) -> str | None:
    """Return the first available alternative for a set of patterns."""

    for _pattern_id, description in describe_pattern_ids(pattern_ids):
        alternative = description["alternative"].strip()
        if alternative:
            return alternative
    return None
