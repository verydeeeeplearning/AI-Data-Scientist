"""Integration test: UnifiedMemoryStore wired into memory tools.

Test 0-3.8: Agent can use memory_store and memory_search tools
with real SQLite backend across simulated sessions.
"""

import json

import pytest

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType


class TestMemoryToolIntegration:
    """Memory tools backed by UnifiedMemoryStore."""

    def test_store_then_search_roundtrip(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "memory.db"))

        # Store
        entry = MemoryEntry(
            type=MemoryType.DOMAIN,
            key="customer_churn",
            content="Churn defined as 90 day inactivity. Use logistic regression.",
            tags=["churn", "classification"],
            source_session_id="session-001",
        )
        store.store(entry)

        # Search
        results = store.search("churn")
        assert len(results) >= 1
        assert any("churn" in r.content.lower() for r in results)

    def test_cross_session_persistence(self, tmp_path):
        """Simulate session 1 storing, session 2 retrieving."""
        db_path = str(tmp_path / "memory.db")

        from ds_agent.memory.unified_store import UnifiedMemoryStore

        # Session 1: store
        store1 = UnifiedMemoryStore(db_path=db_path)
        store1.store(MemoryEntry(
            type=MemoryType.PROJECT,
            key="best_model",
            content="XGBoost with 50 trees gave best results (accuracy=0.89)",
            source_session_id="session-001",
        ))
        del store1  # Close session 1

        # Session 2: search
        store2 = UnifiedMemoryStore(db_path=db_path)
        results = store2.search("XGBoost")
        assert len(results) >= 1
        assert "accuracy" in results[0].content.lower()

    def test_multiple_types_coexist(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "memory.db"))

        # Store different types
        store.store(MemoryEntry(type=MemoryType.SESSION, key="s1", content="Session info"))
        store.store(MemoryEntry(type=MemoryType.PROJECT, key="p1", content="Project info"))
        store.store(MemoryEntry(type=MemoryType.DOMAIN, key="d1", content="Domain info"))
        store.store(MemoryEntry(type=MemoryType.GLOBAL, key="g1", content="Global info"))

        # Each type should be independently queryable
        assert len(store.list_by_type(MemoryType.SESSION)) == 1
        assert len(store.list_by_type(MemoryType.PROJECT)) == 1
        assert len(store.list_by_type(MemoryType.DOMAIN)) == 1
        assert len(store.list_by_type(MemoryType.GLOBAL)) == 1

    def test_store_conforms_to_protocol(self, tmp_path):
        """UnifiedMemoryStore implements MemoryStorePort protocol."""
        from ds_agent.domain.interfaces.memory import MemoryStorePort
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "memory.db"))
        assert isinstance(store, MemoryStorePort)
