"""Code pattern registry — store and retrieve reusable code patterns."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import structlog

logger = structlog.get_logger()


class CodeRegistry:
    """JSON-based code pattern storage."""

    def __init__(self, data_dir: str = "data/memory/code_registry") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "patterns.json"
        # CON-04: Thread-safe file access
        self._lock = threading.Lock()
        self._patterns: dict[str, dict] = self._load()

    def store_pattern(
        self,
        name: str,
        code: str,
        description: str,
        tags: list[str] | None = None,
        task_type: str | None = None,
    ) -> str:
        """Store a code pattern. Returns pattern name."""
        # 4.7/3.10 fix: hold lock for the full dict-modify+write operation
        with self._lock:
            self._patterns[name] = {
                "name": name,
                "code": code,
                "description": description,
                "tags": tags or [],
                "task_type": task_type,
                "use_count": 0,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._write_file()
        return name

    def get_pattern(self, name: str) -> dict | None:
        """Retrieve a pattern by name."""
        return self._patterns.get(name)

    def search_patterns(
        self,
        query: str = "",
        task_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search patterns by keyword and optional task type."""
        results = []
        query_lower = query.lower()
        for pattern in self._patterns.values():
            if task_type and pattern.get("task_type") != task_type:
                continue
            if query_lower:
                parts = [pattern["name"], pattern["description"]]
                parts.extend(pattern.get("tags", []))
                searchable = " ".join(parts).lower()
                if query_lower not in searchable:
                    continue
            results.append(pattern)
        return results[:limit]

    def increment_use_count(self, name: str) -> None:
        """Track pattern usage."""
        with self._lock:
            if name in self._patterns:
                self._patterns[name]["use_count"] += 1
                self._patterns[name]["updated_at"] = time.time()
                self._write_file()

    def _load(self) -> dict[str, dict]:
        if self._file.exists():
            try:
                return dict(json.loads(self._file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("code_registry_load_failed", error=str(e))
                return {}
        return {}

    def _write_file(self) -> None:
        """Write patterns to disk — caller must hold self._lock."""
        self._file.write_text(
            json.dumps(self._patterns, indent=2, default=str),
            encoding="utf-8",
        )

    def _save(self) -> None:
        with self._lock:
            self._write_file()
