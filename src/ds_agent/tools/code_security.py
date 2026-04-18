"""Code security checker — validates Python code before sandbox execution.

Inspired by Claude Code's BashTool security modules:
- bashSecurity.ts (injection defense)
- pathValidation.ts (traversal prevention)
- destructiveCommandWarning.ts (dangerous operation detection)

Defense-in-depth: regex pattern scan + AST analysis.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SecurityCheckResult:
    """Result of a code security check."""

    allowed: bool
    warnings: list[str] = field(default_factory=list)
    blocked_patterns: list[str] = field(default_factory=list)


# (compiled_pattern, human_readable_description)
_BLOCKED: list[tuple[re.Pattern[str], str]] = [
    # Process / command execution
    (re.compile(r"os\.system\s*\("), "os.system() call"),
    (re.compile(r"os\.popen\s*\("), "os.popen() — command execution"),
    (re.compile(r"os\.exec[lv]p?e?\s*\("), "os.exec*() — process replacement"),
    (re.compile(r"os\.spawn[lv]p?e?\s*\("), "os.spawn*() — process creation"),
    (re.compile(r"subprocess\.(?:call|run|Popen|check_output|check_call)\s*\("), "subprocess call"),
    # Eval / exec
    (re.compile(r"(?<!\w)eval\s*\("), "eval() — arbitrary code execution"),
    (re.compile(r"(?<!\w)exec\s*\("), "exec() — arbitrary code execution"),
    (re.compile(r"__import__\s*\("), "dynamic __import__()"),
    # Filesystem destructive
    (re.compile(r"shutil\.rmtree\s*\("), "recursive directory deletion"),
    (re.compile(r"shutil\.(?:move|copytree)\s*\("), "filesystem manipulation"),
    (re.compile(r"os\.(?:remove|unlink|rmdir)\s*\("), "file/dir deletion"),
    (re.compile(r"\.unlink\s*\("), "file deletion via pathlib"),
    (re.compile(r"\.rmdir\s*\("), "directory deletion via pathlib"),
    # Filesystem enumeration outside workspace
    (re.compile(r"os\.chmod\s*\(|os\.chown\s*\("), "permission manipulation"),
    # Environment
    (re.compile(r"os\.environ"), "environment variable access"),
    # Network
    (re.compile(r"(?:requests|httpx)\.(?:get|post|put|delete|patch)\s*\("), "HTTP request"),
    (re.compile(r"urllib\.request"), "urllib network access"),
    (re.compile(r"(?<!\w)socket\.\w+"), "raw socket access"),
    # Native / low-level
    (re.compile(r"ctypes\.\w+"), "ctypes — native code access"),
    # Deserialization (code execution risk)
    (re.compile(r"pickle\.loads?\s*\("), "pickle deserialization — code execution risk"),
    (re.compile(r"marshal\.loads?\s*\("), "marshal deserialization"),
    # Concurrency / signals
    (re.compile(r"multiprocessing\.\w+"), "multiprocessing access"),
    (re.compile(r"signal\.signal\s*\("), "signal handler manipulation"),
    # SEC-07: Additional bypass defense patterns
    (
        re.compile(r"getattr\s*\(.+,\s*['\"](?:system|popen|exec|eval|call|run)"),
        "attribute-based bypass",
    ),
    (re.compile(r"importlib\.import_module\s*\("), "dynamic module import"),
    (re.compile(r"compile\s*\(.+\)\s*\n.*exec\s*\(", re.DOTALL), "compile-exec chain"),
    (re.compile(r"globals\s*\(\s*\)\s*\["), "globals() dict access"),
    (re.compile(r"builtins\.\w*(?:eval|exec|open)\s*\("), "builtins bypass"),
    # Browser / external launch
    (re.compile(r"webbrowser\.open"), "browser open"),
]

_WARNINGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"pip\s+install"), "package installation detected"),
    (re.compile(r"\.to_csv\s*\(|\.to_excel\s*\(|\.to_parquet\s*\("), "file output — verify path"),
    (re.compile(r"joblib\.dump|pickle\.dump"), "model serialization — verify output path"),
    (re.compile(r"while\s+True"), "potential infinite loop — ensure break condition"),
    (re.compile(r"open\s*\([^)]*,\s*['\"]w"), "file write via open() — verify path"),
]

# Modules that must never be imported in sandboxed code
_BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "subprocess",
        "shutil",
        "ctypes",
        "signal",
        "multiprocessing",
        "webbrowser",
        "ftplib",
        "smtplib",
        "telnetlib",
        "importlib",
        "socket",  # 3.5 fix: raw network socket access
        "threading",  # 3.5 fix: thread creation bypasses process isolation
    }
)


class CodeSecurityChecker:
    """Validates Python code against blocked and warning patterns.

    Uses two layers of defense:
    1. Regex pattern matching for known dangerous patterns.
    2. AST analysis to catch import-based bypasses.

    Note: This is process-level isolation, NOT a full sandbox.
    For production use, consider Docker/gVisor-based sandboxing.
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        *,
        allowed_external_modules: set[str] | None = None,
        allow_network: bool = False,
    ) -> None:
        self._workspace = (workspace_dir or Path.cwd()).resolve()
        self._allowed_external_modules = frozenset(allowed_external_modules or ())
        self._allow_network = allow_network

    def check(self, code: str) -> SecurityCheckResult:
        """Check code for security issues (regex + AST)."""
        blocked: list[str] = []
        warnings: list[str] = []

        # Layer 1: Regex pattern scan
        for pattern, desc in _BLOCKED:
            if self._allow_network and desc in {
                "HTTP request",
                "urllib network access",
                "raw socket access",
            }:
                continue
            if pattern.search(code):
                blocked.append(desc)

        for pattern, desc in _WARNINGS:
            if pattern.search(code):
                warnings.append(desc)

        # Layer 2: AST analysis (catches dynamic/obfuscated patterns)
        ast_blocked = self._ast_check(code)
        blocked.extend(ast_blocked)

        return SecurityCheckResult(
            allowed=len(blocked) == 0,
            warnings=warnings,
            blocked_patterns=blocked,
        )

    def _ast_check(self, code: str) -> list[str]:
        """AST-level check — catches imports that regex might miss."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Syntax errors may come from shell commands (!pip), magic, etc.
            # Regex layer still provides coverage, so don't block on parse failure.
            return []

        blocked: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split(".")[0]
                    if top_module in _BLOCKED_MODULES and top_module not in self._allowed_external_modules:
                        blocked.append(f"Blocked import: {alias.name}")
                    elif self._is_disallowed_external_import(top_module):
                        blocked.append(f"Disallowed external import: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_module = node.module.split(".")[0]
                if top_module in _BLOCKED_MODULES and top_module not in self._allowed_external_modules:
                    blocked.append(f"Blocked import from: {node.module}")
                elif self._is_disallowed_external_import(top_module):
                    blocked.append(f"Disallowed external import from: {node.module}")
        return blocked

    def _is_disallowed_external_import(self, top_module: str) -> bool:
        if not self._allowed_external_modules:
            return False
        if top_module == "__future__":
            return False
        if top_module in sys.stdlib_module_names:
            return False
        return top_module not in self._allowed_external_modules

    def validate_path(self, file_path: str) -> bool:
        """Check that a file path is within the workspace (traversal prevention)."""
        try:
            resolved = Path(file_path).resolve()
            return resolved.is_relative_to(self._workspace)
        except (ValueError, OSError):
            return False
