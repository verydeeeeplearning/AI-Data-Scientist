"""Domain knowledge base — accumulate domain-specific insights."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import structlog

logger = structlog.get_logger()


class DomainKB:
    """JSON-based domain knowledge profiles."""

    def __init__(self, data_dir: str = "data/memory/domain_kb") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "profiles.json"
        # CON-04: Thread-safe file access
        self._lock = threading.Lock()
        self._profiles: dict[str, dict] = self._load()

    def store_insight(
        self,
        domain: str,
        insight: str,
        category: str = "general",
        confidence: float = 0.8,
        tags: list[str] | None = None,
    ) -> None:
        """Store a domain insight."""
        # 4.7/3.10 fix: hold lock for the full dict-modify+write operation
        with self._lock:
            if domain not in self._profiles:
                self._profiles[domain] = {
                    "domain": domain,
                    "insights": [],
                    "created_at": time.time(),
                }

            self._profiles[domain]["insights"].append(
                {
                    "content": insight,
                    "category": category,
                    "confidence": confidence,
                    "tags": tags or [],
                    "timestamp": time.time(),
                }
            )
            self._profiles[domain]["updated_at"] = time.time()
            self._write_file()

    def get_insights(
        self,
        domain: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query insights with optional filters."""
        results = []
        for profile in self._profiles.values():
            if domain and profile["domain"] != domain:
                continue
            for insight in profile["insights"]:
                if category and insight.get("category") != category:
                    continue
                entry = {"domain": profile["domain"], **insight}
                entry["effective_confidence"] = self._effective_confidence(insight)
                results.append(entry)
        # Sort by effective confidence (decayed), not raw timestamp
        return sorted(results, key=lambda x: x.get("effective_confidence", 0), reverse=True)[:limit]

    def get_memory_hints(self, domain: str | None = None, max_tokens: int = 500) -> str:
        """Generate memory hints for system prompt injection.

        Insights are ranked by effective confidence (time-decayed).
        Insights with effective confidence below 0.3 are excluded.
        """
        insights = self.get_insights(domain=domain, limit=10)
        if not insights:
            return ""

        hints = []
        total_chars = 0
        max_chars = max_tokens * 4  # rough token-to-char ratio

        for insight in insights:
            # Filter out stale insights with low effective confidence
            if insight.get("effective_confidence", 0) < 0.3:
                continue
            line = f"- [{insight['domain']}] {insight['content']}"
            if total_chars + len(line) > max_chars:
                break
            hints.append(line)
            total_chars += len(line)

        return "\n".join(hints)

    @staticmethod
    def _effective_confidence(insight: dict) -> float:
        """Compute time-decayed confidence: original * 0.95^months_elapsed."""
        raw_confidence = float(insight.get("confidence", 0.5))
        timestamp = insight.get("timestamp", 0)
        if not timestamp:
            return raw_confidence
        months_elapsed = (time.time() - float(timestamp)) / (30 * 24 * 3600)
        return float(raw_confidence * (0.95 ** max(0, months_elapsed)))

    def _load(self) -> dict[str, dict]:
        if self._file.exists():
            try:
                return dict(json.loads(self._file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("domain_kb_load_failed", error=str(e))
                return {}
        return {}

    def _write_file(self) -> None:
        """Write profiles to disk — caller must hold self._lock."""
        self._file.write_text(
            json.dumps(self._profiles, indent=2, default=str),
            encoding="utf-8",
        )

    def _save(self) -> None:
        with self._lock:
            self._write_file()
