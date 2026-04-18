"""Self-registering tool registry (Hermes Agent pattern)."""

from __future__ import annotations

import asyncio
import functools
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()


def _safe_log_error(event: str, **fields: Any) -> None:
    """Log an error without letting a bad stdout encoding abort the call.

    Windows default consoles use cp949 / cp1252, and structlog writes via
    ``print()``. A log message containing em-dash, Korean, or other Unicode
    characters can raise ``UnicodeEncodeError``, which would otherwise
    propagate up through ``ToolRegistry.dispatch`` and turn a recoverable
    tool error into an unrecoverable 0.0s crash.
    """
    try:
        logger.error(event, **fields)
    except UnicodeEncodeError:
        try:
            safe_fields = {
                k: (v.encode("ascii", errors="replace").decode("ascii") if isinstance(v, str) else v)
                for k, v in fields.items()
            }
            logger.error(event, **safe_fields)
        except Exception:
            pass


@dataclass
class ToolEntry:
    """Registered tool metadata + handler."""

    name: str
    description: str
    handler: Callable
    category: str = "general"
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    timeout: int = 120
    prompt: str = ""  # LLM usage guide injected into system prompt
    safety_level: str = "safe"  # safe | caution | dangerous

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Global self-registering tool registry.

    Tools register themselves at import time via the @tool decorator.
    DSAgent calls get_definitions() for LLM and dispatch() for execution.
    """

    _tools: ClassVar[dict[str, ToolEntry]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        handler: Callable,
        category: str = "general",
        parameters: dict | None = None,
        timeout: int = 120,
        allow_override: bool = False,
        prompt: str = "",
        safety_level: str = "safe",
    ) -> None:
        if name in cls._tools and not allow_override:
            raise ValueError(f"Tool '{name}' already registered")

        cls._tools[name] = ToolEntry(
            name=name,
            description=description,
            handler=handler,
            category=category,
            parameters=parameters or {"type": "object", "properties": {}},
            timeout=timeout,
            prompt=prompt,
            safety_level=safety_level,
        )
        logger.debug("tool_registered", name=name, category=category)

    @classmethod
    def get_definitions(cls) -> list[dict]:
        """Get all tool schemas in OpenAI function calling format."""
        return [entry.to_openai_schema() for entry in cls._tools.values()]

    @classmethod
    async def dispatch(cls, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name. Returns result string or error.

        Enforces per-tool timeout from ToolEntry.timeout (4.4 fix).
        Validates parameters against the tool's JSON schema before calling
        the handler so the LLM gets actionable feedback instead of a raw
        Python TypeError when it forgets a required argument.
        """
        entry = cls._tools.get(name)
        if entry is None:
            return json.dumps({
                "error": f"Tool not found: {name}",
                "available_tools": sorted(cls._tools.keys()),
            })

        # Pre-call validation — catches missing/extra kwargs before the
        # handler raises TypeError, and returns a self-describing error
        # that the LLM can act on.
        validation_error = cls._validate_arguments(entry, arguments)
        if validation_error is not None:
            return validation_error

        try:
            if asyncio.iscoroutinefunction(entry.handler):
                coro = entry.handler(**arguments)
                result = await asyncio.wait_for(coro, timeout=entry.timeout)
            else:
                result = entry.handler(**arguments)
            return str(result)
        except TimeoutError:
            _safe_log_error("tool_timeout", tool=name, timeout=entry.timeout)
            return json.dumps({"error": f"Tool '{name}' timed out after {entry.timeout}s"})
        except TypeError as e:
            # Should be rare now that we pre-validate, but surface a useful
            # hint if the handler signature drifts from the schema.
            _safe_log_error("tool_type_error", tool=name, error=str(e))
            schema = entry.parameters or {}
            return json.dumps({
                "error": f"TypeError calling {name}: {e}",
                "required": schema.get("required", []),
                "properties": sorted((schema.get("properties") or {}).keys()),
                "hint": (
                    f"Retry the call with all required parameters: "
                    f"{schema.get('required', [])}."
                ),
            })
        except Exception as e:
            _safe_log_error("tool_dispatch_error", tool=name, error=str(e))
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

    @classmethod
    def _validate_arguments(
        cls, entry: Any, arguments: dict[str, Any]
    ) -> str | None:
        """Return an error-JSON string if arguments don't match the schema.

        Checks:
        - All ``required`` keys are present
        - No unknown keys (not in ``properties``)

        Returns None when validation passes.
        """
        schema = entry.parameters or {}
        properties: dict[str, Any] = schema.get("properties") or {}
        required: list[str] = schema.get("required") or []

        missing = [k for k in required if k not in arguments]
        # Allow empty properties (tools with no params declared).
        unknown: list[str] = []
        if properties:
            unknown = [k for k in arguments if k not in properties]

        if not missing and not unknown:
            return None

        error_parts: list[str] = []
        if missing:
            error_parts.append(f"missing required: {missing}")
        if unknown:
            error_parts.append(f"unknown keys: {unknown}")

        logger.error(
            "tool_arg_validation_failed",
            tool=entry.name,
            missing=missing,
            unknown=unknown,
        )
        return json.dumps({
            "error": f"Invalid arguments for {entry.name}: {'; '.join(error_parts)}",
            "required": required,
            "accepted_properties": sorted(properties.keys()),
            "provided": sorted(arguments.keys()),
            "hint": (
                f"Re-invoke {entry.name} with all required parameters "
                f"({required}) and only accepted keys."
            ),
        })

    @classmethod
    def list_tools(cls, category: str | None = None) -> list[str]:
        """List registered tool names, optionally filtered by category."""
        if category:
            return [n for n, e in cls._tools.items() if e.category == category]
        return list(cls._tools.keys())

    @classmethod
    def reset(cls) -> None:
        """Clear all registered tools. For testing only."""
        cls._tools.clear()


def tool(
    name: str,
    description: str,
    category: str = "general",
    parameters: dict | None = None,
    timeout: int = 120,
    prompt: str = "",
    safety_level: str = "safe",
) -> Callable:
    """Decorator for self-registering tools.

    Usage:
        @tool(name="profile_data", description="Profile a dataset", category="ds_analysis")
        async def profile_data(file_path: str) -> str:
            ...
    """

    def decorator(func: Callable) -> Callable:
        ToolRegistry.register(
            name=name,
            description=description,
            handler=func,
            category=category,
            parameters=parameters,
            timeout=timeout,
            prompt=prompt,
            safety_level=safety_level,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator
