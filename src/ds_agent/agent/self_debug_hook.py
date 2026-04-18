"""SelfDebugHook — autonomous error diagnosis, fix suggestion, and retry loop.

Priority 33: runs after LeakageDetection (30) and before OverfittingDetector (35).

When a tool returns an error, this hook:
1. Classifies the error (DataError / CodeBug / EnvError / LogicError / Unknown)
2. Hashes the error signature to detect repeated failures
3. Generates an actionable suggestion (leveraging DS error patterns)
4. Tracks retry count per tool (resets on success)
5. Escalates to ask_user after max_retries exceeded
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from ds_agent.agent.hooks import HookContext, PostToolUseResult, ToolHook
from ds_agent.domain.value_objects.self_debug import ErrorCategory

# ---------------------------------------------------------------------------
# Error classification patterns
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[ErrorCategory, list[str]]] = [
    (
        ErrorCategory.DATA_ERROR,
        [
            r"FileNotFoundError",
            r"No such file or directory",
            r"UnicodeDecodeError",
            r"ParserError",
            r"EmptyDataError",
            r"cannot open",
            r"permission denied",
            r"encoding",
            r"schema.*mismatch",
            r"column.*not found",
            r"KeyError",
        ],
    ),
    (
        ErrorCategory.ENV_ERROR,
        [
            r"ModuleNotFoundError",
            r"No module named",
            r"MemoryError",
            r"CUDA out of memory",
            r"out of memory",
            r"TimeoutError",
            r"timed out",
            r"ConnectionError",
            r"ResourceWarning",
        ],
    ),
    (
        ErrorCategory.CODE_BUG,
        [
            r"TypeError",
            r"IndexError",
            r"AttributeError",
            r"NameError",
            r"ValueError",
            r"ZeroDivisionError",
            r"SyntaxError",
            r"IndentationError",
            r"UnboundLocalError",
        ],
    ),
    (
        ErrorCategory.LOGIC_ERROR,
        [
            r"data.*leakage",
            r"wrong.*join",
            r"wrong.*metric",
            r"inconsistent.*samples",
            r"Only one class present",
            r"train.*test.*gap",
        ],
    ),
]

# Suggestion templates per category
_CATEGORY_SUGGESTIONS: dict[ErrorCategory, str] = {
    ErrorCategory.DATA_ERROR: (
        "Data access issue detected. Verify the file path, encoding, "
        "and schema match expectations. Use file_list to check available files."
    ),
    ErrorCategory.CODE_BUG: (
        "Code error detected. Review the failing line, check variable types "
        "and shapes. Consider adding type checks or defensive guards."
    ),
    ErrorCategory.ENV_ERROR: (
        "Environment error detected. This may require installing a package, "
        "reducing data size, or increasing resource limits. "
        "Consider using ask_user if the issue persists."
    ),
    ErrorCategory.LOGIC_ERROR: (
        "Methodology issue detected. Review the analysis pipeline for logical "
        "errors such as data leakage, wrong joins, or inappropriate metrics."
    ),
    ErrorCategory.UNKNOWN: (
        "Unexpected error. Review the full traceback, check for edge cases "
        "in the data, and consider a different approach."
    ),
}

# DS-specific error patterns with targeted suggestions
_SPECIFIC_PATTERNS: list[tuple[str, str]] = [
    (
        r"could not convert string to float",
        "Encode categorical columns (LabelEncoder/OneHotEncoder) before fitting.",
    ),
    (
        r"inconsistent numbers of samples",
        "X and y row counts differ. Re-align after NaN removal with reset_index(drop=True).",
    ),
    (
        r"average='binary'",
        "Multiclass target — use average='weighted' or 'macro' for metrics.",
    ),
    (
        r"Input contains NaN",
        "Impute missing values (SimpleImputer with strategy='median') before model fitting.",
    ),
    (
        r"Number of features.*does not match",
        "Train/test feature count mismatch. Apply same pipeline to both; fit on train only.",
    ),
    (
        r"duplicate axis",
        "Duplicate index values. Call df.reset_index(drop=True) before the operation.",
    ),
    (
        r"Only one class present",
        "Evaluation set has only one class. Use stratified splitting (stratify=y).",
    ),
    (
        r"has no attribute '(?:predict|fit|transform|score)'",
        "Model not properly initialized. Ensure fit() was called before predict/transform.",
    ),
]


def _classify_error(error_msg: str) -> ErrorCategory:
    """Classify an error message into a category."""
    for category, patterns in _CATEGORY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, error_msg, re.IGNORECASE):
                return category
    return ErrorCategory.UNKNOWN


def _compute_error_signature(error_msg: str) -> str:
    """Hash error type + core message for deduplication.

    Extracts the exception class name and first meaningful line,
    then produces a stable short hash.
    """
    # Try to extract "ExceptionType: message"
    match = re.search(r"(\w+Error|\w+Exception|\w+Warning):\s*(.+?)(?:\n|$)", error_msg)
    if match:
        key = f"{match.group(1)}:{match.group(2).strip()[:80]}"
    else:
        # Fallback: last non-empty line
        lines = [ln.strip() for ln in error_msg.strip().split("\n") if ln.strip()]
        key = lines[-1][:120] if lines else error_msg[:120]

    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _generate_suggestion(error_msg: str, category: ErrorCategory) -> str:
    """Generate an actionable fix suggestion for the error."""
    # Try specific DS patterns first
    for pattern, suggestion in _SPECIFIC_PATTERNS:
        if re.search(pattern, error_msg, re.IGNORECASE):
            return suggestion

    # Fall back to category-level suggestion
    return _CATEGORY_SUGGESTIONS.get(category, _CATEGORY_SUGGESTIONS[ErrorCategory.UNKNOWN])


class SelfDebugHook(ToolHook):
    """Autonomous self-debugging hook.

    Monitors tool errors and provides structured debug decisions,
    tracking retry counts per tool and escalating when limits are reached.
    """

    name = "self_debug"
    priority = 33

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries
        # Per-tool retry counters
        self._retry_counts: dict[str, int] = defaultdict(int)
        # Per-tool error signature history
        self._error_histories: dict[str, list[str]] = defaultdict(list)
        # Per-tool last error signatures (for repeat detection)
        self._signature_history: dict[str, list[str]] = defaultdict(list)

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if not is_error:
            # Success resets the retry counter for this tool
            if tool_name in self._retry_counts:
                self._retry_counts[tool_name] = 0
                self._signature_history[tool_name].clear()
            return PostToolUseResult()

        # Extract error message
        error_msg = self._extract_error_message(result)

        # Classify and analyze
        category = _classify_error(error_msg)
        signature = _compute_error_signature(error_msg)
        previous_sigs = tuple(self._signature_history[tool_name])
        is_repeated = signature in previous_sigs

        # Update tracking state
        self._retry_counts[tool_name] += 1
        attempt = self._retry_counts[tool_name]
        self._signature_history[tool_name].append(signature)
        self._error_histories[tool_name].append(error_msg[:200])

        # Decide action
        if attempt > self._max_retries:
            # Emit escalation event
            context.emit(
                "debug.escalation",
                {
                    "tool_name": tool_name,
                    "error_history": list(self._error_histories[tool_name]),
                    "reason": "max_retries_exceeded",
                    "attempt": attempt,
                },
            )
            return PostToolUseResult(
                modified_result=(
                    f"{result}\n\n"
                    f"[SELF-DEBUG ESCALATION] {self._max_retries} retries exhausted "
                    f"for {tool_name}. Use ask_user to escalate to the operator."
                ),
            )

        # Generate suggestion
        suggestion = _generate_suggestion(error_msg, category)

        # Emit debug attempt event
        context.emit(
            "debug.attempt",
            {
                "tool_name": tool_name,
                "error_category": category,
                "suggestion": suggestion,
                "attempt": attempt,
                "is_repeated": is_repeated,
                "error_signature": signature,
            },
        )

        # Append suggestion to the result so the LLM sees it
        return PostToolUseResult(
            modified_result=(
                f"{result}\n\n"
                f"[SELF-DEBUG] Attempt {attempt}/{self._max_retries} | "
                f"Category: {category} | "
                f"{'⚠ REPEATED ERROR — try a different approach. ' if is_repeated else ''}"
                f"Suggestion: {suggestion}"
            ),
        )

    @staticmethod
    def _extract_error_message(result: str) -> str:
        """Extract the error string from a tool result."""
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and "error" in parsed:
                return str(parsed["error"])
        except (json.JSONDecodeError, TypeError):
            pass
        return result
